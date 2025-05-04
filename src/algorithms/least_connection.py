from typing import List, Dict
from src.algorithms import LoadBalancingAlgorithm
from src.db.models import Instance
import threading

class LeastConnectionAlgorithm(LoadBalancingAlgorithm):
    _connections: Dict[str, int] = {}  # instance_id -> connection count
    _lock = threading.Lock()  # Thread safety for connection counts

    def __init__(self, instances: List[Instance], client_ip: str):
        super().__init__(instances, client_ip)
        # Initialize connection counts for new instances
        with self._lock:
            for instance in instances:
                if instance.id not in self._connections:
                    self._connections[instance.id] = 0

    @classmethod
    def increment_connections(cls, instance_id: str) -> None:
        """Increment the connection count for an instance."""
        with cls._lock:
            cls._connections[instance_id] = cls._connections.get(instance_id, 0) + 1

    @classmethod
    def decrement_connections(cls, instance_id: str) -> None:
        """Decrement the connection count for an instance."""
        with cls._lock:
            if instance_id in cls._connections and cls._connections[instance_id] > 0:
                cls._connections[instance_id] -= 1

    def select_instance(self) -> Instance:
        """Select the instance with the least number of active connections."""
        if not self.instances:
            raise ValueError("No instances available")
        
        with self._lock:
            # Find instance with minimum connections
            min_connections = float('inf')
            selected_instance = None
            
            for instance in self.instances:
                curr_connections = self._connections.get(instance.id, 0)
                if curr_connections < min_connections:
                    min_connections = curr_connections
                    selected_instance = instance
            
            if selected_instance:
                # Increment connection count for selected instance
                self.increment_connections(selected_instance.id)
                return selected_instance
            
            # Fallback to first instance if something went wrong
            return self.instances[0]