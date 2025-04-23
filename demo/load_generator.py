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
    
    def worker(self):
        headers = {'Host': self.host_header}
        
        while True:
            with self.lock:
                if self.completed >= self.total_requests:
                    break
                self.completed += 1
                current = self.completed
            
            start_time = time.time()
            try:
                response = requests.get(f"{self.url}/test?id={current}", headers=headers)
                status_code = response.status_code
                server_info = response.json() if response.status_code == 200 else None
            except Exception as e:
                status_code = 0
                server_info = str(e)
            
            duration = time.time() - start_time
            
            with self.lock:
                self.results.append({
                    'request_id': current,
                    'status_code': status_code,
                    'duration': duration,
                    'server_info': server_info
                })
                
                # Progress update
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
        
        for t in threads:
            t.join()
        
        total_time = time.time() - start_time
        
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
        if all(r['status_code'] == 200 for r in self.results):
            server_ports = [r['server_info']['server_port'] for r in self.results]
            port_counts = Counter(server_ports)
            print("\nServer Distribution:")
            for port, count in port_counts.items():
                print(f"  Server on port {port}: {count} ({count/len(self.results)*100:.1f}%)")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Load Generator for Demo Load Balancer')
    parser.add_argument('--url', default=LOAD_BALANCER_ADDR, help='Load balancer URL')
    parser.add_argument('--host', default=DEFAULT_HOST_HEADER, help='Host header for the request')
    parser.add_argument('--concurrency', type=int, default=DEFAULT_CONCURRENCY, help='Number of concurrent clients')
    parser.add_argument('--requests', type=int, default=DEFAULT_REQUESTS, help='Total number of requests')
    args = parser.parse_args()
    
    generator = LoadGenerator(args.url, args.host, args.concurrency, args.requests)
    generator.run()
