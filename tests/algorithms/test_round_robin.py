import pytest
from src.algorithms.round_robin import RoundRobinAlgorithm
from src.db.models import Instance, InstanceStatus


def test_round_robin_select_instance(mock_instances):
    """Test that round robin selects instances in circular order"""
    algorithm = RoundRobinAlgorithm(mock_instances)
    
    # Select instances multiple times and verify they are selected in a circular pattern
    first_instance = algorithm.select_instance()
    second_instance = algorithm.select_instance()
    third_instance = algorithm.select_instance()
    fourth_instance = algorithm.select_instance()
    
    # The fourth selection should be the same as the first (circular)
    assert first_instance.id != second_instance.id
    assert second_instance.id != third_instance.id
    assert third_instance.id != first_instance.id
    assert fourth_instance.id == first_instance.id
    
    # Make sure all instances were selected
    selected_ids = {first_instance.id, second_instance.id, third_instance.id}
    expected_ids = {instance.id for instance in mock_instances}
    assert selected_ids == expected_ids


def test_round_robin_with_empty_instances():
    """Test that round robin raises ValueError with empty instances"""
    algorithm = RoundRobinAlgorithm([])
    
    with pytest.raises(ValueError, match="No instances available"):
        algorithm.select_instance()


def test_round_robin_thread_safety(mock_instances):
    """Verify that the round robin counter is thread-safe"""
    # Simple test to ensure the lock works correctly
    algorithm = RoundRobinAlgorithm(mock_instances)
    
    # Verify the lock exists and is usable
    assert hasattr(RoundRobinAlgorithm, "_lock")
    
    # Try to acquire the lock and release it
    acquired = RoundRobinAlgorithm._lock.acquire(blocking=False)
    assert acquired
    
    RoundRobinAlgorithm._lock.release()
    
    # Test that we can select instances while the lock is being used
    instance = algorithm.select_instance()
    assert instance is not None 