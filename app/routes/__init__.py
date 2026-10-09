# Used to organize/import your routes and Flask blueprints.
# Such as main_bp, retrieval_bp, upload_bp,
# explorer_bp, facility_bp, and download_bp

from flask import Flask
from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()


def create_app():
    app = Flask(__name__)

    # Store the SQLite database in the project's instance folder
    app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///epaData.db"
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

    db.init_app(app)

    # Register application routes
    from app.routes import main_bp

    app.register_blueprint(main_bp)

    # Load database models
    from app import models

    # Check database and create missing tables
    with app.app_context():
        print("\nDATABASE:")
        print(db.engine.url)

        print("\nTABLES BEFORE create_all:")
        print(db.metadata.tables.keys())

        db.create_all()

        print("\nTABLES AFTER create_all:")
        print(db.metadata.tables.keys())

    return app