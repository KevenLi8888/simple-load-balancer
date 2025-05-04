import pytest
from unittest.mock import MagicMock, patch, call
from flask import Response, Request
from src.core.balancer import LoadBalancer
from src.db.models import InstanceStatus, Service, Algorithm, Instance


@pytest.fixture
def load_balancer():
    """Creates a LoadBalancer with mocked components"""
    with patch('src.core.balancer.ProxyHandler') as mock_proxy_handler, \
         patch('src.core.balancer.StickySessionManager') as mock_sticky_session_manager, \
         patch('src.core.balancer.get_config') as mock_get_config:
        
        # Configure mocks
        mock_get_config.return_value = {'lb': {'timeout': 10}}
        mock_proxy = mock_proxy_handler.return_value
        mock_sticky = mock_sticky_session_manager.return_value
        
        # Create balancer
        balancer = LoadBalancer()
        
        # Store mocks for test access
        balancer._mock_proxy = mock_proxy
        balancer._mock_sticky = mock_sticky
        
        yield balancer


@pytest.fixture
def db_mock():
    """Mock the database module for the balancer"""
    with patch('src.core.balancer.db') as mock_db:
        yield mock_db


@pytest.fixture
def healthy_instances():
    """Create a list of healthy instances"""
    return [
        Instance(
            id=f"instance{i}",
            service_id="service123",
            addr=f"127.0.0.1:{8000+i}",
            weight=1,
            status=InstanceStatus.HEALTHY,
            connections=i
        )
        for i in range(3)
    ]


def test_route_with_retries_all_instances_fail(load_balancer, mock_request, db_mock, mock_service, healthy_instances):
    """Test the retry logic when all instances fail"""
    # Configure the proxy mock to raise exceptions for all instances
    load_balancer._mock_proxy.forward_request.side_effect = Exception("Connection refused")
    
    # Configure exception handling
    db_mock.update_instance_status = MagicMock()
    
    # Call _route_with_retries directly
    response = load_balancer._route_with_retries(
        mock_request,
        mock_service,
        healthy_instances,
        "192.168.1.1",
        "/api/test"
    )
    
    # Check the response
    assert response.status_code == 503
    assert "All instances failed" in response.get_data(as_text=True)
    
    # Check that update_instance_status was called for each instance
    assert db_mock.update_instance_status.call_count == 3
    assert all(call(instance.id, InstanceStatus.UNHEALTHY) in db_mock.update_instance_status.call_args_list 
              for instance in healthy_instances)


def test_route_with_retries_first_fails_second_succeeds(load_balancer, mock_request, db_mock, mock_service, healthy_instances):
    """Test the retry logic when the first instance fails but the second succeeds"""
    # Configure the proxy mock to fail for the first instance but succeed for others
    def side_effect(req, instance, path):
        if instance.id == "instance0":
            raise Exception("Connection refused")
        return Response("Success", status=200)
    
    load_balancer._mock_proxy.forward_request.side_effect = side_effect
    
    # Mock algorithm to consistently return the first instance first, then second
    with patch('src.core.balancer.AlgorithmFactory') as mock_factory:
        mock_algorithm = MagicMock()
        # Return instances in order (first call returns instance0, second call returns instance1)
        mock_algorithm.select_instance.side_effect = [healthy_instances[0], healthy_instances[1]]
        mock_factory.get_algorithm.return_value = mock_algorithm
        
        # Configure exception handling
        db_mock.update_instance_status = MagicMock()
        
        # Call _route_with_retries directly
        response = load_balancer._route_with_retries(
            mock_request,
            mock_service,
            healthy_instances,
            "192.168.1.1",
            "/api/test"
        )
        
        # Check the response
        assert response.status_code == 200
        assert response.get_data(as_text=True) == "Success"
        
        # Check that update_instance_status was called for the failed instance
        db_mock.update_instance_status.assert_called_with("instance0", InstanceStatus.UNHEALTHY)


def test_route_with_retries_with_sticky_session_failure(load_balancer, mock_request, db_mock, mock_service, healthy_instances):
    """Test the retry logic with sticky sessions when the sticky instance fails"""
    # Enable sticky sessions
    mock_service.stateful = True
    
    # Set up a sticky session
    load_balancer._mock_sticky.get_sticky_instance.return_value = "instance0"
    
    # Configure the proxy mock to fail
    load_balancer._mock_proxy.forward_request.side_effect = Exception("Connection refused")
    
    # Configure exception handling
    db_mock.update_instance_status = MagicMock()
    
    # Call _route_with_retries directly
    load_balancer._route_with_retries(
        mock_request,
        mock_service,
        healthy_instances,
        "192.168.1.1",
        "/api/test"
    )
    
    # Verify that the sticky session was removed
    load_balancer._mock_sticky.remove_sticky_instance.assert_called_with("192.168.1.1", "service123")


def test_get_client_ip_with_x_forwarded_for(load_balancer):
    """Test extracting client IP from X-Forwarded-For header"""
    request = MagicMock(spec=Request)
    request.headers = {'X-Forwarded-For': '203.0.113.195, 70.41.3.18, 150.172.238.178'}
    request.remote_addr = '127.0.0.1'
    
    client_ip = load_balancer._get_client_ip(request)
    
    assert client_ip == '203.0.113.195'


def test_get_client_ip_with_x_real_ip(load_balancer):
    """Test extracting client IP from X-Real-IP header"""
    request = MagicMock(spec=Request)
    request.headers = {'X-Real-IP': '203.0.113.195'}
    request.remote_addr = '127.0.0.1'
    
    client_ip = load_balancer._get_client_ip(request)
    
    assert client_ip == '203.0.113.195'


def test_get_client_ip_fallback_to_remote_addr(load_balancer):
    """Test falling back to remote_addr when no proxy headers are present"""
    request = MagicMock(spec=Request)
    request.headers = {}
    request.remote_addr = '127.0.0.1'
    
    client_ip = load_balancer._get_client_ip(request)
    
    assert client_ip == '127.0.0.1'


def test_get_client_ip_fallback_to_default(load_balancer):
    """Test falling back to default IP when no IP information is available"""
    request = MagicMock(spec=Request)
    request.headers = {}
    request.remote_addr = None
    
    client_ip = load_balancer._get_client_ip(request)
    
    assert client_ip == '0.0.0.0'


def test_select_instance_with_sticky_session(load_balancer, mock_service, healthy_instances):
    """Test instance selection with a sticky session"""
    # Enable sticky sessions
    mock_service.stateful = True
    
    # Set up a sticky session for the second instance
    load_balancer._mock_sticky.get_sticky_instance.return_value = "instance1"
    
    # Call _select_instance directly
    instance = load_balancer._select_instance(mock_service, healthy_instances, "192.168.1.1")
    
    # Verify the selected instance
    assert instance.id == "instance1"


def test_select_instance_sticky_session_not_in_available_instances(load_balancer, mock_service, healthy_instances):
    """Test instance selection when the sticky instance is not in the available instances"""
    # Enable sticky sessions
    mock_service.stateful = True
    
    # Set up a sticky session for an instance that's not in the list
    load_balancer._mock_sticky.get_sticky_instance.return_value = "instance99"
    
    # Mock the algorithm factory
    with patch('src.core.balancer.AlgorithmFactory') as mock_factory:
        mock_algorithm = MagicMock()
        mock_algorithm.select_instance.return_value = healthy_instances[0]
        mock_factory.get_algorithm.return_value = mock_algorithm
        
        # Call _select_instance directly
        instance = load_balancer._select_instance(mock_service, healthy_instances, "192.168.1.1")
        
        # Verify the sticky session was removed
        load_balancer._mock_sticky.remove_sticky_instance.assert_called_once_with("192.168.1.1", "service123")
        
        # Verify the fallback to algorithm
        mock_factory.get_algorithm.assert_called_once()
        
        # Verify the selected instance
        assert instance == healthy_instances[0]


def test_select_instance_no_sticky_session(load_balancer, mock_service, healthy_instances):
    """Test instance selection without a sticky session"""
    # Disable sticky sessions
    mock_service.stateful = False
    
    # Mock the algorithm factory
    with patch('src.core.balancer.AlgorithmFactory') as mock_factory:
        mock_algorithm = MagicMock()
        mock_algorithm.select_instance.return_value = healthy_instances[0]
        mock_factory.get_algorithm.return_value = mock_algorithm
        
        # Call _select_instance directly
        instance = load_balancer._select_instance(mock_service, healthy_instances, "192.168.1.1")
        
        # Verify the algorithm was used
        mock_factory.get_algorithm.assert_called_once_with(
            mock_service.algorithm,
            healthy_instances,
            "192.168.1.1"
        )
        
        # Verify the selected instance
        assert instance == healthy_instances[0]


def test_select_instance_with_exception(load_balancer, mock_service, healthy_instances):
    """Test instance selection when an exception occurs"""
    # Mock the algorithm factory to raise an exception
    with patch('src.core.balancer.AlgorithmFactory') as mock_factory:
        mock_factory.get_algorithm.side_effect = Exception("Algorithm error")
        
        # Call _select_instance directly
        instance = load_balancer._select_instance(mock_service, healthy_instances, "192.168.1.1")
        
        # Verify None is returned when an exception occurs
        assert instance is None


def test_route_request_with_exception(load_balancer, mock_request):
    """Test handling of unexpected exceptions in the route_request method"""
    # Mock an exception in the database call
    with patch('src.core.balancer.db.get_service_by_header') as mock_get_service:
        mock_get_service.side_effect = Exception("Unexpected database error")
        
        # Call route_request
        response = load_balancer.route_request(mock_request, "/api/test")
        
        # Verify the response
        assert response.status_code == 500
        assert "Internal server error" in response.get_data(as_text=True)


def test_handle_db_error_in_update_instance_status(load_balancer, mock_request, db_mock, mock_service, healthy_instances):
    """Test handling database errors when updating instance status"""
    # Configure the proxy mock to raise exceptions
    load_balancer._mock_proxy.forward_request.side_effect = Exception("Connection refused")
    
    # Configure the database error
    db_mock.update_instance_status.side_effect = Exception("Database error")
    
    # Call _route_with_retries directly
    response = load_balancer._route_with_retries(
        mock_request,
        mock_service,
        healthy_instances[:1],  # Just one instance to simplify
        "192.168.1.1",
        "/api/test"
    )
    
    # The method should handle the database error and continue
    assert response.status_code == 503
    assert "All instances failed" in response.get_data(as_text=True) 