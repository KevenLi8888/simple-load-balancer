import pytest
from src.algorithms.ip_hash import IpHashAlgorithm
from src.db.models import Instance, InstanceStatus


def test_ip_hash_consistent_selection(mock_instances):
    """Test that IP hash algorithm consistently selects the same instance for the same IP"""
    client_ip = "192.168.1.1"
    algorithm = IpHashAlgorithm(mock_instances, client_ip)
    
    # Select an instance multiple times
    first_selection = algorithm.select_instance()
    for _ in range(10):
        # Should consistently select the same instance for the same IP
        assert algorithm.select_instance().id == first_selection.id


def test_ip_hash_different_ips(mock_instances):
    """Test that different IPs might select different instances"""
    # Use a set of IPs with known different hash outcomes
    ips = ["192.168.1.1", "10.0.0.1", "172.16.0.1"]
    
    # Keep track of selected instances for each IP
    ip_to_instance = {}
    
    # Test with different IPs
    for ip in ips:
        algorithm = IpHashAlgorithm(mock_instances, ip)
        ip_to_instance[ip] = algorithm.select_instance().id
    
    # We can't guarantee all IPs will select different instances due to the hash nature,
    # but we can check that the selection is deterministic per IP
    for ip in ips:
        algorithm = IpHashAlgorithm(mock_instances, ip)
        assert algorithm.select_instance().id == ip_to_instance[ip]


def test_ip_hash_with_empty_instances():
    """Test that IP hash raises ValueError with empty instances"""
    algorithm = IpHashAlgorithm([], "192.168.1.1")
    
    with pytest.raises(ValueError, match="No instances available"):
        algorithm.select_instance()


def test_ip_hash_with_empty_ip():
    """Test that IP hash raises ValueError with an empty IP string"""
    instances = [
        Instance(
            id="instance1",
            service_id="service123",
            addr="127.0.0.1:8001",
            weight=1,
            status=InstanceStatus.HEALTHY,
            connections=0
        )
    ]
    
    # Empty IP should raise a ValueError
    with pytest.raises(ValueError, match="Client IP is required for IP Hash algorithm"):
        algorithm = IpHashAlgorithm(instances, "") 