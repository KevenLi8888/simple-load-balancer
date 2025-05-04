import itertools
import threading
from typing import List, Dict
from src.algorithms import LoadBalancingAlgorithm
from src.db.models import Instance

class WeightedRoundRobinAlgorithm(LoadBalancingAlgorithm):
    _counter = itertools.cycle(range(1_000_000))  # large enough cycle
    _lock = threading.Lock()  # thread-safe counter lock
    
    # instance weight mapping (instance ID -> weight value)
    _weights: Dict[str, int] = {}
    
    def __init__(self, instances: List[Instance], client_ip: str = None):
        super().__init__(instances, client_ip)
        
        # for simplicity, we assign fixed weights to instances
        # in actual applications, these weights may come from configuration or database
        for i, instance in enumerate(instances):
            # assign weights 1, 2, 3 to the first three instances
            # if there are more than 3 instances, the weights of the subsequent instances are 1
            weight = i + 1 if i < 3 else 1
            self._weights[instance.id] = weight
    
    def select_instance(self) -> Instance:
        """select the next instance based on weights"""
        if not self.instances:
            raise ValueError("No instances available")
        
        # create an extended list, copy instances according to weights
        weighted_instances = []
        for instance in self.instances:
            weight = self._weights.get(instance.id, 1)  # default weight is 1
            # add instances to the list according to weights
            weighted_instances.extend([instance] * weight)
        
        if not weighted_instances:
            return self.instances[0]  # if there is an issue, return the first instance
        
        # use the round-robin counter to select an instance
        with self._lock:
            index = next(self._counter) % len(weighted_instances)
            return weighted_instances[index]