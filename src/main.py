import sys
import os
import argparse
import threading
from flask import Flask, request
import logging

# Add src directory to Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.utils.config import load_config, get_config
from src.db.connection import connect_to_mongo
from src.api.api import create_api_server
from src.core.balancer import LoadBalancer
from src.core.health_checker import HealthChecker

def create_lb_server(health_checker: HealthChecker) -> Flask:
    """Creates the load balancer server."""
    app = Flask(__name__)
    lb = LoadBalancer()

    # Proxy all requests
    @app.route('/', defaults={'path': ''}, methods=['GET', 'POST', 'PUT', 'DELETE', 'PATCH'])
    @app.route('/<path:path>', methods=['GET', 'POST', 'PUT', 'DELETE', 'PATCH'])
    def proxy(path):
        return lb.route_request(request, path)

    return app

def run_server(app: Flask, host: str, port: int, name: str):
    """Run a Flask server in a thread."""
    if name == 'Load Balancer':
        # Disable Werkzeug's default request logging for the load balancer
        log = logging.getLogger('werkzeug')
        log.setLevel(logging.ERROR)
        
    try:
        app.run(host=host, port=port, threaded=True)
    except Exception as e:
        print(f"Error starting {name} server: {e}", file=sys.stderr)
        sys.exit(1)

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description="Run the Load Balancer and API servers.")
    parser.add_argument('--config', type=str, default='config.yaml', help='Path to the configuration file.')
    args = parser.parse_args()

    if not os.path.exists(args.config):
        print(f"Error: Configuration file not found at {args.config}", file=sys.stderr)
        sys.exit(1)

    # Load configuration
    load_config(args.config)
    config = get_config()
    
    # Setup logging
    logging_config = config.get('logging', {})
    log_level_name = logging_config.get('level', 'INFO').upper()
    log_file = logging_config.get('file')
    
    logger = logging.getLogger()
    logger.setLevel(getattr(logging, log_level_name, logging.INFO))
    
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    
    # Console Handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)
    
    # File Handler (if specified)
    if log_file:
        # Ensure log directory exists
        log_dir = os.path.dirname(log_file)
        if log_dir and not os.path.exists(log_dir):
            os.makedirs(log_dir)
            
        file_handler = logging.FileHandler(log_file)
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)
    
    # Connect to MongoDB
    print("Establishing MongoDB connection...")
    connect_to_mongo()

    # Initialize health checker
    health_checker = HealthChecker(
        interval=config.get('health_check', {}).get('interval', 5),
        timeout=config.get('health_check', {}).get('timeout', 2),
        retries=config.get('health_check', {}).get('retries', 3)
    )
    
    # Create API and LB servers
    api_app = create_api_server()
    lb_app = create_lb_server(health_checker)

    # Get server configurations
    api_config = config.get('api', {})
    lb_config = config.get('lb', {})

    # Start health checker
    health_checker.start()
    print("Health checker started")

    # Create and start server threads
    api_thread = threading.Thread(
        target=run_server,
        args=(api_app, api_config.get('host', '0.0.0.0'), api_config.get('port', 8081), 'API'),
        daemon=True
    )

    lb_thread = threading.Thread(
        target=run_server,
        args=(lb_app, lb_config.get('host', '0.0.0.0'), lb_config.get('port', 8080), 'Load Balancer'),
        daemon=True
    )

    print(f"Starting API server on {api_config.get('host', '0.0.0.0')}:{api_config.get('port', 8081)}")
    print(f"Starting Load Balancer on {lb_config.get('host', '0.0.0.0')}:{lb_config.get('port', 8080)}")

    # Start both servers
    api_thread.start()
    lb_thread.start()

    # Keep the main thread alive
    try:
        while True:
            if not api_thread.is_alive() or not lb_thread.is_alive():
                print("One of the servers has stopped unexpectedly", file=sys.stderr)
                sys.exit(1)
            threading.Event().wait(1)
    except KeyboardInterrupt:
        print("\nShutting down servers...")
        health_checker.stop()
        sys.exit(0)
