"""
app/setup/routes.py
Маршруты мастера первоначальной настройки Zero-DB (ЦОПП РК).
Позволяет развернуть систему с нуля без предварительно созданной БД:
- либо через загрузку полного ZIP-бэкапа (БД + uploads)
- либо через загрузку одного файла .sqlite / .db
- либо через инициализацию чистой БД с администратором по умолчанию
"""
import os
import shutil
import tempfile
import zipfile
import logging
from flask import render_template, request, redirect, url_for, jsonify, current_app
from app.setup import bp
from app.services.setup_service import is_db_ready, init_clean_db, get_db_path
from app.extensions import db
from config import basedir

logger = logging.getLogger(__name__)


@bp.route('/', methods=['GET'])
def index():
    """
    Страница первоначальной настройки системы.
    Если база данных уже инициализирована и готова к работе,
    перенаправляет на страницу авторизации или главную.
    """
    if is_db_ready():
        return redirect(url_for('auth.login'))
    return render_template('setup.html')


@bp.route('/upload', methods=['POST'])
def upload():
    """
    Принимает файл .sqlite / .db (только база данных)
    или .zip (полный архив с базой данных и загруженными файлами uploads).
    """
    if is_db_ready():
        return jsonify({'success': False, 'message': 'База данных уже настроена и активна'}), 400

    if 'backup_file' not in request.files:
        return jsonify({'success': False, 'message': 'Файл не выбран'}), 400

    file = request.files['backup_file']
    filename = file.filename or ''
    if not filename:
        return jsonify({'success': False, 'message': 'Файл не выбран'}), 400

    db_path = get_db_path(current_app)
    lower_name = filename.lower()

    # ── 1. ВАРИАНТ: Загружен файл SQLite (.db / .sqlite / .sqlite3) ──────────
    if lower_name.endswith(('.sqlite', '.db', '.sqlite3')):
        temp_db_path = f"{db_path}.setup.temp"
        try:
            # Освобождаем сессию и пул соединений SQLAlchemy
            try:
                db.session.remove()
                db.engine.dispose()
            except Exception:
                pass

            file.save(temp_db_path)

            # Проверка сигнатуры SQLite
            with open(temp_db_path, 'rb') as f:
                header = f.read(16)
            if not header.startswith(b'SQLite format 3\x00'):
                if os.path.exists(temp_db_path):
                    os.remove(temp_db_path)
                return jsonify({'success': False, 'message': 'Загруженный файл не является корректной базой данных SQLite 3'}), 400

            # Заменяем рабочий файл базы данных
            shutil.move(temp_db_path, db_path)

            # Удаляем старые WAL/SHM журналы
            for extra in (f"{db_path}-wal", f"{db_path}-shm"):
                if os.path.exists(extra):
                    try:
                        os.remove(extra)
                    except OSError:
                        pass

            # Выставляем права для веб-сервера
            try:
                os.chmod(db_path, 0o664)
            except Exception:
                pass

            # Применяем миграцию недостающих колонок если нужно
            _apply_migrations(current_app)

            # Если приложение работает на PostgreSQL, синхронизируем данные в PostgreSQL
            db_uri = current_app.config.get('SQLALCHEMY_DATABASE_URI', '')
            if db_uri.startswith(('postgresql://', 'postgres://')):
                try:
                    from scripts.migrate_sqlite_to_pg import migrate_data
                    migrate_data(db_path, db_uri)
                except Exception as e:
                    logger.exception("Ошибка переноса в PostgreSQL")
                    return jsonify({'success': False, 'message': f'Ошибка переноса в PostgreSQL: {e}'}), 500

            if not is_db_ready():
                return jsonify({
                    'success': False,
                    'message': 'Файл загружен, но в базе отсутствуют обязательные таблицы или учетная запись администратора'
                }), 400

            return jsonify({
                'success': True,
                'message': 'База данных успешно установлена!',
                'redirect': url_for('auth.login')
            })
        except Exception as e:
            logger.exception("Ошибка при установке SQLite файла")
            if os.path.exists(temp_db_path):
                try:
                    os.remove(temp_db_path)
                except OSError:
                    pass
            return jsonify({'success': False, 'message': f'Ошибка при сохранении базы: {str(e)}'}), 500

    # ── 2. ВАРИАНТ: Загружен ZIP-архив бэкапа ────────────────────────────────
    elif lower_name.endswith('.zip'):
        temp_zip_fd, temp_zip_path = tempfile.mkstemp(suffix='.zip')
        os.close(temp_zip_fd)

        try:
            file.save(temp_zip_path)

            if not zipfile.is_zipfile(temp_zip_path):
                if os.path.exists(temp_zip_path):
                    os.remove(temp_zip_path)
                return jsonify({'success': False, 'message': 'Загруженный файл не является корректным ZIP-архивом'}), 400

            # Освобождаем сессию SQLAlchemy
            try:
                db.session.remove()
                db.engine.dispose()
            except Exception:
                pass

            uploads_dir = os.path.join(basedir, 'app', 'uploads')
            static_uploads_dir = os.path.join(basedir, 'app', 'static', 'uploads')
            os.makedirs(uploads_dir, exist_ok=True)
            os.makedirs(static_uploads_dir, exist_ok=True)

            with zipfile.ZipFile(temp_zip_path, 'r') as zip_ref:
                file_list = zip_ref.namelist()

                # Поиск файла БД в архиве
                db_filename_in_zip = None
                preferred_names = ('reports.db', 'coppdb.sqlite', 'database.sqlite', 'app/reports.db')
                for name in preferred_names:
                    if name in file_list:
                        db_filename_in_zip = name
                        break

                if not db_filename_in_zip:
                    for name in file_list:
                        lower = name.lower()
                        if lower.endswith(('.sqlite', '.db', '.sqlite3')) and not lower.endswith('-wal') and not lower.endswith('-shm'):
                            db_filename_in_zip = name
                            break

                if not db_filename_in_zip:
                    return jsonify({'success': False, 'message': 'В ZIP-архиве не найден файл базы данных (.db / .sqlite)'}), 400

                # Извлекаем и проверяем БД
                temp_db_extract = f"{db_path}.zip_extract.temp"
                with zip_ref.open(db_filename_in_zip) as src, open(temp_db_extract, 'wb') as dst:
                    shutil.copyfileobj(src, dst, length=64 * 1024)

                with open(temp_db_extract, 'rb') as f:
                    header = f.read(16)
                if not header.startswith(b'SQLite format 3\x00'):
                    os.remove(temp_db_extract)
                    return jsonify({'success': False, 'message': 'Файл базы данных внутри архива поврежден'}), 400

                shutil.move(temp_db_extract, db_path)

                # Удаляем старые WAL/SHM
                for extra in (f"{db_path}-wal", f"{db_path}-shm"):
                    if os.path.exists(extra):
                        try:
                            os.remove(extra)
                        except OSError:
                            pass

                try:
                    os.chmod(db_path, 0o664)
                except Exception:
                    pass

                # Извлекаем загруженные файлы (uploads)
                for member in file_list:
                    if member.endswith('/'):
                        continue
                    # Защита от Path Traversal
                    norm = os.path.normpath(member)
                    if norm.startswith('..') or os.path.isabs(norm):
                        continue

                    # Определяем целевую папку
                    target_file = None
                    if 'app/uploads/' in member:
                        rel = member.split('app/uploads/', 1)[1]
                        if rel and '..' not in rel:
                            target_file = os.path.join(uploads_dir, rel)
                    elif 'uploads/' in member:
                        rel = member.split('uploads/', 1)[1]
                        if rel and '..' not in rel:
                            target_file = os.path.join(uploads_dir, rel)
                    elif 'app/static/uploads/' in member:
                        rel = member.split('app/static/uploads/', 1)[1]
                        if rel and '..' not in rel:
                            target_file = os.path.join(static_uploads_dir, rel)

                    if target_file:
                        os.makedirs(os.path.dirname(target_file), exist_ok=True)
                        with zip_ref.open(member) as src, open(target_file, 'wb') as dst:
                            shutil.copyfileobj(src, dst, length=64 * 1024)

            # Применяем миграции недостающих колонок если необходимо
            _apply_migrations(current_app)

            # Если приложение работает на PostgreSQL, синхронизируем данные в PostgreSQL
            db_uri = current_app.config.get('SQLALCHEMY_DATABASE_URI', '')
            if db_uri.startswith(('postgresql://', 'postgres://')):
                try:
                    from scripts.migrate_sqlite_to_pg import migrate_data
                    migrate_data(db_path, db_uri)
                except Exception as e:
                    logger.exception("Ошибка переноса в PostgreSQL")
                    return jsonify({'success': False, 'message': f'Ошибка переноса в PostgreSQL: {e}'}), 500

            if not is_db_ready():
                return jsonify({
                    'success': False,
                    'message': 'Архив распакован, но база данных не содержит обязательных таблиц или учетной записи администратора'
                }), 400

            return jsonify({
                'success': True,
                'message': 'Полный бэкап успешно развернут!',
                'redirect': url_for('auth.login')
            })

        except Exception as e:
            logger.exception("Ошибка при распаковке ZIP архива")
            return jsonify({'success': False, 'message': f'Ошибка при распаковке архива: {str(e)}'}), 500
        finally:
            if os.path.exists(temp_zip_path):
                try:
                    os.remove(temp_zip_path)
                except OSError:
                    pass

    return jsonify({'success': False, 'message': 'Поддерживаются только форматы .zip или .db / .sqlite'}), 400


@bp.route('/init-clean', methods=['POST'])
def init_clean():
    """
    Развертывает чистую начальную базу данных ЦОПП с нуля:
    - Создает все таблицы
    - Создает дефолтного администратора admin / admin123
    """
    if is_db_ready():
        return jsonify({'success': False, 'message': 'База данных уже настроена'}), 400

    try:
        try:
            db.session.remove()
            db.engine.dispose()
        except Exception:
            pass

        init_clean_db(current_app)

        db_path = get_db_path(current_app)
        try:
            os.chmod(db_path, 0o664)
        except Exception:
            pass

        return jsonify({
            'success': True,
            'message': 'Чистая база данных успешно создана!',
            'redirect': url_for('auth.login')
        })
    except Exception as e:
        logger.exception("Ошибка при инициализации чистой БД")
        return jsonify({'success': False, 'message': f'Ошибка инициализации: {str(e)}'}), 500


def _apply_migrations(app):
    """Применяет миграцию схемы для добавления новых колонок в существующую БД."""
    try:
        with app.app_context():
            from sqlalchemy import inspect, text
            inspector = inspect(db.engine)
            if 'users' in inspector.get_table_names():
                cols = [c['name'] for c in inspector.get_columns('users')]
                if 'subgroup' not in cols:
                    db.session.execute(text("ALTER TABLE users ADD COLUMN subgroup VARCHAR(100)"))
                    db.session.commit()
    except Exception as e:
        logger.debug(f"Миграция колонок пропущена: {e}")
