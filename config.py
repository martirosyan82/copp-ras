import os
from datetime import timedelta
import logging
basedir = os.path.abspath(os.path.dirname(__file__))
# Загрузка переменных окружения из .env (если установлен python-dotenv)
try:
    from dotenv import load_dotenv
    load_dotenv(os.path.join(basedir, '.env'))
except ImportError:
    pass


class Config:
    """Базовая конфигурация. Общие настройки для всех окружений."""

    # ── Secret Key ──────────────────────────────────────────────────────────
    SECRET_KEY = os.environ.get('SECRET_KEY')
    if not SECRET_KEY:
        secret_file = os.path.join(basedir, '.secret_key')
        try:
            with open(secret_file, 'r', encoding='utf-8') as f:
                SECRET_KEY = f.read().strip()
        except FileNotFoundError:
            SECRET_KEY = os.urandom(24).hex()
            try:
                with open(secret_file, 'w', encoding='utf-8') as f:
                    f.write(SECRET_KEY)
            except IOError:
                pass
            logging.warning("SECRET_KEY not set in env. Generated and saved to .secret_key")

    # ── Database ─────────────────────────────────────────────────────────────
    raw_db_url = os.environ.get('DATABASE_URL')
    if raw_db_url and raw_db_url.startswith('postgres://'):
        raw_db_url = raw_db_url.replace('postgres://', 'postgresql://', 1)

    SQLALCHEMY_DATABASE_URI = (
        raw_db_url
        or 'sqlite:///' + os.path.join(basedir, 'reports.db')
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # Пул соединений для PostgreSQL и автопроверка живых соединений
    SQLALCHEMY_ENGINE_OPTIONS = {
        'pool_pre_ping': True,
        'pool_recycle': 1800,
    }
    if raw_db_url and 'sqlite' not in raw_db_url:
        SQLALCHEMY_ENGINE_OPTIONS.update({
            'pool_size': 15,
            'max_overflow': 25,
            'pool_timeout': 30,
        })

    # ── Session & Cookie Security ─────────────────────────────────────────────
    PERMANENT_SESSION_LIFETIME = timedelta(hours=24)
    SESSION_REFRESH_EACH_REQUEST = False
    # По умолчанию false, чтобы куки и CSRF-токены работали как по HTTP (по прямому IP), так и по HTTPS
    SESSION_COOKIE_SECURE = os.environ.get('SESSION_COOKIE_SECURE', 'false').lower() in ('true', '1', 'yes')
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = 'Lax'
    REMEMBER_COOKIE_SECURE = os.environ.get('REMEMBER_COOKIE_SECURE', 'false').lower() in ('true', '1', 'yes')
    REMEMBER_COOKIE_HTTPONLY = True

    # ── CSRF Protection ───────────────────────────────────────────────────────
    # None — токен действует всё время жизни сессии (24 часа), а не сгорает через 1 час (3600с)
    WTF_CSRF_TIME_LIMIT = None

    # ── Features ──────────────────────────────────────────────────────────────
    ENABLE_CHARTS = True


class DevelopmentConfig(Config):
    """
    Конфигурация для локальной разработки.
    Отключает HTTPS-куки, включает debug-режим Flask.

    Использование:
        FLASK_CONFIG=development python run.py
    """
    DEBUG = True
    SESSION_COOKIE_SECURE = False
    REMEMBER_COOKIE_SECURE = False
    # Отдельная БД для разработки (не трогает продакшн)
    SQLALCHEMY_DATABASE_URI = (
        os.environ.get('DEV_DATABASE_URL')
        or 'sqlite:///' + os.path.join(basedir, 'reports.db')
    )


class ProductionConfig(Config):
    """
    Конфигурация для продакшн-сервера.
    Все настройки безопасности включены.

    Использование:
        FLASK_CONFIG=production gunicorn wsgi:app
    """
    DEBUG = False


class TestingConfig(Config):
    """
    Конфигурация для автотестов.
    Использует in-memory SQLite для скорости.

    Использование:
        pytest
    """
    TESTING = True
    DEBUG = True
    SESSION_COOKIE_SECURE = False
    REMEMBER_COOKIE_SECURE = False
    SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'
    WTF_CSRF_ENABLED = False  # Отключаем CSRF в тестах


# Словарь для выбора конфига через переменную окружения FLASK_CONFIG
config_map = {
    'development': DevelopmentConfig,
    'production':  ProductionConfig,
    'testing':     TestingConfig,
    'default':     DevelopmentConfig,
}
