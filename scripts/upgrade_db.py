"""
upgrade_db.py вЂ” РЎРєСЂРёРїС‚ Р±РµР·РѕРїР°СЃРЅРѕР№ РјРёРіСЂР°С†РёРё Р±Р°Р·С‹ РґР°РЅРЅС‹С….
Р—Р°РїСѓСЃРє РІСЂСѓС‡РЅСѓСЋ:
    python upgrade_db.py

Р§С‚Рѕ РґРµР»Р°РµС‚:
1. РЎРѕР·РґР°РµС‚ РЅРµРґРѕСЃС‚Р°СЋС‰РёРµ С‚Р°Р±Р»РёС†С‹ (departments, department_templates, background_tasks Рё РґСЂ.)
2. РџСЂРѕРІРµСЂСЏРµС‚ РЅР°Р»РёС‡РёРµ РІСЃРµС… РєРѕР»РѕРЅРѕРє РІ СЃСѓС‰РµСЃС‚РІСѓСЋС‰РёС… С‚Р°Р±Р»РёС†Р°С… С‡РµСЂРµР· PRAGMA table_info.
3. Р”РѕР±Р°РІР»СЏРµС‚ РѕС‚СЃСѓС‚СЃС‚РІСѓСЋС‰РёРµ РєРѕР»РѕРЅРєРё (department_id, ip_address, is_template Рё РґСЂ.) Р±РµР· РїРѕС‚РµСЂРё РґР°РЅРЅС‹С….
4. РџСЂРѕРІРµСЂСЏРµС‚ СЂР°Р±РѕС‚РѕСЃРїРѕСЃРѕР±РЅРѕСЃС‚СЊ РІС‹Р±РѕСЂРєРё РїРѕР»СЊР·РѕРІР°С‚РµР»РµР№.
"""
import os
import sys
import sqlite3
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from config import basedir

def get_columns(cursor, table_name):
    """Р’РѕР·РІСЂР°С‰Р°РµС‚ РјРЅРѕР¶РµСЃС‚РІРѕ РёРјРµРЅ РєРѕР»РѕРЅРѕРє С‚Р°Р±Р»РёС†С‹."""
    try:
        cursor.execute(f"PRAGMA table_info({table_name});")
        return {row[1] for row in cursor.fetchall()}
    except Exception:
        return set()

def upgrade_database():
    print("=" * 60)
    print("  РњРР“Р РђР¦РРЇ Р‘РђР—Р« Р”РђРќРќР«РҐ COPP-RAS")
    print("=" * 60)

    # 1. РЎРЅР°С‡Р°Р»Р° РёСЃРїРѕР»СЊР·СѓРµРј РєРѕРЅС‚РµРєСЃС‚ Flask РґР»СЏ СЃРѕР·РґР°РЅРёСЏ РІСЃРµС… РЅРѕРІС‹С… С‚Р°Р±Р»РёС†
    try:
        from app import create_app
        from app.extensions import db
        app = create_app()
        with app.app_context():
            db.create_all()
            print("[OK] РќРѕРІС‹Рµ С‚Р°Р±Р»РёС†С‹ (РµСЃР»Рё РѕС‚СЃСѓС‚СЃС‚РІРѕРІР°Р»Рё) СѓСЃРїРµС€РЅРѕ СЃРѕР·РґР°РЅС‹ С‡РµСЂРµР· SQLAlchemy.")
    except Exception as e:
        print(f"[WARN] РћС€РёР±РєР° РїСЂРё СЃРѕР·РґР°РЅРёРё С‚Р°Р±Р»РёС† С‡РµСЂРµР· SQLAlchemy: {e}")

    # 2. РџСЂСЏРјР°СЏ СЂР°Р±РѕС‚Р° СЃ С„Р°Р№Р»РѕРј SQLite РґР»СЏ РґРѕР±Р°РІР»РµРЅРёСЏ РЅРµРґРѕСЃС‚Р°СЋС‰РёС… РєРѕР»РѕРЅРѕРє
    db_path = os.path.join(basedir, 'reports.db')
    if not os.path.exists(db_path):
        print(f"[!] Р¤Р°Р№Р» Р±Р°Р·С‹ РґР°РЅРЅС‹С… РЅРµ РЅР°Р№РґРµРЅ РїРѕ РїСѓС‚Рё: {db_path}")
        print("    Р•СЃР»Рё РёСЃРїРѕР»СЊР·СѓРµС‚СЃСЏ РґСЂСѓРіРѕРµ РёРјСЏ С„Р°Р№Р»Р° РёР»Рё РїСѓС‚СЊ, РїСЂРѕРІРµСЂСЊС‚Рµ config.py")
        return False

    print(f"[*] РџРѕРґРєР»СЋС‡РµРЅРёРµ Рє Р±Р°Р·Рµ РґР°РЅРЅС‹С…: {db_path}")
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # РћРїРёСЃР°РЅРёРµ РЅРµРѕР±С…РѕРґРёРјС‹С… РєРѕР»РѕРЅРѕРє РґР»СЏ РїСЂРѕРІРµСЂРєРё:
    # (С‚Р°Р±Р»РёС†Р°, РєРѕР»РѕРЅРєР°, sql_С‚РёРї_Рё_РїР°СЂР°РјРµС‚СЂС‹)
    columns_to_check = [
        ('users', 'department_id', 'INTEGER REFERENCES departments(id)'),
        ('users', 'group', 'VARCHAR(50)'),
        ('uploaded_files', 'department_id', 'INTEGER REFERENCES departments(id)'),
        ('dictionaries', 'department_id', 'INTEGER REFERENCES departments(id)'),
        ('action_logs', 'ip_address', 'VARCHAR(45)'),
        ('report_templates', 'period_data', 'JSON'),
        ('report_templates', 'is_template', 'BOOLEAN DEFAULT 0'),
        ('report_templates', 'short_name', 'VARCHAR(64)'),
        ('report_submissions', 'is_revision', 'BOOLEAN DEFAULT 0'),
        ('report_submissions', 'revision_comment', 'TEXT'),
        ('report_submissions', 'returned_at', 'DATETIME'),
        ('report_submissions', 'returned_by_id', 'INTEGER REFERENCES users(id)'),
        ('report_submissions', 'submitted_at', 'DATETIME'),
        ('announcements', 'target_type', 'VARCHAR(20) DEFAULT "all"'),
        ('announcements', 'target_departments', 'JSON'),
        ('announcements', 'target_groups', 'JSON'),
    ]

    changes_applied = 0

    for table, column, col_def in columns_to_check:
        cols = get_columns(cursor, table)
        if not cols:
            print(f"[SKIP] РўР°Р±Р»РёС†Р° '{table}' РїРѕРєР° РЅРµ СЃСѓС‰РµСЃС‚РІСѓРµС‚, РїСЂРѕРїСѓСЃРєР°РµРј.")
            continue

        if column in cols:
            print(f"[OK]   РўР°Р±Р»РёС†Р° '{table}': РєРѕР»РѕРЅРєР° '{column}' СѓР¶Рµ СЃСѓС‰РµСЃС‚РІСѓРµС‚.")
        else:
            alter_query = f"ALTER TABLE {table} ADD COLUMN {column} {col_def};"
            try:
                cursor.execute(alter_query)
                conn.commit()
                print(f"[+]   РўР°Р±Р»РёС†Р° '{table}': РЈРЎРџР•РЁРќРћ РґРѕР±Р°РІР»РµРЅР° РєРѕР»РѕРЅРєР° '{column}'.")
                changes_applied += 1
            except Exception as err:
                print(f"[ERR] РћС€РёР±РєР° РїСЂРё РґРѕР±Р°РІР»РµРЅРёРё {table}.{column}: {err}")

    conn.close()

    # 3. РўРµСЃС‚РѕРІР°СЏ РїСЂРѕРІРµСЂРєР° ORM-Р·Р°РїСЂРѕСЃР° Рє РјРѕРґРµР»Рё User Рё РёРЅРёС†РёР°Р»РёР·Р°С†РёСЏ РЅР°СЃС‚СЂРѕРµРє
    print("-" * 60)
    print("[*] РџСЂРѕРІРµСЂРєР° С‡С‚РµРЅРёСЏ РјРѕРґРµР»Рё User Рё РЅР°СЃС‚СЂРѕРµРє С‡РµСЂРµР· SQLAlchemy...")
    try:
        with app.app_context():
            from app.models import User, MaintenanceSetting
            count = User.query.count()
            sample_user = User.query.first()
            user_info = f"'{sample_user.username}', РѕС‚РґРµР»: {sample_user.department_id}" if sample_user else "РЅРµС‚ Р·Р°РїРёСЃРµР№"
            print(f"[OK] РџРѕР»СЊР·РѕРІР°С‚РµР»РµР№ РІ Р±Р°Р·Рµ: {count} (РїСЂРёРјРµСЂ: {user_info}).")

            # РРЅРёС†РёР°Р»РёР·РёСЂСѓРµРј Р·Р°РїРёСЃСЊ РЅР°СЃС‚СЂРѕРµРє С‚РµС…СЂР°Р±РѕС‚, РµСЃР»Рё РµС‰Рµ РЅРµС‚
            setting = MaintenanceSetting.get_settings()
            print(f"[OK] РўР°Р±Р»РёС†Р° maintenance_settings РіРѕС‚РѕРІР° (СЃС‚Р°С‚СѓСЃ Р°РєС‚РёРІРЅРѕСЃС‚Рё: {setting.is_active}).")
    except Exception as e:
        print(f"[ERR] РћС€РёР±РєР° РїСЂРё РїСЂРѕРІРµСЂРєРµ С‡С‚РµРЅРёСЏ РґР°РЅРЅС‹С…: {e}")
        return False

    print("=" * 60)
    print(f"  Р“РћРўРћР’Рћ! РџСЂРёРјРµРЅРµРЅРѕ РёР·РјРµРЅРµРЅРёР№: {changes_applied}. Р‘Р°Р·Р° РґР°РЅРЅС‹С… Р°РєС‚СѓР°Р»СЊРЅР°.")
    print("=" * 60)
    return True

if __name__ == '__main__':
    success = upgrade_database()
    sys.exit(0 if success else 1)
