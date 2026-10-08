from pathlib import Path
import struct

DB = Path("instance/epadata_corrupted_backup.db")

data = DB.read_bytes()

print(f"File size: {len(data):,} bytes")

# SQLite header
print("\nSQLite header:")
print(data[:16])

if data[:16] == b"SQLite format 3\x00":
    print("Valid SQLite header: YES")
else:
    print("Valid SQLite header: NO")

# SQLite page size is stored at bytes 16-17.
page_size = struct.unpack(">H", data[16:18])[0]

if page_size == 1:
    page_size = 65536

print(f"Page size: {page_size:,} bytes")

# Number of pages from database header, bytes 28-31.
page_count = struct.unpack(">I", data[28:32])[0]

print(f"Header page count: {page_count}")

actual_pages = len(data) // page_size

print(f"Actual complete pages: {actual_pages}")

print("\nPage information:")

for page_number in range(1, actual_pages + 1):
    start = (page_number - 1) * page_size
    end = start + page_size

    page = data[start:end]

    if page_number == 1:
        # Database header occupies first 100 bytes.
        page_content = page[100:]
    else:
        page_content = page

    if not page_content:
        print(f"Page {page_number}: EMPTY")
        continue

    first_byte = page_content[0]

    page_types = {
        0x02: "interior index B-tree",
        0x05: "interior table B-tree",
        0x0A: "leaf index B-tree",
        0x0D: "leaf table B-tree",
    }

    page_type = page_types.get(
        first_byte,
        f"UNKNOWN (0x{first_byte:02X})"
    )

    print(
        f"Page {page_number}: "
        f"first byte=0x{first_byte:02X}, "
        f"type={page_type}"
    )