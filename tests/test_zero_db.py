import os
import sys
import tempfile
import zipfile
import sqlite3

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from app import create_app
from app.services.setup_service import is_db_ready, init_clean_db
from config import Config


class TempDBConfig(Config):
    TESTING = True
    WTF_CSRF_ENABLED = False


def test_zero_db_redirection_and_init():
    # Создаем временный каталог для имитации сервера без БД
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_db_path = os.path.join(temp_dir, 'reports.db')
        
        class TestZeroConfig(TempDBConfig):
            SQLALCHEMY_DATABASE_URI = f'sqlite:///{temp_db_path}'

        # 1. Проверяем, что базы нет
        assert not is_db_ready(temp_db_path)

        app = create_app(TestZeroConfig)
        client = app.test_client()

        # 2. Любой запрос должен перенаправлять на /setup/
        res = client.get('/', follow_redirects=False)
        assert res.status_code == 302
        assert '/setup/' in res.headers['Location']

        # 3. Страница /setup/ отдает 200 OK
        setup_page = client.get('/setup/')
        assert setup_page.status_code == 200
        assert 'ЦОПП' in setup_page.get_data(as_text=True)
        assert 'Восстановить из бэкапа' in setup_page.get_data(as_text=True)

        # 4. Выполняем инициализацию чистой БД через POST /setup/init-clean
        init_res = client.post('/setup/init-clean', headers={'X-Requested-With': 'XMLHttpRequest'})
        assert init_res.status_code == 200
        data = init_res.get_json()
        assert data['success'] is True

        # 5. Теперь is_db_ready() должна вернуть True
        assert is_db_ready(temp_db_path)

        # 6. Теперь / не редиректит на /setup/
        res_after = client.get('/', follow_redirects=False)
        assert res_after.status_code != 302 or '/setup/' not in res_after.headers.get('Location', '')

        with app.app_context():
            from app.extensions import db
            db.session.remove()
            db.engine.dispose()


def test_zero_db_zip_upload():
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_db_path = os.path.join(temp_dir, 'reports.db')
        
        class TestZeroConfig(TempDBConfig):
            SQLALCHEMY_DATABASE_URI = f'sqlite:///{temp_db_path}'

        app = create_app(TestZeroConfig)
        client = app.test_client()

        # Создаем тестовый zip-архив с базой данных
        test_source_db = os.path.join(temp_dir, 'source.db')
        with app.app_context():
            from app.extensions import db
            from app.models import User
            # Временно переключаем URI для создания валидной БД источника
            db.create_all()
            admin = User(username='admin_test', role='admin')
            admin.set_password('secret123')
            db.session.add(admin)
            db.session.commit()
            db.session.remove()
            db.engine.dispose()

        # Удаляем созданную БД, чтобы имитировать чистый сервер
        if os.path.exists(temp_db_path):
            os.remove(temp_db_path)
        assert not is_db_ready(temp_db_path)

        # Создаем zip с reports.db
        dummy_db = os.path.join(temp_dir, 'dummy.db')
        conn = sqlite3.connect(dummy_db)
        conn.execute("CREATE TABLE users (id INTEGER PRIMARY KEY, username TEXT, role TEXT, password_hash TEXT)")
        conn.execute("CREATE TABLE report_templates (id INTEGER PRIMARY KEY, name TEXT)")
        conn.execute("CREATE TABLE report_submissions (id INTEGER PRIMARY KEY, status TEXT)")
        conn.execute("INSERT INTO users (username, role) VALUES ('admin', 'admin')")
        conn.commit()
        conn.close()

        zip_path = os.path.join(temp_dir, 'backup.zip')
        with zipfile.ZipFile(zip_path, 'w') as zf:
            zf.write(dummy_db, 'reports.db')

        # Загружаем ZIP через API /setup/upload
        with open(zip_path, 'rb') as f:
            upload_res = client.post(
                '/setup/upload',
                data={'backup_file': (f, 'backup.zip')},
                content_type='multipart/form-data',
                headers={'X-Requested-With': 'XMLHttpRequest'}
            )

        assert upload_res.status_code == 200
        res_data = upload_res.get_json()
        assert res_data['success'] is True
        assert is_db_ready(temp_db_path)

        with app.app_context():
            from app.extensions import db
            db.session.remove()
            db.engine.dispose()


if __name__ == '__main__':
    print("Testing test_zero_db_redirection_and_init()...")
    test_zero_db_redirection_and_init()
    print("OK!")
    print("Testing test_zero_db_zip_upload()...")
    test_zero_db_zip_upload()
    print("OK!")
    print("ALL ZERO-DB TESTS PASSED!")
