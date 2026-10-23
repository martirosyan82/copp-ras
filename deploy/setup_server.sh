#!/bin/bash
# ==============================================================================
# setup_server.sh — Полный скрипт автоматического развертывания ЦОПП (copp-ras)
# Для ОС: Ubuntu 24.04 / 26.04 LTS (чистый сервер)
#
# Настраивает:
#   1. SSH на порт 52678 (вместо 22) + UFW (порты 80, 443, 52678)
#   2. Системные пакеты (Python 3, Nginx, Git, venv, SQLite)
#   3. Клонирование / настройка репозитория в /var/www/copp-ras
#   4. Установка SSL-сертификата (*.copp82.ru / ras.copp82.ru) в Nginx
#   5. Gunicorn Systemd сервис с таймаутом 300с и автозапуском
#   6. Zero-DB запуск: сайт сразу работает и встречает мастера настройки БД
# ==============================================================================

set -euo pipefail

# ─── ЦВЕТА И ВЫВОД ────────────────────────────────────────────────────────────
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
CYAN='\033[0;36m'
BOLD='\033[1m'
NC='\033[0m'

info()    { echo -e "${GREEN}[OK]${NC}    $*"; }
warn()    { echo -e "${YELLOW}[WARN]${NC}  $*"; }
error()   { echo -e "${RED}[ERROR]${NC} $*"; }
section() { echo -e "\n${CYAN}════════════════════════════════════════════════════════════${NC}"; echo -e "${CYAN}▶ $*${NC}"; echo -e "${CYAN}════════════════════════════════════════════════════════════${NC}"; }

# ─── ПАРАМЕТРЫ ПО УМОЛЧАНИЮ ───────────────────────────────────────────────────
APP_DIR="/var/www/copp-ras"
SERVICE_NAME="copp-ras"
APP_USER="www-data"
SSH_PORT="52678"
DEFAULT_GIT_REPO="https://github.com/martirosyan82/copp-ras.git"
SERVER_IP_FALLBACK="195.88.112.88"
DOMAIN_NAME="ras.copp82.ru"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# ─── ПРОВЕРКА ROOT ────────────────────────────────────────────────────────────
if [ "$EUID" -ne 0 ]; then
    error "Этот скрипт должен быть запущен с правами root: sudo bash setup_server.sh"
    exit 1
fi

echo -e "${BOLD}${CYAN}"
cat << "BANNER"
  ╔════════════════════════════════════════════════════════════╗
  ║    ЦОПП РК — Автоматическое развёртывание copp-ras         ║
  ║    Ubuntu 24.04 / 26.04 | Nginx + Gunicorn + Zero-DB       ║
  ║    Сервер: 195.88.112.88 | Домен: ras.copp82.ru           ║
  ╚════════════════════════════════════════════════════════════╝
BANNER
echo -e "${NC}"

# ─── 1. НАСТРОЙКА SSH (ПОРТ 52678) И ФАЕРВОЛА UFW ─────────────────────────────
section "1/6. Настройка портов (SSH 52678, HTTP 80, HTTPS 443)"

info "Конфигурирую SSH на порт $SSH_PORT..."
mkdir -p /etc/ssh/sshd_config.d
cat > /etc/ssh/sshd_config.d/50-copp-port.conf << EOF
Port $SSH_PORT
EOF

# Обработка systemd socket activation (Ubuntu 24.04 / 26.04)
if systemctl is-active --quiet ssh.socket 2>/dev/null || systemctl is-enabled --quiet ssh.socket 2>/dev/null; then
    mkdir -p /etc/systemd/system/ssh.socket.d
    cat > /etc/systemd/system/ssh.socket.d/listen.conf << EOF
[Socket]
ListenStream=
ListenStream=$SSH_PORT
EOF
    systemctl daemon-reload
    systemctl restart ssh.socket
    info "SSH socket переключен на порт $SSH_PORT (ssh.socket)"
else
    # Классический ssh.service
    if grep -q "^#\?Port " /etc/ssh/sshd_config; then
        sed -i "s/^#\?Port .*/Port $SSH_PORT/" /etc/ssh/sshd_config
    else
        echo "Port $SSH_PORT" >> /etc/ssh/sshd_config
    fi
    systemctl restart ssh 2>/dev/null || systemctl restart sshd 2>/dev/null || true
    info "SSH service переключен на порт $SSH_PORT"
fi

info "Настройка фаервола UFW..."
apt-get update -qq
apt-get install -y -qq ufw >/dev/null

ufw default deny incoming
ufw default allow outgoing
ufw allow ${SSH_PORT}/tcp comment 'SSH Custom'
ufw allow 80/tcp comment 'HTTP'
ufw allow 443/tcp comment 'HTTPS'

# Удаляем стандартный 22 порт из правил
ufw delete allow 22/tcp 2>/dev/null || true
ufw --force enable
info "UFW активирован: открыты порты 80, 443, $SSH_PORT"

# ─── 2. УСТАНОВКА СИСТЕМНЫХ ПАКЕТОВ ───────────────────────────────────────────
section "2/6. Установка необходимых пакетов Ubuntu"

export DEBIAN_FRONTEND=noninteractive
apt-get install -y -qq \
    python3 \
    python3-venv \
    python3-pip \
    git \
    nginx \
    curl \
    rsync \
    sqlite3 \
    libmagic1 \
    libpango-1.0-0 \
    libharfbuzz0b \
    libpangoft2-1.0-0 >/dev/null

info "Системные зависимости установлены."

# ─── 3. КЛОНИРОВАНИЕ / РАЗМЕЩЕНИЕ КОДА ПРОЕКТА ─────────────────────────────────
section "3/6. Размещение кода проекта в $APP_DIR"

mkdir -p /var/www

# Проверяем, запущен ли скрипт прямо из каталога с проектом
if [ -f "$SCRIPT_DIR/wsgi.py" ] || [ -f "$SCRIPT_DIR/../wsgi.py" ]; then
    SRC_DIR="$SCRIPT_DIR"
    [ -f "$SCRIPT_DIR/../wsgi.py" ] && SRC_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
    
    if [ "$SRC_DIR" != "$APP_DIR" ]; then
        info "Копирую файлы проекта из $SRC_DIR в $APP_DIR..."
        mkdir -p "$APP_DIR"
        rsync -a --exclude 'venv' --exclude '__pycache__' --exclude '.git' "$SRC_DIR/" "$APP_DIR/"
    else
        info "Скрипт уже запущен в целевой папке $APP_DIR."
    fi
else
    # Клонирование из Git
    if [ ! -d "$APP_DIR/.git" ]; then
        info "Клонирую репозиторий: $DEFAULT_GIT_REPO..."
        git clone "$DEFAULT_GIT_REPO" "$APP_DIR" || {
            error "Не удалось клонировать репозиторий через Git."
            error "Пожалуйста, скопируйте файлы проекта в $APP_DIR вручную и перезапустите скрипт."
            exit 1
        }
    else
        info "Папка $APP_DIR уже существует, пропускаю клонирование."
    fi
fi

cd "$APP_DIR"
git config --global --add safe.directory "$APP_DIR" 2>/dev/null || true

# Гарантируем наличие .env с постоянным SECRET_KEY
if [ ! -f "$APP_DIR/.env" ]; then
    info "Создаю файл .env с постоянным SECRET_KEY для Gunicorn..."
    SECRET_HEX=$(python3 -c "import secrets; print(secrets.token_hex(32))" 2>/dev/null || openssl rand -hex 32)
    cat > "$APP_DIR/.env" << EOF
SECRET_KEY=$SECRET_HEX
ADMIN_PASSWORD=admin123
FLASK_CONFIG=production
EOF
    chown "$APP_USER":"$APP_USER" "$APP_DIR/.env"
    chmod 600 "$APP_DIR/.env"
fi

# Создаем структуру каталогов для загрузок
mkdir -p "$APP_DIR/app/uploads"
mkdir -p "$APP_DIR/app/static/uploads"
mkdir -p "$APP_DIR/backups"

# ─── 4. УСТАНОВКА PYTHON VENV И ЗАВИСИМОСТЕЙ ──────────────────────────────────
section "4/6. Сборка Python окружения (venv)"

if [ ! -d "$APP_DIR/venv" ]; then
    info "Создаю виртуальное окружение venv..."
    python3 -m venv "$APP_DIR/venv"
fi

info "Устанавливаю пакеты из requirements.txt..."
"$APP_DIR/venv/bin/pip" install --upgrade pip --quiet
if [ -f "$APP_DIR/requirements.txt" ]; then
    "$APP_DIR/venv/bin/pip" install -r "$APP_DIR/requirements.txt" --quiet
fi
"$APP_DIR/venv/bin/pip" install gunicorn python-dotenv --quiet
info "Python зависимости успешно установлены."

# ─── 5. УСТАНОВКА SSL И НАСТРОЙКА NGINX ────────────────────────────────────────
section "5/6. Установка SSL-сертификатов и настройка Nginx"

mkdir -p /etc/ssl/certs /etc/ssl/private

# Ищем сертификаты в проекте deploy/ssl
SSL_SRC="$APP_DIR/deploy/ssl"
if [ -f "$SSL_SRC/copp82.ru.fullchain.crt" ] && [ -f "$SSL_SRC/copp82.ru.key" ]; then
    info "Устанавливаю SSL-сертификат *.copp82.ru..."
    cp "$SSL_SRC/copp82.ru.fullchain.crt" /etc/ssl/certs/copp82.ru.fullchain.crt
    cp "$SSL_SRC/copp82.ru.key" /etc/ssl/private/copp82.ru.key
    chmod 644 /etc/ssl/certs/copp82.ru.fullchain.crt
    chmod 600 /etc/ssl/private/copp82.ru.key
    HAS_SSL=true
else
    warn "Сертификаты в $SSL_SRC не найдены, создаю временный самоподписанный сертификат..."
    openssl req -x509 -nodes -days 365 -newkey rsa:2048 \
        -keyout /etc/ssl/private/copp82.ru.key \
        -out /etc/ssl/certs/copp82.ru.fullchain.crt \
        -subj "/C=RU/ST=Crimea/L=Simferopol/O=COPP/CN=*.copp82.ru" >/dev/null 2>&1
    chmod 644 /etc/ssl/certs/copp82.ru.fullchain.crt
    chmod 600 /etc/ssl/private/copp82.ru.key
    HAS_SSL=true
fi

# Конфигурация Nginx сайта для copp-ras
cat > "/etc/nginx/sites-available/$SERVICE_NAME" << 'NGINXEOF'
# 1. Редирект с HTTP на HTTPS для рабочего домена ras.copp82.ru
server {
    listen 80;
    listen [::]:80;
    server_name ras.copp82.ru;
    return 301 https://$host$request_uri;
}

# 2. Прямой HTTP доступ по IP-адресу (для первоначальной настройки Zero-DB до делегирования домена)
server {
    listen 80 default_server;
    listen [::]:80 default_server;
    server_name _;

    client_max_body_size 500M;
    client_body_timeout 300s;

    location /static/ {
        alias /var/www/copp-ras/app/static/;
        expires 30d;
        add_header Cache-Control "public, no-transform";
    }

    location / {
        proxy_pass http://127.0.0.1:5000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_read_timeout 300s;
        proxy_connect_timeout 300s;
        proxy_send_timeout 300s;
    }
}

# 3. Основной защищенный HTTPS сервер
server {
    listen 443 ssl default_server;
    listen [::]:443 ssl default_server;
    server_name ras.copp82.ru 195.88.112.88 _;

    ssl_certificate /etc/ssl/certs/copp82.ru.fullchain.crt;
    ssl_certificate_key /etc/ssl/private/copp82.ru.key;

    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_prefer_server_ciphers on;
    ssl_ciphers HIGH:!aNULL:!MD5;
    ssl_session_cache shared:SSL:10m;
    ssl_session_timeout 1d;

    client_max_body_size 500M;
    client_body_timeout 300s;

    location /static/ {
        alias /var/www/copp-ras/app/static/;
        expires 30d;
        add_header Cache-Control "public, no-transform";
    }

    location / {
        proxy_pass http://127.0.0.1:5000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto https;
        proxy_read_timeout 300s;
        proxy_connect_timeout 300s;
        proxy_send_timeout 300s;
    }
}
NGINXEOF

# Активация сайта и удаление default
ln -sf "/etc/nginx/sites-available/$SERVICE_NAME" "/etc/nginx/sites-enabled/$SERVICE_NAME"
rm -f /etc/nginx/sites-enabled/default

# Чистка дубликатов client_max_body_size в общем nginx.conf
if grep -q "client_max_body_size" /etc/nginx/nginx.conf 2>/dev/null; then
    sed -i '/client_max_body_size/d' /etc/nginx/nginx.conf
fi
sed -i '/http {/a \    client_max_body_size 500M;' /etc/nginx/nginx.conf

nginx -t
systemctl reload nginx 2>/dev/null || systemctl restart nginx
info "Nginx успешно настроен и запущен."

# ─── 6. SYSTEMD СЕРВИС GUNICORN И ПРАВА ────────────────────────────────────────
section "6/6. Настройка службы Gunicorn и запуск сервиса"

# Создаем файл службы
cat > "/etc/systemd/system/${SERVICE_NAME}.service" << EOF
[Unit]
Description=COPP RAS Gunicorn Application
After=network.target

[Service]
User=$APP_USER
Group=$APP_USER
WorkingDirectory=$APP_DIR
Environment="PATH=$APP_DIR/venv/bin"
EnvironmentFile=-$APP_DIR/.env
ExecStart=$APP_DIR/venv/bin/gunicorn \\
    --workers 4 \\
    --timeout 300 \\
    --bind 127.0.0.1:5000 \\
    --access-logfile /var/log/${SERVICE_NAME}_access.log \\
    --error-logfile /var/log/${SERVICE_NAME}_error.log \\
    wsgi:app
Restart=always
RestartSec=3

[Install]
WantedBy=multi-user.target
EOF

# Лог-файлы
touch /var/log/${SERVICE_NAME}_error.log /var/log/${SERVICE_NAME}_access.log
chown "$APP_USER":"$APP_USER" /var/log/${SERVICE_NAME}_error.log /var/log/${SERVICE_NAME}_access.log

# Назначение прав на файлы проекта
chown -R "$APP_USER":"$APP_USER" "$APP_DIR"
chmod -R 755 "$APP_DIR"
chmod -R 775 "$APP_DIR/app/uploads"
chmod -R 775 "$APP_DIR/app/static/uploads"
chmod -R 775 "$APP_DIR/backups"
[ -f "$APP_DIR/reports.db" ] && chmod 664 "$APP_DIR/reports.db"

# Запуск службы
systemctl daemon-reload
systemctl enable --now "$SERVICE_NAME"
sleep 2

if systemctl is-active --quiet "$SERVICE_NAME"; then
    info "Сервис $SERVICE_NAME успешно запущен!"
else
    error "Сервис не смог запуститься! Проверьте логи:"
    journalctl -u "$SERVICE_NAME" --no-pager -n 20
    exit 1
fi

SERVER_IP=$(curl -s -m 3 -4 https://api.ipify.org 2>/dev/null || curl -s -m 3 -4 https://icanhazip.com 2>/dev/null || echo "$SERVER_IP_FALLBACK")
if [[ ! "$SERVER_IP" =~ ^[0-9]+\.[0-9]+\.[0-9]+\.[0-9]+$ ]]; then
    SERVER_IP="$SERVER_IP_FALLBACK"
fi

echo ""
echo -e "${BOLD}${GREEN}════════════════════════════════════════════════════════════${NC}"
echo -e "${BOLD}${GREEN}  РАЗВЁРТЫВАНИЕ COPP-RAS УСПЕШНО ЗАВЕРШЕНО!                 ${NC}"
echo -e "${BOLD}${GREEN}════════════════════════════════════════════════════════════${NC}"
echo ""
echo -e "  ${BOLD}Параметры подключения:${NC}"
echo -e "    ► SSH:            ${CYAN}ssh -p $SSH_PORT root@$SERVER_IP${NC}"
echo -e "    ► Веб-сайт:       ${CYAN}https://ras.copp82.ru${NC} или ${CYAN}http://$SERVER_IP${NC}"
echo ""
echo -e "  ${BOLD}Первоначальная настройка базы данных:${NC}"
echo -e "    Проект запущен в режиме ${YELLOW}Zero-DB${NC}."
echo -e "    Откройте сайт в браузере: ${CYAN}http://$SERVER_IP${NC}"
echo -e "    На открывшейся странице мастера настройки вы сможете в один клик:"
echo -e "      1. Загрузить ваш бэкап (${BOLD}.zip${NC} архив или файл ${BOLD}.db${NC} / ${BOLD}.sqlite${NC})"
echo -e "      2. Либо создать чистую базу данных (пользователь ${BOLD}admin${NC})"
echo ""
echo -e "  ${BOLD}Полезные команды управления:${NC}"
echo -e "    sudo systemctl status $SERVICE_NAME           # Статус сервиса"
echo -e "    sudo journalctl -u $SERVICE_NAME -f           # Живые логи Gunicorn"
echo -e "    sudo tail -f /var/log/${SERVICE_NAME}_error.log  # Ошибки приложения"
echo ""
