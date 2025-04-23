from abc import ABC, abstractmethod
from typing import List
from src.db.models import Instance

class LoadBalancingAlgorithm(ABC):
    def __init__(self, instances: List[Instance], client_ip: str = None):
        self.instances = instances
        self.client_ip = client_ip

    @abstractmethod
    def select_instance(self) -> Instance:
        """Returns the next instance to handle a request based on the algorithm's logic."""
        pass