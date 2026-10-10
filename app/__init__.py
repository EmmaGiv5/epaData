# Initializes your Flask application
# Creates the Flask app and connects:
# Flask-SQLAlchemy, Flask-Migrate, configuration, and routes/blueprints

import os
from flask import Flask, request, redirect, url_for, session
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate

db = SQLAlchemy()
migrate = Migrate()


def create_app():

    # Create the Flask application FIRST
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

    # Connect database and migrations
    db.init_app(app)
    migrate.init_app(app, db)

    # Register blueprints
    from .routes.main import main_bp
    from .routes.explorer import explorer_bp

    app.register_blueprint(main_bp)
    app.register_blueprint(explorer_bp)
    # Require login before accessing protected pages
    ''' 
    @app.before_request
    def require_login():

        # Allow CSS, images, and JavaScript to load
        if request.endpoint == "static":
            return None

        # Allow the login page without being logged in
        if request.endpoint == "main.login":
            return None

        # Redirect unauthenticated users to the login page
        if "user_id" not in session:
            return redirect(url_for("main.login"))

        # Allow logged-in users to continue
        return None
    '''

    # Print routes for debugging
    print("Registered routes:")
    for rule in app.url_map.iter_rules():
        print(rule, "->", rule.endpoint)
        print("========\n")

    return app