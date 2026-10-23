"""
app/services/setup_service.py
Сервис проверки готовности базы данных и первоначальной инициализации (Zero-DB mode).
Поддерживает как SQLite, так и PostgreSQL.
"""
import os
import sqlite3
import logging
from flask import current_app

logger = logging.getLogger(__name__)


def get_db_uri(app=None):
    """Возвращает строку подключения к базе данных из конфигурации Flask."""
    if app is None:
        try:
            app = current_app
        except Exception:
            app = None

    if app and hasattr(app, 'config') and 'SQLALCHEMY_DATABASE_URI' in app.config:
        return app.config['SQLALCHEMY_DATABASE_URI']

    from config import basedir
    return 'sqlite:///' + os.path.abspath(os.path.join(basedir, 'reports.db'))


def get_db_path(app=None):
    """Возвращает абсолютный путь к файлу SQLite базы данных (для SQLite)."""
    uri = get_db_uri(app)
    if uri.startswith('sqlite:///'):
        return os.path.abspath(uri.replace('sqlite:///', ''))
    from config import basedir
    return os.path.abspath(os.path.join(basedir, 'reports.db'))


def is_db_ready(app_or_path=None):
    """
    Проверяет, готова ли база данных к работе (для SQLite или PostgreSQL):
    1. Проверяет доступность базы данных
    2. Созданы ли ключевые таблицы: users, report_templates, report_submissions
    3. Присутствует ли в таблице users хотя бы один администратор (role='admin')
    """
    if isinstance(app_or_path, str) and not app_or_path.startswith(('postgresql://', 'postgres://', 'sqlite:///')):
        # Передан прямой путь к файлу SQLite
        db_path = app_or_path
        if not db_path or not os.path.exists(db_path) or os.path.getsize(db_path) < 1024:
            return False
        try:
            conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True, timeout=5)
            cursor = conn.cursor()
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
            tables = {row[0] for row in cursor.fetchall()}
            required_tables = {'users', 'report_templates', 'report_submissions'}
            if not required_tables.issubset(tables):
                conn.close()
                return False
            cursor.execute("SELECT COUNT(*) FROM users WHERE role='admin'")
            admin_count = cursor.fetchone()[0]
            conn.close()
            return admin_count > 0
        except Exception as e:
            logger.debug(f"SQLite is_db_ready check failed: {e}")
            return False

    # Получаем URI из переданного объекта или текущего приложения
    db_uri = app_or_path if isinstance(app_or_path, str) else get_db_uri(app_or_path)

    # ── Проверка для PostgreSQL ───────────────────────────────────────────────
    if db_uri.startswith(('postgresql://', 'postgres://')):
        try:
            from sqlalchemy import create_engine, inspect, text
            engine = create_engine(db_uri, connect_args={'connect_timeout': 3})
            inspector = inspect(engine)
            tables = set(inspector.get_table_names())
            required = {'users', 'report_templates', 'report_submissions'}
            if not required.issubset(tables):
                engine.dispose()
                return False
            with engine.connect() as conn:
                cnt = conn.execute(text("SELECT COUNT(*) FROM users WHERE role='admin'")).scalar()
            engine.dispose()
            return cnt is not None and cnt > 0
        except Exception as e:
            logger.debug(f"PostgreSQL is_db_ready check failed: {e}")
            return False

    # ── Проверка для SQLite ───────────────────────────────────────────────────
    db_path = get_db_path(app_or_path)
    if not db_path or not os.path.exists(db_path):
        return False

    try:
        if os.path.getsize(db_path) < 1024:
            return False

        conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True, timeout=5)
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = {row[0] for row in cursor.fetchall()}

        required_tables = {'users', 'report_templates', 'report_submissions'}
        if not required_tables.issubset(tables):
            conn.close()
            return False

        cursor.execute("SELECT COUNT(*) FROM users WHERE role='admin'")
        admin_count = cursor.fetchone()[0]
        conn.close()

        return admin_count > 0
    except Exception as e:
        logger.debug(f"SQLite is_db_ready check failed: {e}")
        return False


def init_clean_db(app=None):
    """
    Создает чистую начальную базу данных ЦОПП с нуля:
    - Создает все таблицы через Alembic миграции (или SQLAlchemy)
    - Создает учетную запись администратора (admin / admin123 или ADMIN_PASSWORD из .env)
    - Создает базовое подразделение
    """
    if app is None:
        app = current_app

    from app.extensions import db
    from app.models import User, Department, MaintenanceSetting

    with app.app_context():
        # Применяем миграции для создания схемы
        try:
            from flask_migrate import upgrade
            upgrade()
        except Exception:
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
