"""Flask application factory."""

from flask import Flask
from .routes import register_routes


def create_app():
    app = Flask(
        __name__,
        static_folder='../static',
        template_folder='../templates'
    )
    app.secret_key = 'rps-game-secret-key'
    register_routes(app)
    return app
