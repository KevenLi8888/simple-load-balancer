from typing import List
from src.algorithms import LoadBalancingAlgorithm
from src.db.models import Instance
import itertools
import threading

class RoundRobinAlgorithm(LoadBalancingAlgorithm):
    _counter = itertools.cycle(range(1_000_000))  # Large enough cycle
    _lock = threading.Lock()  # Thread safety for counter

    def __init__(self, instances: List[Instance], client_ip: str = None):
        super().__init__(instances, client_ip)

    def select_instance(self) -> Instance:
        """Select the next instance in a round-robin fashion."""
        if not self.instances:
            raise ValueError("No instances available")
        
        with self._lock:
            index = next(self._counter) % len(self.instances)
            return self.instances[index]