from typing import Dict, Type, List, Optional
from src.algorithms import LoadBalancingAlgorithm
from src.algorithms.round_robin import RoundRobinAlgorithm
from src.algorithms.ip_hash import IpHashAlgorithm
from src.algorithms.least_connection import LeastConnectionAlgorithm
from src.db.models import Instance, Algorithm

class AlgorithmFactory:
    _algorithms: Dict[Algorithm, Type[LoadBalancingAlgorithm]] = {
        Algorithm.ROUND_ROBIN: RoundRobinAlgorithm,
        Algorithm.IP_HASH: IpHashAlgorithm,
        Algorithm.LEAST_CONNECTION: LeastConnectionAlgorithm
    }
    
    @classmethod
    def get_algorithm(cls, algorithm_type: Algorithm, instances: List[Instance], client_ip: Optional[str] = None) -> LoadBalancingAlgorithm:
        """
        Factory method to get the appropriate load balancing algorithm
        """
        if algorithm_type not in cls._algorithms:
            raise ValueError(f"Algorithm '{algorithm_type}' not supported")
        
        algorithm_class = cls._algorithms[algorithm_type]
        return algorithm_class(instances, client_ip if client_ip is not None else "")