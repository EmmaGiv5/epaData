# Initializes your Flask application 
# Creates the Flask app and connects:
# Flask-SQLAlchemy, Flask-Migrate, configuration, and routes/blueprints

from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate

from .config import Config


db = SQLAlchemy()
migrate = Migrate()


def create_app():
    app = Flask(__name__)

    # Load configuration
    app.config.from_object(Config)

    # Initialize database
    db.init_app(app)

    # Initialize migrations
    migrate.init_app(app, db)

    # Import models
    from .models import (
        Dataset,
        Facility,
        Unit,
        AnnualRecord,
        UploadedFile,
        DataProvenance
    )

    # Register routes
    from .routes.main import main_bp
    app.register_blueprint(main_bp)

    return app