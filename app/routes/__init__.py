# Used to organize/import your routes and Flask blueprints.
# Such as main_bp, retireval_bp, upload_bp, 
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

    with app.app_context():
        db.create_all()

    return app