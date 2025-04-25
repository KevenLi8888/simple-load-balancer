import requests
import threading
import time
import random
import argparse
from collections import Counter

# Hard-coded configuration
LOAD_BALANCER_ADDR = "http://localhost:18080"
DEFAULT_HOST_HEADER = "demo-service"
DEFAULT_CONCURRENCY = 10
DEFAULT_REQUESTS = 100000

class LoadGenerator:
    def __init__(self, url, host_header, concurrency, total_requests):
        self.url = url
        self.host_header = host_header
        self.concurrency = concurrency
        self.total_requests = total_requests
        self.results = []
        self.lock = threading.Lock()
        self.completed = 0
        self.stop_requested = threading.Event()  # Add a stop event
    
    def worker(self):
        headers = {'Host': self.host_header}
        
        while not self.stop_requested.is_set():  # Check the stop event
            # Check stop event again before potentially blocking operations
            if self.stop_requested.is_set():
                break

            with self.lock:
                if self.completed >= self.total_requests:
                    break
                self.completed += 1
                current = self.completed
            
            # Check stop event before making the network request
            if self.stop_requested.is_set():
                break

            start_time = time.time()
            try:
                response = requests.get(f"{self.url}/test?id={current}", headers=headers)
                status_code = response.status_code
                server_info = response.json() if response.status_code == 200 else None

                if status_code != 200:
                    print(f"\nReceived status code {status_code}. Stopping load generator.")
                    self.stop_requested.set()  # Signal other threads to stop
                    # Optionally record the error before breaking
                    with self.lock:
                        self.results.append({
                            'request_id': current,
                            'status_code': status_code,
                            'duration': time.time() - start_time,
                            'server_info': f"Stopped due to status {status_code}"
                        })
                    break  # Stop this worker immediately

            except Exception as e:
                status_code = 0
                server_info = str(e)
                print(f"\nRequest failed: {e}. Stopping load generator.")
                self.stop_requested.set()  # Signal other threads to stop
                # Optionally record the error before breaking
                with self.lock:
                    self.results.append({
                        'request_id': current,
                        'status_code': status_code,
                        'duration': time.time() - start_time,
                        'server_info': f"Stopped due to exception: {e}"
                    })
                break  # Stop this worker immediately
            
            duration = time.time() - start_time
            
            with self.lock:
                # Only append successful results if not stopped
                if not self.stop_requested.is_set():
                    self.results.append({
                        'request_id': current,
                        'status_code': status_code,
                        'duration': duration,
                        'server_info': server_info
                    })
                    
                    # Progress update only if not stopping
                    if current % 10 == 0 or current == self.total_requests:
                        print(f"Completed {current}/{self.total_requests} requests")
    
    def run(self):
        print(f"Starting load test with {self.concurrency} concurrent clients")
        print(f"Target: {self.url} with Host header: {self.host_header}")
        
        start_time = time.time()
        
        threads = []
        for _ in range(self.concurrency):
            t = threading.Thread(target=self.worker)
            t.start()
            threads.append(t)
        
        try:
            # Wait for threads with a timeout to allow interrupt handling
            for t in threads:
                while t.is_alive():
                    t.join(timeout=0.1) # Check every 100ms
        except KeyboardInterrupt:
            print("\nCtrl+C detected. Signaling workers to stop...")
            self.stop_requested.set()
            # Wait briefly for threads to acknowledge the stop signal
            for t in threads:
                t.join(timeout=1.0) # Give threads a second to exit cleanly
        
        total_time = time.time() - start_time
        
        if self.stop_requested.is_set() and not any(r['status_code'] != 200 and r['status_code'] != 0 for r in self.results):
             print("\nLoad test interrupted by user.")
        elif self.stop_requested.is_set():
            print("\nLoad test stopped prematurely due to errors or interruption.")
        else:
            print("\nLoad test completed.")
        
        self.print_results(total_time)
    
    def print_results(self, total_time):
        print("\n=== Load Test Results ===")
        print(f"Total requests: {len(self.results)}")
        print(f"Total time: {total_time:.2f} seconds")
        print(f"Requests per second: {len(self.results) / total_time:.2f}")
        
        # Status code distribution
        status_counts = Counter(r['status_code'] for r in self.results)
        print("\nStatus Code Distribution:")
        for status, count in status_counts.items():
            print(f"  {status}: {count} ({count/len(self.results)*100:.1f}%)")
        
        # Response time stats
        durations = [r['duration'] for r in self.results]
        print("\nResponse Time (seconds):")
        print(f"  Min: {min(durations):.4f}")
        print(f"  Max: {max(durations):.4f}")
        print(f"  Avg: {sum(durations)/len(durations):.4f}")
        
        # Server distribution (load balancing check)
        # Filter out results that might not have server_info if stopped early
        successful_results = [r for r in self.results if r['status_code'] == 200 and r.get('server_info')]
        if successful_results:
            server_ports = [r['server_info']['server_port'] for r in successful_results]
            if server_ports:  # Check if there are any successful results with server ports
                port_counts = Counter(server_ports)
                print("\nServer Distribution (for successful requests):")
                total_successful = len(successful_results)
                for port, count in port_counts.items():
                    print(f"  Server on port {port}: {count} ({count/total_successful*100:.1f}%)")
            else:
                print("\nNo successful requests with server info to analyze distribution.")
        else:
            print("\nNo successful requests to analyze server distribution.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Load Generator for Demo Load Balancer')
    parser.add_argument('--url', default=LOAD_BALANCER_ADDR, help='Load balancer URL')
    parser.add_argument('--host', default=DEFAULT_HOST_HEADER, help='Host header for the request')
    parser.add_argument('--concurrency', type=int, default=DEFAULT_CONCURRENCY, help='Number of concurrent clients')
    parser.add_argument('--requests', type=int, default=DEFAULT_REQUESTS, help='Total number of requests')
    args = parser.parse_args()
    
    generator = LoadGenerator(args.url, args.host, args.concurrency, args.requests)
    generator.run()
