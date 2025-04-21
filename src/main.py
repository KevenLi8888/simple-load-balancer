import sys
import os
import argparse

# Add src directory to Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.utils.config import load_config, get_config
from src.db.connection import connect_to_mongo
from src.api.api import create_api_server
# Import other components like balancer, health_checker later

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description="Run the Load Balancer API server.")
    parser.add_argument('--config', type=str, default='config.yaml', help='Path to the configuration file.')
    args = parser.parse_args()

    config_path = args.config

    if not os.path.exists(config_path):
        print(f"Error: Configuration file not found at {config_path}", file=sys.stderr)
        sys.exit(1)

    # Load configuration first
    load_config(config_path)
    
    # Connect to MongoDB before creating API server
    print("Establishing MongoDB connection...")
    connect_to_mongo()
    
    # Now create the API server
    api_app = create_api_server()

    # Get config values after loading
    api_config = get_config().get('api', {})
    host = api_config.get('host', '0.0.0.0')
    port = api_config.get('port', 8081)
    # Ensure logging config is accessed safely
    logging_config = get_config().get('logging', {})
    debug_mode = logging_config.get('level', 'INFO').upper() == 'DEBUG'

    print(f"Starting API server on {host}:{port} with config from {config_path}")
    # Note: Flask's development server is not recommended for production.
    # Use a production-ready WSGI server like Gunicorn or uWSGI.
    api_app.run(host=host, port=port, debug=debug_mode)

    # The load balancer core logic (proxying) would run separately or in a different process/thread.
    # This main.py currently only starts the API server.
