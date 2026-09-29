# Initializes your Flask application 
# Creates the Flask app and connects:
# Flask-SQLAlchemy, Flask-Migrate, configuration, and routes/blueprints

import os
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate

db = SQLAlchemy()
migrate = Migrate()


def create_app():

    app = Flask(__name__)

    app.config["SECRET_KEY"] = "dev-secret-key"

    app.config["SQLALCHEMY_DATABASE_URI"] = (
        "sqlite:///epaData.db"
    )

    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

    app.config["UPLOAD_FOLDER"] = os.path.join(
        app.root_path,
        "uploads"
    )

    os.makedirs(
        app.config["UPLOAD_FOLDER"],
        exist_ok=True
    )

    db.init_app(app)
    migrate.init_app(app, db)

    from .routes.main import main_bp
    from .routes.explorer import explorer_bp

    app.register_blueprint(main_bp)
    app.register_blueprint(explorer_bp)

    print("Register routes")
    for rule in app.url_map.iter_rules():
        print(rule, "->", rule.endpoint)
        print("========\n")
    return app