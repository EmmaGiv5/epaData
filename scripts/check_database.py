import sqlite3
from pathlib import Path

db_path = Path("instance/epadata.db")

print(f"Database: {db_path}")
print(f"Exists: {db_path.exists()}")
print(f"Size: {db_path.stat().st_size:,} bytes")

try: 
    conn = sqlite3.connect(str(db_path))
    print("\nRunning integrity check....")
    result = conn.execute("PRAGMA integrity_check").fetchall()
    print(result)

    print("\nReading tables...")
    tables = conn.execute("""
    SELECT name FROM sqlite_master WHERE type='table ORDER BY name """).fetchall()
    print(tables)
    conn.close()
except Exception as e:
    print(f"\nERROR: {type(e)._name_}: {e}")
    