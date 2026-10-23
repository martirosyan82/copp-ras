import sqlite3

def dump_schema(db_path):
    print(f"Schema for {db_path}:")
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("SELECT name, sql FROM sqlite_master WHERE type='table';")
    tables = cursor.fetchall()
    for table_name, schema in tables:
        print(schema)
    conn.close()
    print("\n" + "="*50 + "\n")

dump_schema('reports_main.db')
dump_schema('reports.db')
