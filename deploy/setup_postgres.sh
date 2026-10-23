#!/bin/bash
# ==============================================================================
# setup_postgres.sh — Автоматическая установка, тюнинг под 12 ГБ RAM
# и миграция проекта COPP-RAS с SQLite на PostgreSQL
#
# Для ОС: Ubuntu 24.04 / 26.04 LTS
# ==============================================================================

set -euo pipefail

# ─── ЦВЕТА И ВЫВОД ────────────────────────────────────────────────────────────
GREEN='\033[0;32m'; YELLOW='\033[1;33m'; RED='\033[0;31m'; CYAN='\033[0;36m'; BOLD='\033[1m'; NC='\033[0m'
info()    { echo -e "${GREEN}[OK]${NC}    $*"; }
warn()    { echo -e "${YELLOW}[WARN]${NC}  $*"; }
error()   { echo -e "${RED}[ERROR]${NC} $*"; }
section() { echo -e "\n${CYAN}════════════════════════════════════════════════════════════${NC}\n${CYAN}▶ $*${NC}\n${CYAN}════════════════════════════════════════════════════════════${NC}"; }

# ─── ПАРАМЕТРЫ ────────────────────────────────────────────────────────────────
APP_DIR="/var/www/copp-ras"
SERVICE_NAME="copp-ras"
DB_NAME="copp_ras_db"
DB_USER="copp_user"
APP_USER="www-data"

if [ "$EUID" -ne 0 ]; then
    error "Запустите скрипт с правами root: sudo bash deploy/setup_postgres.sh"
    exit 1
fi

echo -e "${BOLD}${CYAN}"
cat << "BANNER"
  ╔════════════════════════════════════════════════════════════╗
  ║    ЦОПП РК — Настройка PostgreSQL & Тюнинг под 12 GB RAM   ║
  ║    Переход с SQLite на PostgreSQL для COPP-RAS             ║
  ╚════════════════════════════════════════════════════════════╝
BANNER
echo -e "${NC}"

# ─── 1. УСТАНОВКА POSTGRESQL ──────────────────────────────────────────────────
section "1/5. Установка PostgreSQL и служебных пакетов"

export DEBIAN_FRONTEND=noninteractive
apt-get update -qq
apt-get install -y -qq postgresql postgresql-contrib libpq-dev >/dev/null
systemctl enable --now postgresql
info "PostgreSQL успешно установлен и запущен."

# ─── 2. СОЗДАНИЕ БАЗЫ ДАННЫХ И ПОЛЬЗОВАТЕЛЯ ───────────────────────────────────
section "2/5. Создание базы данных $DB_NAME и пользователя $DB_USER"

# Генерируем или читаем существующий пароль БД из .env
DB_PASS=""
if [ -f "$APP_DIR/.env" ]; then
    DB_PASS=$(grep -E '^PG_PASSWORD=' "$APP_DIR/.env" | cut -d '=' -f2- | tr -d ' "\r' || true)
fi

if [ -z "$DB_PASS" ]; then
    DB_PASS=$(python3 -c "import secrets; print(secrets.token_urlsafe(20))" 2>/dev/null || openssl rand -base64 16 | tr -dc 'a-zA-Z0-9')
fi

# Создаем роль и базу в Postgres
sudo -u postgres psql -tc "SELECT 1 FROM pg_roles WHERE rolname = '$DB_USER'" | grep -q 1 || \
    sudo -u postgres psql -c "CREATE USER $DB_USER WITH ENCRYPTED PASSWORD '$DB_PASS';"

# Обновляем пароль на случай если пользователь уже был
sudo -u postgres psql -c "ALTER USER $DB_USER WITH ENCRYPTED PASSWORD '$DB_PASS';"

sudo -u postgres psql -tc "SELECT 1 FROM pg_database WHERE datname = '$DB_NAME'" | grep -q 1 || \
    sudo -u postgres psql -c "CREATE DATABASE $DB_NAME OWNER $DB_USER;"

sudo -u postgres psql -c "GRANT ALL PRIVILEGES ON DATABASE $DB_NAME TO $DB_USER;"
sudo -u postgres psql -d "$DB_NAME" -c "GRANT ALL ON SCHEMA public TO $DB_USER;"

info "Пользователь $DB_USER и база $DB_NAME настроены."

# ─── 3. ТЮНИНГ ПОД 12 ГБ ОПЕРАТИВНОЙ ПАМЯТИ ──────────────────────────────────
section "3/5. Применение настроек производительности (12 GB RAM)"

PG_CONF_DIR=$(ls -d /etc/postgresql/*/main/conf.d 2>/dev/null | tail -n 1 || true)

if [ -z "$PG_CONF_DIR" ]; then
    PG_MAIN_CONF=$(ls /etc/postgresql/*/main/postgresql.conf 2>/dev/null | tail -n 1 || true)
    PG_CONF_DIR="$(dirname "$PG_MAIN_CONF")/conf.d"
    mkdir -p "$PG_CONF_DIR"
fi

cat > "$PG_CONF_DIR/copp_12gb_tuning.conf" << 'EOF'
# ==============================================================================
# COPP-RAS — Конфигурация PostgreSQL оптимизированная под 12 GB RAM и NVMe SSD
# ==============================================================================

# Память и кэш
shared_buffers = 3GB
effective_cache_size = 9GB
work_mem = 64MB
maintenance_work_mem = 1GB

# Дисковая подсистема (SSD / NVMe)
random_page_cost = 1.1
effective_io_concurrency = 200

# Журнал транзакций (WAL) и сброс контрольных точек
wal_buffers = 16MB
min_wal_size = 1GB
max_wal_size = 8GB
checkpoint_completion_target = 0.9

# Планировщик и соединения
default_statistics_target = 100
max_connections = 100
EOF

systemctl restart postgresql
sleep 1
info "Настройки применены: shared_buffers=3GB, effective_cache_size=9GB, work_mem=64MB."

# ─── 4. ОБНОВЛЕНИЕ .ENV И УСТАНОВКА СХЕМЫ ─────────────────────────────────────
section "4/5. Обновление .env и создание схемы через Flask-Migrate"

DATABASE_URL="postgresql://${DB_USER}:${DB_PASS}@localhost:5432/${DB_NAME}"

# Обновляем или добавляем DATABASE_URL в .env
if [ -f "$APP_DIR/.env" ]; then
    sed -i '/^DATABASE_URL=/d' "$APP_DIR/.env"
    sed -i '/^PG_PASSWORD=/d' "$APP_DIR/.env"
    echo "DATABASE_URL=$DATABASE_URL" >> "$APP_DIR/.env"
    echo "PG_PASSWORD=$DB_PASS" >> "$APP_DIR/.env"
else
    cat > "$APP_DIR/.env" << EOF
DATABASE_URL=$DATABASE_URL
PG_PASSWORD=$DB_PASS
EOF
fi

chown "$APP_USER":"$APP_USER" "$APP_DIR/.env"
chmod 600 "$APP_DIR/.env"

# Установка драйверов PostgreSQL в venv (psycopg v3 и psycopg2)
info "Устанавливаю драйверы PostgreSQL (psycopg, psycopg2) в venv..."
"$APP_DIR/venv/bin/pip" install "psycopg[binary]" psycopg2-binary --quiet

# Создание всех таблиц в PostgreSQL через Alembic
info "Развертываю структуру таблиц в PostgreSQL..."
cd "$APP_DIR"
export FLASK_APP="wsgi:app"
"$APP_DIR/venv/bin/flask" db upgrade
info "Все таблицы и индексы успешно созданы в PostgreSQL."

# ─── 5. ПЕРЕНОС ДАННЫХ ИЗ SQLITE ──────────────────────────────────────────────
section "5/5. Перенос накопленных данных из SQLite в PostgreSQL"

if [ -f "$APP_DIR/reports.db" ] && [ -s "$APP_DIR/reports.db" ]; then
    info "Найден файл рабочей базы данных reports.db. Запускаю перенос строк..."
    "$APP_DIR/venv/bin/python" "$APP_DIR/scripts/migrate_sqlite_to_pg.py" "$APP_DIR/reports.db" "$DATABASE_URL"
    info "Перенос данных завершен."
else
    warn "Файл reports.db пуст или отсутствует. PostgreSQL инициализирован чистым."
fi

# Перезапуск сервиса приложения
systemctl restart "$SERVICE_NAME"
sleep 2

if systemctl is-active --quiet "$SERVICE_NAME"; then
    info "Сервис $SERVICE_NAME успешно переключен на PostgreSQL и работает!"
else
    error "Сервис не смог перезапуститься! Проверьте логи: sudo journalctl -u $SERVICE_NAME -n 25"
    exit 1
fi

echo ""
echo -e "${BOLD}${GREEN}════════════════════════════════════════════════════════════${NC}"
echo -e "${BOLD}${GREEN}  ПЕРЕХОД НА POSTGRESQL (12 GB RAM) УСПЕШНО ЗАВЕРШЁН!       ${NC}"
echo -e "${BOLD}${GREEN}════════════════════════════════════════════════════════════${NC}"
echo ""
echo -e "  Параметры СУБД:"
echo -e "    ► База данных:    ${CYAN}$DB_NAME${NC}"
echo -e "    ► Пользователь:   ${CYAN}$DB_USER${NC}"
echo -e "    ► Выделено памяти:${CYAN}12 GB (shared_buffers: 3 GB, cache: 9 GB)${NC}"
echo ""
