import pytest
from unittest.mock import MagicMock, patch
from flask import Response
from src.core.balancer import LoadBalancer
from src.db.models import InstanceStatus


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


def test_route_request_missing_host_header(load_balancer, mock_request):
    """Test that the balancer returns a 400 error when Host header is missing"""
    # Remove the Host header
    mock_request.headers = {}
    
    response = load_balancer.route_request(mock_request, "")
    
    assert response.status_code == 400
    assert "Missing Host header" in response.get_data(as_text=True)


def test_route_request_service_not_found(load_balancer, mock_request, db_mock):
    """Test that the balancer returns a 404 when the service is not found"""
    # Configure the DB mock to not find a service
    db_mock.get_service_by_header.return_value = None
    
    response = load_balancer.route_request(mock_request, "")
    
    assert response.status_code == 404
    assert "No service found for host" in response.get_data(as_text=True)


def test_route_request_no_healthy_instances(load_balancer, mock_request, db_mock, mock_service):
    """Test that the balancer returns a 503 when no healthy instances are available"""
    # Configure the DB mock to find a service but no healthy instances
    db_mock.get_service_by_header.return_value = mock_service
    db_mock.get_instances_by_service.return_value = []
    
    response = load_balancer.route_request(mock_request, "")
    
    assert response.status_code == 503
    assert "No healthy instances available" in response.get_data(as_text=True)


def test_route_request_success(load_balancer, mock_request, db_mock, mock_service, mock_instances):
    """Test a successful request routing"""
    # Configure the DB mock
    db_mock.get_service_by_header.return_value = mock_service
    db_mock.get_instances_by_service.return_value = mock_instances
    
    # Configure the proxy mock to return a successful response
    success_response = Response("Success", status=200)
    load_balancer._mock_proxy.forward_request.return_value = success_response
    
    # Route the request
    response = load_balancer.route_request(mock_request, "api/test")
    
    # Check that the proxy was called correctly
    load_balancer._mock_proxy.forward_request.assert_called_once()
    
    # Verify the response
    assert response.status_code == 200
    assert response.get_data(as_text=True) == "Success"


def test_route_request_with_sticky_session(load_balancer, mock_request, db_mock, mock_service, mock_instances):
    """Test routing with sticky sessions enabled"""
    # Enable sticky sessions on the service
    mock_service.stateful = True
    
    # Configure the DB mock
    db_mock.get_service_by_header.return_value = mock_service
    db_mock.get_instances_by_service.return_value = mock_instances
    
    # Configure sticky session mock
    load_balancer._mock_sticky.get_sticky_instance.return_value = None
    
    # Configure the proxy mock to return a successful response
    success_response = Response("Success", status=200)
    load_balancer._mock_proxy.forward_request.return_value = success_response
    
    # Route the request
    response = load_balancer.route_request(mock_request, "api/test")
    
    # Check that sticky session was set after successful request
    load_balancer._mock_sticky.set_sticky_instance.assert_called_once()
    
    # Verify the response
    assert response.status_code == 200


def test_route_request_with_existing_sticky_session(load_balancer, mock_request, db_mock, mock_service, mock_instances):
    """Test routing with an existing sticky session"""
    # Enable sticky sessions on the service
    mock_service.stateful = True
    
    # Configure the DB mock
    db_mock.get_service_by_header.return_value = mock_service
    db_mock.get_instances_by_service.return_value = mock_instances
    
    # Configure sticky session mock to return an existing sticky instance
    sticky_instance_id = mock_instances[0].id
    load_balancer._mock_sticky.get_sticky_instance.return_value = sticky_instance_id
    
    # Configure the proxy mock to return a successful response
    success_response = Response("Success", status=200)
    load_balancer._mock_proxy.forward_request.return_value = success_response
    
    # Route the request
    response = load_balancer.route_request(mock_request, "api/test")
    
    # Verify the response
    assert response.status_code == 200
    
    # Check that the proxy forwarded to the sticky instance
    args, _ = load_balancer._mock_proxy.forward_request.call_args
    selected_instance = args[1]
    assert selected_instance.id == sticky_instance_id 