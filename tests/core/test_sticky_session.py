import pytest
from src.core.stickey_session import StickySessionManager


def test_sticky_session_initialization():
    """Test that the StickySessionManager initializes correctly"""
    manager = StickySessionManager()
    assert hasattr(manager, 'sessions')
    assert isinstance(manager.sessions, dict)
    assert len(manager.sessions) == 0


def test_set_and_get_sticky_instance():
    """Test setting and retrieving a sticky session mapping"""
    manager = StickySessionManager()
    
    client_ip = "192.168.1.1"
    service_id = "service123"
    instance_id = "instance456"
    
    # Initially should return None
    assert manager.get_sticky_instance(client_ip, service_id) is None
    
    # Set the sticky instance
    manager.set_sticky_instance(client_ip, service_id, instance_id)
    
    # Now should return the instance id
    assert manager.get_sticky_instance(client_ip, service_id) == instance_id


def test_remove_sticky_instance():
    """Test removing a sticky session mapping"""
    manager = StickySessionManager()
    
    client_ip = "192.168.1.1"
    service_id = "service123"
    instance_id = "instance456"
    
    # Set the sticky instance
    manager.set_sticky_instance(client_ip, service_id, instance_id)
    assert manager.get_sticky_instance(client_ip, service_id) == instance_id
    
    # Remove the mapping
    manager.remove_sticky_instance(client_ip, service_id)
    
    # Now should return None
    assert manager.get_sticky_instance(client_ip, service_id) is None


def test_multiple_clients_and_services():
    """Test handling multiple client IPs and services"""
    manager = StickySessionManager()
    
    # Define test data
    mappings = [
        ("192.168.1.1", "service1", "instance1"),
        ("192.168.1.1", "service2", "instance2"),  # Same client, different service
        ("10.0.0.5", "service1", "instance3")      # Different client, same service
    ]
    
    # Set all mappings
    for client_ip, service_id, instance_id in mappings:
        manager.set_sticky_instance(client_ip, service_id, instance_id)
    
    # Verify all mappings
    for client_ip, service_id, instance_id in mappings:
        assert manager.get_sticky_instance(client_ip, service_id) == instance_id
    
    # Remove one mapping and verify it's gone but others remain
    manager.remove_sticky_instance("192.168.1.1", "service1")
    assert manager.get_sticky_instance("192.168.1.1", "service1") is None
    assert manager.get_sticky_instance("192.168.1.1", "service2") == "instance2"
    assert manager.get_sticky_instance("10.0.0.5", "service1") == "instance3"


def test_sticky_session_with_empty_values():
    """Test behavior with empty or None values"""
    manager = StickySessionManager()
    
    # Set with empty client IP (should still work)
    manager.set_sticky_instance("", "service1", "instance1")
    assert manager.get_sticky_instance("", "service1") == "instance1"
    
    # Try to get with None values (should handle gracefully)
    assert manager.get_sticky_instance(None, "service1") is None
    assert manager.get_sticky_instance("192.168.1.1", None) is None
    
    # Try to remove with None values (should not raise errors)
    manager.remove_sticky_instance(None, "service1")
    manager.remove_sticky_instance("192.168.1.1", None) 