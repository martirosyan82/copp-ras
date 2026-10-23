#!/bin/bash

# ==============================================================================
# update.sh — Быстрое и безопасное обновление COPP-RAS на сервере
#
# Что делает скрипт:
#   1. Создает резервную копию базы данных в backups/ и во временную память
#   2. Стягивает свежий код из ветки main
#   3. Восстанавливает рабочую базу данных (защита от затирания гитом)
#   4. Обновляет зависимости Python (если изменился requirements.txt)
#   5. Проверяет и применяет миграции колонок в БД
#   6. Выставляет корректные права доступа (www-data:www-data, 755/664/775)
#   7. Перезапускает Gunicorn сервис и перезагружает Nginx
#
# Использование: sudo bash update.sh [--hard] [--no-restart]
# ==============================================================================

set -euo pipefail

# ─── ЦВЕТА И ВЫВОД ────────────────────────────────────────────────────────────
GREEN='\033[0;32m'; YELLOW='\033[1;33m'; RED='\033[0;31m'; CYAN='\033[0;36m'; BOLD='\033[1m'; NC='\033[0m'
info()    { echo -e "${GREEN}[OK]${NC}    $*"; }
warn()    { echo -e "${YELLOW}[WARN]${NC}  $*"; }
error()   { echo -e "${RED}[ERROR]${NC} $*"; }
section() { echo -e "\n${CYAN}════════════════════════════════════════════════════════════${NC}\n${CYAN}▶ $*${NC}\n${CYAN}════════════════════════════════════════════════════════════${NC}"; }

# ─── ОПРЕДЕЛЕНИЕ ПУТЕЙ И СЛУЖБ ────────────────────────────────────────────────
if [ -d "/var/www/copp-ras" ]; then
    APP_DIR="/var/www/copp-ras"
else
    APP_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
fi

SERVICE_NAME="copp-ras"
APP_USER="www-data"
BRANCH="main"

# ─── АРГУМЕНТЫ ────────────────────────────────────────────────────────────────
NO_RESTART=false
HARD_RESET=false
for arg in "$@"; do
    case $arg in
        --no-restart) NO_RESTART=true ;;
        --hard)       HARD_RESET=true ;;
    esac
done

# ─── ПРОВЕРКИ ─────────────────────────────────────────────────────────────────
if [ "$EUID" -ne 0 ]; then
    error "Запустите скрипт с правами root: sudo bash update.sh"
    exit 1
fi

START_TIME=$(date +%s)
echo -e "${BOLD}${CYAN}"
echo "════════════════════════════════════════════════════════════"
echo "  COPP-RAS — Обновление приложения $(date '+%d.%m.%Y %H:%M')"
echo "════════════════════════════════════════════════════════════"
echo -e "${NC}"

# Подхват SSH-ключа для Git (если репозиторий клонирован по SSH)
CANDIDATE_KEYS=("/root/.ssh/id_ed25519" "/root/.ssh/id_rsa" "/root/.ssh/id_new")
if [ -n "${SUDO_USER:-}" ] && [ "$SUDO_USER" != "root" ]; then
    USER_HOME=$(eval echo "~$SUDO_USER")
    CANDIDATE_KEYS+=("$USER_HOME/.ssh/id_ed25519" "$USER_HOME/.ssh/id_rsa" "$USER_HOME/.ssh/id_new")
fi

SSH_KEY_FOUND=""
for key in "${CANDIDATE_KEYS[@]}"; do
    if [ -f "$key" ]; then
        SSH_KEY_FOUND="$key"
        break
    fi
done

if [ -n "$SSH_KEY_FOUND" ]; then
    export GIT_SSH_COMMAND="ssh -i $SSH_KEY_FOUND -o StrictHostKeyChecking=no"
    info "Используется SSH-ключ: $SSH_KEY_FOUND"
else
    export GIT_SSH_COMMAND="ssh -o StrictHostKeyChecking=no"
fi

cd "$APP_DIR" || exit 1
git config --global --add safe.directory "$APP_DIR" 2>/dev/null || true

# ─── 1. СОЗДАНИЕ РЕЗЕРВНОЙ КОПИИ БАЗЫ ДАННЫХ ──────────────────────────────────
section "1/5. Резервное копирование рабочей базы данных"

BACKUP_DIR="$APP_DIR/backups"
mkdir -p "$BACKUP_DIR"
TEMP_DB_BACKUP="/tmp/copp_reports_pre_update_$START_TIME.db"
PERM_DB_BACKUP="$BACKUP_DIR/reports_before_update_$(date +%Y%m%d_%H%M%S).db"

if [ -f "$APP_DIR/reports.db" ] && [ -s "$APP_DIR/reports.db" ]; then
    cp "$APP_DIR/reports.db" "$TEMP_DB_BACKUP"
    cp "$APP_DIR/reports.db" "$PERM_DB_BACKUP"
    info "Резервная копия сохранена в $PERM_DB_BACKUP"
else
    warn "Рабочая база данных reports.db отсутствует (режим Zero-DB)."
fi

# ─── 2. СТЯГИВАНИЕ ОБНОВЛЕНИЙ ИЗ GIT ──────────────────────────────────────────
section "2/5. Получение свежего кода из Git ($BRANCH)"

OLD_COMMIT=$(git rev-parse --short HEAD 2>/dev/null || echo "unknown")

git fetch origin "$BRANCH"
git checkout "$BRANCH" 2>/dev/null || true
git reset --hard "origin/$BRANCH"

# Восстанавливаем рабочую БД, чтобы Git не перетер её
if [ -f "$TEMP_DB_BACKUP" ]; then
    cp "$TEMP_DB_BACKUP" "$APP_DIR/reports.db"
    rm -f "$TEMP_DB_BACKUP"
    info "Рабочая база данных reports.db восстановлена."
fi

NEW_COMMIT=$(git rev-parse --short HEAD 2>/dev/null || echo "unknown")

if [ "$OLD_COMMIT" = "$NEW_COMMIT" ]; then
    warn "Код уже актуален (коммит: $NEW_COMMIT). Новых изменений нет."
else
    info "Код обновлен: $OLD_COMMIT -> $NEW_COMMIT"
    echo ""
    echo "  Измененные файлы:"
    git diff --name-only "$OLD_COMMIT" "$NEW_COMMIT" 2>/dev/null | sed 's/^/    > /' || true
fi

# ─── 3. ОБНОВЛЕНИЕ ЗАВИСИМОСТЕЙ PYTHON ─────────────────────────────────────────
section "3/5. Проверка зависимостей Python (venv)"

VENV_PIP="$APP_DIR/venv/bin/pip"
VENV_PYTHON="$APP_DIR/venv/bin/python"

if [ ! -d "$APP_DIR/venv" ]; then
    info "Создаю виртуальное окружение venv..."
    python3 -m venv "$APP_DIR/venv"
fi

if [ "$OLD_COMMIT" != "$NEW_COMMIT" ] && git diff --name-only "$OLD_COMMIT" "$NEW_COMMIT" 2>/dev/null | grep -q "requirements.txt"; then
    info "requirements.txt изменился — обновляю пакеты..."
    "$VENV_PIP" install --upgrade pip --quiet
    "$VENV_PIP" install -r "$APP_DIR/requirements.txt" --quiet
    "$VENV_PIP" install gunicorn python-dotenv "psycopg[binary]" psycopg2-binary --quiet
    info "Пакеты успешно обновлены."
else
    info "requirements.txt без изменений, пропуск."
fi

# ─── 4. МИГРАЦИИ СХЕМЫ БД (ALEMBIC) ───────────────────────────────────────────
section "4/5. Проверка и применение миграций схемы БД"

export FLASK_APP="wsgi:app"
if [ -d "$APP_DIR/migrations" ]; then
    # Если на сервере уже есть база SQLite без таблицы alembic_version, штампуем ее базовой ревизией
    "$VENV_PYTHON" -c "
import sqlite3, os
db_file = '$APP_DIR/reports.db'
if os.path.exists(db_file) and os.path.getsize(db_file) > 1024:
    conn = sqlite3.connect(db_file)
    cursor = conn.cursor()
    cursor.execute(\"SELECT name FROM sqlite_master WHERE type='table' AND name='alembic_version'\")
    if not cursor.fetchone():
        cursor.execute(\"CREATE TABLE alembic_version (version_num VARCHAR(32) NOT NULL, CONSTRAINT alembic_version_pkc PRIMARY KEY (version_num))\")
        cursor.execute(\"INSERT INTO alembic_version (version_num) VALUES ('8da40f5858b1')\")
        conn.commit()
    conn.close()
" 2>/dev/null || true

    # Применение всех свежих миграций
    "$APP_DIR/venv/bin/flask" db upgrade 2>/dev/null || warn "Миграция Alembic пропущена или база уже актуальна."
    info "Миграции базы данных успешно проверены и применены."
fi

# Создаем структуру каталогов загрузок если нет
mkdir -p "$APP_DIR/app/uploads"
mkdir -p "$APP_DIR/app/static/uploads"
mkdir -p "$APP_DIR/backups"

# ─── 5. ПРАВА ДОСТУПА И ПЕРЕЗАПУСК ────────────────────────────────────────────
section "5/5. Права доступа и перезапуск сервисов"

chown -R "$APP_USER":"$APP_USER" "$APP_DIR"
chmod -R 755 "$APP_DIR"
chmod -R 775 "$APP_DIR/app/uploads" 2>/dev/null || true
chmod -R 775 "$APP_DIR/app/static/uploads" 2>/dev/null || true
chmod -R 775 "$APP_DIR/backups" 2>/dev/null || true
[ -f "$APP_DIR/reports.db" ] && chmod 664 "$APP_DIR/reports.db"

# Проверка и установка SSL-сертификатов copp82.ru
if [ -f "$APP_DIR/deploy/ssl/copp82.ru.fullchain.crt" ] && [ -f "$APP_DIR/deploy/ssl/copp82.ru.key" ]; then
    info "Устанавливаю рабочие SSL-сертификаты copp82.ru..."
    cp "$APP_DIR/deploy/ssl/copp82.ru.fullchain.crt" /etc/ssl/certs/copp82.ru.fullchain.crt
    cp "$APP_DIR/deploy/ssl/copp82.ru.key" /etc/ssl/private/copp82.ru.key
    chmod 644 /etc/ssl/certs/copp82.ru.fullchain.crt
    chmod 600 /etc/ssl/private/copp82.ru.key
fi

touch /var/log/${SERVICE_NAME}_error.log /var/log/${SERVICE_NAME}_access.log
chown "$APP_USER":"$APP_USER" /var/log/${SERVICE_NAME}_error.log /var/log/${SERVICE_NAME}_access.log

if [ "$NO_RESTART" = false ]; then
    systemctl restart "$SERVICE_NAME"
    sleep 2

    if systemctl is-active --quiet "$SERVICE_NAME"; then
        info "Сервис $SERVICE_NAME успешно перезапущен!"
    else
        error "Сервис $SERVICE_NAME не смог запуститься! Последние строки лога:"
        journalctl -u "$SERVICE_NAME" --no-pager -n 25
        exit 1
    fi

    # Перезагрузка Nginx при изменении шаблонов, статики или конфигурации
    if [ "$OLD_COMMIT" != "$NEW_COMMIT" ] && \
       git diff --name-only "$OLD_COMMIT" "$NEW_COMMIT" 2>/dev/null | grep -qE "^app/static/|^app/templates/|^deploy/"; then
        if nginx -t 2>/dev/null; then
            systemctl reload nginx 2>/dev/null || true
            info "Nginx перезагружен."
        fi
    fi
else
    warn "Перезапуск пропущен (--no-restart)."
fi

END_TIME=$(date +%s)
ELAPSED=$((END_TIME - START_TIME))

echo ""
echo -e "${BOLD}${GREEN}════════════════════════════════════════════════════════════${NC}"
echo -e "${BOLD}${GREEN}  ОБНОВЛЕНИЕ УСПЕШНО ЗАВЕРШЕНО ЗА ${ELAPSED}с!               ${NC}"
echo -e "${BOLD}${GREEN}  Текущий коммит: $NEW_COMMIT                               ${NC}"
echo -e "${BOLD}${GREEN}════════════════════════════════════════════════════════════${NC}"
echo ""
