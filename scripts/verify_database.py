import sqlite3
from pathlib import Path

db_path = Path("instance") / "epadata.db"

print("Database:", db_path)
print("Exists:", db_path.exists())

if not db_path.exists():
    raise SystemExit("ERROR: epadata.db does not exist.")

print("Size:", db_path.stat().st_size, "bytes")
print()

connection = sqlite3.connect(db_path)

print("Integrity check:")
print(connection.execute("PRAGMA integrity_check").fetchone())

print()
print("Tables:")

tables = connection.execute(
    "SELECT name FROM sqlite_master "
    "WHERE type = 'table' "
    "ORDER BY name"
).fetchall()

for table in tables:
    print("  -", table[0])

print()
print("Annual records table exists:",
      any(table[0] == "annual_records" for table in tables))

connection.close()