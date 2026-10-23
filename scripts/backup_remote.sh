#!/bin/bash

# ==============================================================================
# Скрипт автоматического резервного копирования на удаленный сервер через SSH
# ==============================================================================

# Настройки путей
PROJECT_DIR="/var/www/copp-ras"
BACKUP_DIR="/home/ras.copp/copp_backups"
DB_FILE="reports.db"
UPLOADS_DIR="app/uploads"

# Настройки удаленного сервера
REMOTE_USER="git"
REMOTE_HOST="178.212.14.44"
REMOTE_PORT="22"
REMOTE_DIR="/home/git/backups/copp-ras"

# Формирование имени файла
DATE=$(date +"%d-%m-%Y-%H-%M")
ARCHIVE_NAME="copp-ras-$DATE.zip"
ARCHIVE_PATH="$BACKUP_DIR/$ARCHIVE_NAME"

mkdir -p "$BACKUP_DIR"

# Установка zip, если его нет
if ! command -v zip &> /dev/null; then
    echo "[$(date +"%Y-%m-%d %H:%M:%S")] Утилита zip не найдена. Попытка установки..."
    sudo apt-get update -qq && sudo apt-get install -y zip -qq
fi

# Переход в директорию проекта
cd "$PROJECT_DIR" || exit 1

echo "[$(date +"%Y-%m-%d %H:%M:%S")] Начинаем создание архива $ARCHIVE_NAME..."

# Создаем архив (добавляем БД и загрузки)
zip -q "$ARCHIVE_PATH" "$DB_FILE"
zip -q -r "$ARCHIVE_PATH" "$UPLOADS_DIR"

if [ $? -eq 0 ]; then
    echo "[$(date +"%Y-%m-%d %H:%M:%S")] Архив успешно создан. Отправка на удаленный сервер..."
    
    # Отправка файла через SCP.
    scp -P "$REMOTE_PORT" "$ARCHIVE_PATH" "${REMOTE_USER}@${REMOTE_HOST}:${REMOTE_DIR}/"
    
    if [ $? -eq 0 ]; then
        echo "[$(date +"%Y-%m-%d %H:%M:%S")] Бекап успешно отправлен на $REMOTE_HOST!"
        # Удаляем локальный архив
        rm "$ARCHIVE_PATH"
        echo "[$(date +"%Y-%m-%d %H:%M:%S")] Локальный архив удален."
    else
        echo "[$(date +"%Y-%m-%d %H:%M:%S")] ОШИБКА: Не удалось отправить файл на удаленный сервер."
        exit 1
    fi
else
    echo "[$(date +"%Y-%m-%d %H:%M:%S")] ОШИБКА: Не удалось создать локальный архив."
    exit 1
fi
