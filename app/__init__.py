from flask import Flask

def create_app():
    """Factory to create and configure the Flask application."""
    app = Flask(__name__)

    # Import and register blueprints/routes
    from .routes import main
    app.register_blueprint(main)

    return app
