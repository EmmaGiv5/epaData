
# Initializes your Flask application
# Connects the database, configuration, models, and routes.

import os

from flask import Flask, request, redirect, url_for, session
from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()


def create_app():
    # Create the Flask application
    app = Flask(__name__)

    # Load application configuration
    app.config.from_object("app.config.Config")

    # Configure uploaded files
    app.config["UPLOAD_FOLDER"] = os.path.join(
        app.root_path,
        "uploads"
    )

    os.makedirs(
        app.config["UPLOAD_FOLDER"],
        exist_ok=True
    )

    # Initialize the database connection
    db.init_app(app)

    # Load database models
    from . import models

    # Import application blueprints
    from .routes.main import main_bp
    from .routes.explorer import explorer_bp

    # Register blueprints
    app.register_blueprint(main_bp)
    app.register_blueprint(explorer_bp)

    # Require login before accessing protected pages
    # Keep disabled while testing the application.
    
    @app.before_request
    def require_login():
        if request.endpoint == "static":
            return None
    
        if request.endpoint == "main.login":
            return None
    
        if "user_id" not in session:
            return redirect(url_for("main.login"))

    # Create database tables and check database configuration
    with app.app_context():
        print("\n========== DATABASE CHECK ==========")

        print("\nDATABASE LOCATION:")
        print(db.engine.url)

        print("\nTABLES BEFORE create_all:")
        print(list(db.metadata.tables.keys()))

        db.create_all()

        print("\nTABLES AFTER create_all:")
        print(list(db.metadata.tables.keys()))

        print("====================================\n")

    # Print registered routes for debugging
    print("Registered routes:")
    for rule in app.url_map.iter_rules():
        print(rule, "->", rule.endpoint)
        print("========\n")

    return app
