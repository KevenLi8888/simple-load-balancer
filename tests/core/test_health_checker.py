import pytest
import time
from unittest.mock import patch, MagicMock
from src.core.health_checker import HealthChecker
from src.db.models import InstanceStatus, Service, Instance
import requests


@pytest.fixture
def mock_services():
    """Returns a list of mock services for testing health checks"""
    service = Service(
        id="service123",
        name="test-service",
        domain="test.example.com",
        algorithm="round_robin",
        stateful=False
    )
    return [service]


@pytest.fixture
def mock_service_instances():
    """Mock service instances for health check testing"""
    return [
        Instance(
            id=f"instance{i}",
            service_id="service123",
            addr=f"127.0.0.1:{8000+i}",
            weight=1,
            status=InstanceStatus.HEALTHY,
            connections=0
        )
        for i in range(2)
    ]


def test_health_checker_init():
    """Test initializing the health checker with custom parameters"""
    checker = HealthChecker(interval=10, timeout=3, retries=2)
    assert checker.interval == 10
    assert checker.timeout == 3
    assert checker.retries == 2


def test_health_checker_check_instance_healthy():
    """Test checking a healthy instance"""
    with patch('src.core.health_checker.requests.get') as mock_get, \
         patch('src.core.health_checker.db') as mock_db:
        
        # Configure the mock response
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_get.return_value = mock_response
        
        # Configure instance
        instance = Instance(
            id="instance1",
            service_id="service123",
            addr="127.0.0.1:8001",
            weight=1,
            status=InstanceStatus.HEALTHY,
            connections=0
        )
        
        # Create checker and test instance check
        checker = HealthChecker(interval=5, timeout=2, retries=1)
        checker._check_instance(instance)
        
        # Verify that requests.get was called with the right URL
        mock_get.assert_called_once_with(
            'http://127.0.0.1:8001/', 
            timeout=2
        )
        
        # Verify that instance status was not changed
        mock_db.update_instance_status.assert_not_called()


def test_health_checker_check_instance_unhealthy():
    """Test checking an unhealthy instance"""
    with patch('src.core.health_checker.requests.get') as mock_get, \
         patch('src.core.health_checker.db') as mock_db:
        
        # Configure mock to raise requests.RequestException (not a generic Exception)
        mock_get.side_effect = requests.RequestException("Connection refused")
        
        # Configure instance
        instance = Instance(
            id="instance1",
            service_id="service123",
            addr="127.0.0.1:8001",
            weight=1,
            status=InstanceStatus.HEALTHY,  # Start as healthy
            connections=0
        )
        
        # Create checker and test instance check
        checker = HealthChecker(interval=5, timeout=2, retries=3)
        checker._check_instance(instance)
        
        # Verify request attempts
        assert mock_get.call_count == 3  # Should retry 3 times
        
        # Verify instance was marked as unhealthy
        mock_db.update_instance_status.assert_called_once_with(
            instance.id,
            InstanceStatus.UNHEALTHY
        )


def test_health_checker_no_status_change():
    """Test that health status doesn't change if status matches check result"""
    with patch('src.core.health_checker.requests.get') as mock_get, \
         patch('src.core.health_checker.db') as mock_db:
        
        # Unhealthy instance stays unhealthy
        mock_get.side_effect = requests.RequestException("Connection refused")
        
        instance = Instance(
            id="instance1",
            service_id="service123",
            addr="127.0.0.1:8001",
            weight=1,
            status=InstanceStatus.UNHEALTHY,  # Already unhealthy
            connections=0
        )
        
        checker = HealthChecker(interval=5, timeout=2, retries=3)
        checker._check_instance(instance)
        
        # Status should not be updated since it's already unhealthy
        mock_db.update_instance_status.assert_not_called()


def test_health_checker_check_all_instances():
    """Test checking all instances across services"""
    with patch('src.core.health_checker.db') as mock_db, \
         patch.object(HealthChecker, '_check_instance') as mock_check_instance:
        
        # Configure mock data
        mock_services = [
            Service(id="service1", name="Service 1", header="s1.example.com", domain="s1.example.com", algorithm="round_robin", stateful=False),
            Service(id="service2", name="Service 2", header="s2.example.com", domain="s2.example.com", algorithm="round_robin", stateful=False)
        ]
        
        mock_instances = {
            "service1": [
                Instance(id="instance1", service_id="service1", addr="127.0.0.1:8001", weight=1, status=InstanceStatus.HEALTHY, connections=0),
                Instance(id="instance2", service_id="service1", addr="127.0.0.1:8002", weight=1, status=InstanceStatus.HEALTHY, connections=0)
            ],
            "service2": [
                Instance(id="instance3", service_id="service2", addr="127.0.0.1:8003", weight=1, status=InstanceStatus.HEALTHY, connections=0)
            ]
        }
        
        # Configure the mocks
        mock_db.get_all_services.return_value = mock_services
        mock_db.get_instances_by_service.side_effect = lambda service_id: mock_instances.get(service_id, [])
        
        # Run health checks
        checker = HealthChecker(interval=5, timeout=2, retries=1)
        checker._check_all_instances()
        
        # Verify that _check_instance was called for each instance
        assert mock_check_instance.call_count == 3  # Total instances across all services
        
        # Verify the instances passed to _check_instance
        calls = mock_check_instance.call_args_list
        assert calls[0][0][0].id == "instance1"
        assert calls[1][0][0].id == "instance2"
        assert calls[2][0][0].id == "instance3" 