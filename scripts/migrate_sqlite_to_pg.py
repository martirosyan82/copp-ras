"""
scripts/migrate_sqlite_to_pg.py
Скрипт безопасного переноса данных из SQLite (reports.db) в PostgreSQL.

Использование:
    python scripts/migrate_sqlite_to_pg.py [путь_к_sqlite_db] [postgres_url]

Если аргументы не указаны, скрипт берет:
- SQLite: basedir/reports.db
- PostgreSQL: DATABASE_URL из файла .env
"""
import os
import sys
import json
import sqlite3
from datetime import datetime

# Подключаем корень проекта к sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from config import basedir
from sqlalchemy import create_engine, inspect, text, MetaData, Table

# Порядок таблиц с учетом Foreign Key зависимостей
TABLE_ORDER = [
    'departments',
    'users',
    'maintenance_settings',
    'dictionaries',
    'uploaded_files',
    'report_templates',
    'department_templates',
    'user_template_access',
    'report_attachments',
    'report_submissions',
    'report_drafts',
    'manual_rows',
    'announcements',
    'action_logs',
    'background_tasks',
]

# Колонки, содержащие JSON данные
JSON_COLUMNS = {
    'dictionaries': ['items'],
    'report_templates': ['schema', 'period_data'],
    'report_submissions': ['data'],
    'report_drafts': ['data'],
    'manual_rows': ['data'],
    'announcements': ['target_departments', 'target_groups'],
}

# Колонки с булевыми значениями (в SQLite 0/1, в Postgres True/False)
BOOLEAN_COLUMNS = {
    'maintenance_settings': ['is_active'],
    'report_templates': ['is_published', 'is_completed', 'is_archived', 'is_template'],
    'report_submissions': ['is_revision'],
    'announcements': ['is_active'],
}

# Колонки с датами/временем
DATETIME_COLUMNS = {
    'maintenance_settings': ['start_at', 'end_at', 'updated_at'],
    'dictionaries': ['created_at'],
    'uploaded_files': ['upload_date'],
    'action_logs': ['timestamp'],
    'announcements': ['created_at', 'updated_at'],
    'background_tasks': ['created_at'],
    'manual_rows': ['created_at', 'updated_at'],
    'report_drafts': ['updated_at'],
    'report_submissions': ['submitted_at', 'returned_at'],
    'report_templates': ['deadline'],
}


def parse_val(table_name, col_name, val):
    """Преобразует строковые и числовые типы SQLite в нативные типы для PostgreSQL."""
    if val is None:
        return None

    # Обработка JSON
    if col_name in JSON_COLUMNS.get(table_name, []):
        if isinstance(val, str):
            try:
                return json.loads(val)
            except Exception:
                return val
        return val

    # Обработка Boolean
    if col_name in BOOLEAN_COLUMNS.get(table_name, []):
        return bool(val)

    # Обработка DateTime / Date
    if col_name in DATETIME_COLUMNS.get(table_name, []):
        if isinstance(val, str):
            for fmt in ('%Y-%m-%d %H:%M:%S.%f', '%Y-%m-%d %H:%M:%S', '%Y-%m-%d'):
                try:
                    dt = datetime.strptime(val, fmt)
                    if col_name == 'deadline':
                        return dt.date()
                    return dt
                except ValueError:
                    pass
        return val

    return val


def migrate_data(sqlite_path=None, pg_url=None):
    """
    Программная функция переноса данных из SQLite в PostgreSQL.
    Может вызываться как из мастера /setup/upload, так и из CLI.
    """
    if not sqlite_path:
        sqlite_path = os.path.join(basedir, 'reports.db')

    if not pg_url:
        env_file = os.path.join(basedir, '.env')
        if os.path.exists(env_file):
            with open(env_file, 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    if line.startswith('DATABASE_URL='):
                        pg_url = line.split('DATABASE_URL=', 1)[1].strip(' "\'')
                        break

    if not pg_url or not pg_url.startswith(('postgresql://', 'postgres://')):
        raise ValueError("Не указан валидный DATABASE_URL для PostgreSQL")

    if pg_url.startswith('postgres://'):
        pg_url = pg_url.replace('postgres://', 'postgresql://', 1)

    if not os.path.exists(sqlite_path):
        raise FileNotFoundError(f"Исходный файл SQLite не найден: {sqlite_path}")

    print("=" * 65)
    print("  МИГРАЦИЯ ДАННЫХ COPP-RAS: SQLite -> PostgreSQL")
    print("=" * 65)
    print(f"Источник (SQLite):    {sqlite_path} ({os.path.getsize(sqlite_path) / (1024*1024):.2f} МБ)")
    masked_pg = pg_url.split('@')[-1] if '@' in pg_url else pg_url
    print(f"Приёмник (PostgreSQL): ...@{masked_pg}")
    print("=" * 65)

    # 1. Подключение к SQLite
    sqlite_conn = sqlite3.connect(sqlite_path)
    sqlite_conn.row_factory = sqlite3.Row
    sqlite_tables = {
        r[0] for r in sqlite_conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
    }

    # 2. Подключение к PostgreSQL
    pg_engine = create_engine(pg_url)
    inspector = inspect(pg_engine)
    pg_tables = set(inspector.get_table_names())

    # Проверка наличия схемы в PostgreSQL
    if not {'users', 'report_templates', 'report_submissions'}.issubset(pg_tables):
        print("\n[ВНИМАНИЕ] Таблицы в PostgreSQL ещё не созданы!")
        print("Выполняю создание схемы через Flask-Migrate (flask db upgrade)...")
        from flask_migrate import upgrade
        from app import create_app
        app = create_app()
        with app.app_context():
            upgrade()
        inspector = inspect(pg_engine)
        pg_tables = set(inspector.get_table_names())
        print("[OK] Схема PostgreSQL успешно создана.")

    # Автоматическое расширение длины колонок для существующих таблиц в PostgreSQL
    try:
        with pg_engine.begin() as conn:
            conn.execute(text("ALTER TABLE report_templates ALTER COLUMN name TYPE VARCHAR(1024);"))
            conn.execute(text("ALTER TABLE report_templates ALTER COLUMN short_name TYPE VARCHAR(256);"))
            conn.execute(text("ALTER TABLE background_tasks ALTER COLUMN name TYPE VARCHAR(512);"))
    except Exception:
        pass

    metadata = MetaData()
    metadata.reflect(bind=pg_engine)

    # Каскадная очистка всех таблиц перед переносом
    try:
        with pg_engine.begin() as clean_conn:
            existing_tables = [f'"{t}"' for t in reversed(TABLE_ORDER) if t in pg_tables]
            if existing_tables:
                clean_conn.execute(text(f"TRUNCATE TABLE {', '.join(existing_tables)} CASCADE;"))
    except Exception as e:
        print(f"  [ИНФО] Очистка таблиц через DELETE: {e}")

    total_records = 0

    # 3. Перенос данных таблица за таблицей
    print("\nНачинаю перенос данных:\n")

    with pg_engine.begin() as pg_conn:
        # Отключаем проверку внешних ключей на время массовой вставки
        try:
            pg_conn.execute(text("SET session_replication_role = 'replica';"))
        except Exception:
            pass

        for table_name in TABLE_ORDER:
            if table_name not in sqlite_tables or table_name not in pg_tables:
                continue

            target_table = Table(table_name, metadata, autoload_with=pg_engine)
            target_cols = {c.name for c in target_table.columns}

            # Считываем строки из SQLite
            rows = sqlite_conn.execute(f"SELECT * FROM {table_name}").fetchall()
            row_count = len(rows)

            if row_count == 0:
                print(f"  > {table_name:<24} 0 строк (пусто)")
                continue

            # Подготавливаем данные
            prepared_records = []
            for r in rows:
                rec = {}
                for k in r.keys():
                    if k in target_cols:
                        rec[k] = parse_val(table_name, k, r[k])
                prepared_records.append(rec)

            # Пакетная вставка
            pg_conn.execute(target_table.insert(), prepared_records)
            total_records += row_count
            print(f"  [OK] {table_name:<22} перенесено: {row_count:>5} строк")

        # Включаем проверку внешних ключей обратно
        try:
            pg_conn.execute(text("SET session_replication_role = 'origin';"))
        except Exception:
            pass

        # 4. Обновление sequence (автоинкрементов) для таблиц с полем id
        print("\nОбновление системных автоинкрементов (Sequences) в PostgreSQL...")
        for table_name in TABLE_ORDER:
            if table_name in pg_tables:
                target_table = Table(table_name, metadata, autoload_with=pg_engine)
                if 'id' in [c.name for c in target_table.columns]:
                    try:
                        seq_sql = text(f"""
                            SELECT setval(
                                pg_get_serial_sequence('{table_name}', 'id'),
                                coalesce(max(id), 1)
                            ) FROM {table_name};
                        """)
                        pg_conn.execute(seq_sql)
                    except Exception:
                        pass

    sqlite_conn.close()
    pg_engine.dispose()

    print("\n" + "=" * 65)
    print(f"  УСПЕШНО ПЕРЕНЕСЕНО ЗАПИСЕЙ: {total_records}")
    print("=" * 65)
    return total_records


def migrate():
    sqlite_path = sys.argv[1] if len(sys.argv) > 1 else None
    pg_url = sys.argv[2] if len(sys.argv) > 2 else None
    try:
        migrate_data(sqlite_path, pg_url)
    except Exception as e:
        print(f"[ОШИБКА] {e}")
        sys.exit(1)


if __name__ == '__main__':
    migrate()
