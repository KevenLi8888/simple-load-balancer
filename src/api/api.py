import os
from flask import Flask
from src.utils.config import get_config
from src.db.connection import close_mongo_connection
from src.api.service import service_bp
from src.api.instance import instance_bp

def create_api_server() -> Flask:
    """Creates and configures the Flask API server."""
    app = Flask(__name__)

    # Register Blueprints for API endpoints
    app.register_blueprint(service_bp)
    app.register_blueprint(instance_bp)

    # # Teardown context to close DB connection when app stops
    # @app.teardown_appcontext
    # def shutdown_session(exception=None):
    #     close_mongo_connection()

    # Basic root endpoint (optional)
    @app.route('/')
    def index():
        return "Load Balancer API is running."

    return app
