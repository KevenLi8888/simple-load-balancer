import http.server
import socketserver
import json
import argparse
import threading
import requests
import time
import socket
from functools import partial
import collections
import threading
import time

# Hard-coded configuration
DEFAULT_PORT = 28000
SERVICE_NAME = "demo-service"
SERVICE_HEADER = "demo-service"
SERVICE_REGISTRY_ADDR = "http://localhost:18081"

# Global variables for RPS calculation
request_timestamps = collections.deque()
rps_lock = threading.Lock()
RPS_WINDOW_SECONDS = 5 # Calculate RPS over the last 10 seconds
RPS_UPDATE_INTERVAL = 2 # Update RPS every 2 seconds

class DemoHTTPHandler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, port=None, **kwargs):
        self.port = port
        super().__init__(*args, **kwargs)
        
    def do_GET(self):
        # Record timestamp for RPS calculation
        with rps_lock:
            request_timestamps.append(time.time())
            
        self.send_response(200)
        self.send_header('Content-type', 'application/json')
        self.end_headers()
        
        response = {
            'message': 'Hello from demo server!',
            'server_port': self.port,
            'path': self.path
        }
        
        self.wfile.write(json.dumps(response).encode())

    def log_message(self, format, *args):
        """Suppress default logging."""
        pass

def register_with_load_balancer(port):
    # Try to find the service by header first
    service_id = None
    try:
        service_lookup_url = f"{SERVICE_REGISTRY_ADDR}/services/header/{SERVICE_HEADER}"
        response = requests.get(service_lookup_url)
        if response.status_code == 200:
            service_id = response.json()['id']
            print(f"Found existing service '{SERVICE_NAME}' with ID: {service_id}")
        elif response.status_code == 404:
            print(f"Service with header '{SERVICE_HEADER}' not found. Attempting to create.")
        else:
            # Handle other potential errors during lookup
            response.raise_for_status()

    except requests.exceptions.RequestException as e:
        print(f"Error looking up service by header: {e}")
        # Decide if you want to proceed to creation or exit
        # For now, we'll proceed to attempt creation

    except Exception as e:
        print(f"An unexpected error occurred during service lookup: {e}")
        # Decide if you want to proceed or exit

    # If service not found, create it
    if not service_id:
        try:
            service_payload = {
                'name': SERVICE_NAME,
                'header': SERVICE_HEADER,
                'stateful': False # Assuming stateless for demo
                # 'algorithm': 'round_robin' # Optional: specify algorithm if needed
            }
            service_create_url = f"{SERVICE_REGISTRY_ADDR}/services"
            service_response = requests.post(service_create_url, json=service_payload)
            service_response.raise_for_status() # Check for HTTP errors
            service_id = service_response.json()['id']
            print(f"Created service '{SERVICE_NAME}' with ID: {service_id}")
        except requests.exceptions.RequestException as e:
            print(f"Failed to create service: {e}")
            # If service creation fails, we cannot register an instance
            return None, None
        except Exception as e:
            print(f"An unexpected error occurred during service creation: {e}")
            return None, None

    # Register instance for the found/created service
    try:
        hostname = socket.gethostname()
        # Ensure we get an IP address, not just the hostname if it resolves differently
        try:
            ip = socket.gethostbyname(hostname)
        except socket.gaierror:
             # Fallback if gethostbyname fails (e.g., misconfigured /etc/hosts)
             # This might get 127.0.0.1, which might be okay for local testing
             # but not ideal for network accessibility. Consider logging a warning.
             print(f"Warning: Could not resolve hostname '{hostname}' to IP via gethostbyname. Falling back.")
             ip = socket.gethostbyname('') # Often resolves to 127.0.0.1 or a local IP

        # API expects 'addr' field in 'host:port' format
        instance_payload = {
            'addr': f"{ip}:{port}"
            # 'status': 'healthy' # Optional: Can set initial status if API allows
        }
        instance_create_url = f"{SERVICE_REGISTRY_ADDR}/services/{service_id}/instances"
        instance_response = requests.post(instance_create_url, json=instance_payload)
        instance_response.raise_for_status() # Check for HTTP errors

        instance_id = instance_response.json()['id']
        print(f"Registered instance {ip}:{port} with ID {instance_id} for service {service_id}")
        return instance_id, service_id

    except requests.exceptions.RequestException as e:
        print(f"Failed to register instance: {e}")
        # Consider if cleanup (like deleting the service if just created) is needed
        return None, service_id # Return service_id for potential cleanup if needed
    except Exception as e:
        print(f"An unexpected error occurred during instance registration: {e}")
        return None, service_id

def deregister_from_load_balancer(service_id, instance_id):
    if service_id and instance_id:
        try:
            response = requests.delete(f"{SERVICE_REGISTRY_ADDR}/services/{service_id}/instances/{instance_id}")
            response.raise_for_status() # Check for HTTP errors
            print("Deregistered from load balancer")
        except requests.exceptions.RequestException as e: # Catch specific requests errors
            print(f"Failed to deregister from load balancer: {e}")
        except Exception as e: # Catch other potential errors
            print(f"An unexpected error occurred during deregistration: {e}")

def calculate_and_print_rps(stop_event):
    """Periodically calculates and prints RPS."""
    while not stop_event.is_set():
        stop_event.wait(RPS_UPDATE_INTERVAL) # Wait for the interval or until stopped
        if stop_event.is_set():
            break
            
        with rps_lock:
            now = time.time()
            # Remove timestamps older than the window
            while request_timestamps and request_timestamps[0] < now - RPS_WINDOW_SECONDS:
                request_timestamps.popleft()
            
            # Calculate RPS
            count = len(request_timestamps)
            rps = count / RPS_WINDOW_SECONDS if RPS_WINDOW_SECONDS > 0 else 0
            
        print(f"RPS ({RPS_WINDOW_SECONDS}s window): {rps:.2f}")

def run_server(port):
    Handler = partial(DemoHTTPHandler, port=port)
    
    # Start RPS calculation thread
    stop_event = threading.Event()
    rps_thread = threading.Thread(target=calculate_and_print_rps, args=(stop_event,), daemon=True)
    rps_thread.start()

    with socketserver.TCPServer(("", port), Handler) as httpd:
        print(f"Server running on port {port}")
        
        # Register with load balancer
        instance_id, service_id = register_with_load_balancer(port)
        
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\nShutting down server...")
        finally:
            # Stop RPS thread
            print("Stopping RPS calculator...")
            stop_event.set()
            rps_thread.join(timeout=RPS_UPDATE_INTERVAL + 1) # Wait for thread to finish
            
            # Deregister from load balancer
            deregister_from_load_balancer(service_id, instance_id)
            httpd.server_close()

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Demo HTTP Server')
    parser.add_argument('--port', type=int, default=DEFAULT_PORT, help='Port to run the server on')
    args = parser.parse_args()
    
    run_server(args.port)
