"""
app/services/setup_service.py
Сервис проверки готовности базы данных и первоначальной инициализации (Zero-DB mode).
"""
import os
import sqlite3
import logging
from flask import current_app

logger = logging.getLogger(__name__)


def get_db_path(app=None):
    """Возвращает абсолютный путь к файлу SQLite базы данных reports.db."""
    if app is None:
        try:
            app = current_app
        except Exception:
            app = None

    if app and hasattr(app, 'config') and 'SQLALCHEMY_DATABASE_URI' in app.config:
        uri = app.config['SQLALCHEMY_DATABASE_URI']
        if uri.startswith('sqlite:///'):
            return os.path.abspath(uri.replace('sqlite:///', ''))

    from config import basedir
    return os.path.abspath(os.path.join(basedir, 'reports.db'))


def is_db_ready(app_or_path=None):
    """
    Проверяет, готова ли база данных к работе:
    1. Существует ли файл БД на диске
    2. Размер файла больше 1 КБ
    3. Созданы ли ключевые таблицы: users, report_templates, report_submissions
    4. Присутствует ли в таблице users хотя бы один администратор (role='admin')
    """
    if isinstance(app_or_path, str):
        db_path = app_or_path
    else:
        db_path = get_db_path(app_or_path)

    if not db_path or not os.path.exists(db_path):
        return False

    try:
        if os.path.getsize(db_path) < 1024:
            return False

        # Прямая быстрая проверка через sqlite3
        conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True, timeout=5)
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = {row[0] for row in cursor.fetchall()}

        required_tables = {'users', 'report_templates', 'report_submissions'}
        if not required_tables.issubset(tables):
            conn.close()
            return False

        # Проверяем наличие хотя бы одного администратора
        cursor.execute("SELECT COUNT(*) FROM users WHERE role='admin'")
        admin_count = cursor.fetchone()[0]
        conn.close()

        return admin_count > 0
    except Exception as e:
        logger.debug(f"is_db_ready check failed: {e}")
        return False


def init_clean_db(app=None):
    """
    Создает чистую начальную базу данных ЦОПП с нуля:
    - Создает все таблицы через SQLAlchemy
    - Создает учетную запись администратора (admin / admin123 или ADMIN_PASSWORD из .env)
    - Создает базовое подразделение
    """
    if app is None:
        app = current_app

    from app.extensions import db
    from app.models import User, Department, MaintenanceSetting

    with app.app_context():
        from app import models  # noqa: F401
        db.create_all()

        # Создаем администратора по умолчанию
        admin = User.query.filter_by(role='admin').first()
        if not admin:
            default_pass = os.environ.get('ADMIN_PASSWORD', 'admin123')
            admin = User(
                username='admin',
                role='admin',
                description='Главный администратор'
            )
            admin.set_password(default_pass)
            db.session.add(admin)

        # Создаем базовое подразделение
        if not Department.query.first():
            dept = Department(name='Основное подразделение')
            db.session.add(dept)

        # Инициализируем запись настроек техработ
        try:
            MaintenanceSetting.get_settings()
        except Exception:
            pass

        db.session.commit()
    return True
