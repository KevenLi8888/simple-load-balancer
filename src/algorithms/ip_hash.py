import hashlib
from typing import List
from src.algorithms import LoadBalancingAlgorithm
from src.db.models import Instance

class IpHashAlgorithm(LoadBalancingAlgorithm):
    def __init__(self, instances: List[Instance], client_ip: str = ""):
        super().__init__(instances, client_ip)
        if client_ip == "":
            raise ValueError("Client IP is required for IP Hash algorithm")

    def select_instance(self) -> Instance:
        """Select an instance based on the hash of the client's IP address."""
        if not self.instances:
            raise ValueError("No instances available")
        

        if self.client_ip == "":
            raise ValueError("Client IP is required for IP Hash algorithm")
        
        # Create a hash of the IP address
        hash_obj = hashlib.md5(self.client_ip.encode())
        hash_hex = hash_obj.hexdigest()
        hash_int = int(hash_hex, 16)
        
        # Use the hash to select an instance
        index = hash_int % len(self.instances)
        return self.instances[index]