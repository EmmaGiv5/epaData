# Initializes your Flask application 
# Creates the Flask app and connects:
# Flask-SQLAlchemy, Flask-Migrate, configuration, and routes/blueprints

from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate

from .config import Config


db = SQLAlchemy() # connect to our models to SQLite 
migrate = Migrate()


def create_app(): # creates the Flask application
    app = Flask(__name__)

    # Load configuration
    app.config.from_object(Config)

    # Initialize database
    db.init_app(app)

    # Initialize migrations
    migrate.init_app(app, db)

    # Register routes
    from .routes.main import main_bp
    app.register_blueprint(main_bp)

    return app
