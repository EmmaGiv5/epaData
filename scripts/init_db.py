"""
Initialize the epaData SQLite database.

Creates all Phase 1 SQLAlchemy tables and verifies the database.
"""

from app import create_app, db

# Import the models so SQLAlchemy knows about them.
from app.models import (
    Dataset,
    Facility,
    Unit,
    AnnualRecord,
    UploadedFile,
    DataProvenance,
)


def main():
    app = create_app()

    with app.app_context():
        database_uri = app.config["SQLALCHEMY_DATABASE_URI"]

        print(f"Database URI: {database_uri}")
        print()
        print("Creating database tables...")

        db.create_all()

        print("Database tables created successfully.")
        print()

        inspector = db.inspect(db.engine)
        tables = inspector.get_table_names()

        print("Tables:")

        for table in tables:
            print(f"  - {table}")

        required_tables = {
            "datasets",
            "facilities",
            "units",
            "annual_records",
            "uploaded_files",
            "data_provenance",
        }

        missing = required_tables - set(tables)

        if missing:
            print()
            print("ERROR: Missing required tables:")

            for table in sorted(missing):
                print(f"  - {table}")

            raise SystemExit(1)

        print()
        print("Database initialization successful.")


if __name__ == "__main__":
    main()