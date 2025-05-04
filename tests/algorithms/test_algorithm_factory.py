import pytest
from src.algorithms.algorithm_factory import AlgorithmFactory
from src.algorithms.round_robin import RoundRobinAlgorithm
from src.algorithms.ip_hash import IpHashAlgorithm
from src.algorithms.least_connection import LeastConnectionAlgorithm
from src.algorithms.weighted_round_robin import WeightedRoundRobinAlgorithm
from src.db.models import Algorithm


def test_get_round_robin_algorithm(mock_instances):
    """Test that the factory returns a RoundRobinAlgorithm instance"""
    algorithm = AlgorithmFactory.get_algorithm(Algorithm.ROUND_ROBIN, mock_instances)
    assert isinstance(algorithm, RoundRobinAlgorithm)


def test_get_ip_hash_algorithm(mock_instances):
    """Test that the factory returns an IpHashAlgorithm instance"""
    client_ip = "192.168.1.1"
    algorithm = AlgorithmFactory.get_algorithm(Algorithm.IP_HASH, mock_instances, client_ip)
    assert isinstance(algorithm, IpHashAlgorithm)
    assert algorithm.client_ip == client_ip


def test_get_least_connection_algorithm(mock_instances):
    """Test that the factory returns a LeastConnectionAlgorithm instance"""
    algorithm = AlgorithmFactory.get_algorithm(Algorithm.LEAST_CONNECTION, mock_instances)
    assert isinstance(algorithm, LeastConnectionAlgorithm)


def test_get_weighted_round_robin_algorithm(mock_instances):
    """Test that the factory returns a WeightedRoundRobinAlgorithm instance"""
    algorithm = AlgorithmFactory.get_algorithm(Algorithm.WEIGHTED_ROUND_ROBIN, mock_instances)
    assert isinstance(algorithm, WeightedRoundRobinAlgorithm)


def test_algorithm_factory_with_invalid_algorithm(mock_instances):
    """Test that the factory raises a ValueError for invalid algorithms"""
    with pytest.raises(ValueError, match="Algorithm 'invalid' not supported"):
        AlgorithmFactory.get_algorithm("invalid", mock_instances)


def test_algorithm_factory_with_no_client_ip(mock_instances):
    """Test that the factory raises a ValueError when no client IP is provided for IP Hash algorithm"""
    with pytest.raises(ValueError, match="Client IP is required for IP Hash algorithm"):
        AlgorithmFactory.get_algorithm(Algorithm.IP_HASH, mock_instances) 