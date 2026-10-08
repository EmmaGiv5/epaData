import sqlite3

db = r"instance\epaData_recovery.db"

try:
    conn = sqlite3.connect(db)
    print("Connected to:", db)

    rows = conn.execute(
        "SELECT name, type FROM sqlite_master "
        "WHERE type IN ('table', 'index', 'view', 'trigger') "
        "ORDER BY type, name"
    ).fetchall()

    print("\nSQLite objects:")
    for row in rows:
        print(row)

except Exception as e:
    print("\nERROR:")
    print(type(e).__name__, e)

finally:
    try:
        conn.close()
    except:
        pass