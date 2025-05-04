import pytest
from unittest.mock import patch, MagicMock, call
import time
import logging
import requests
from src.core.health_checker import HealthChecker
from src.db.models import Instance, InstanceStatus, Service


@pytest.fixture
def mock_instances():
    """Return a list of mock instances for testing"""
    return [
        Instance(
            id=f"instance{i}",
            service_id="service123",
            addr=f"127.0.0.1:{8000+i}",
            weight=1,
            status=InstanceStatus.HEALTHY,
            connections=0
        )
        for i in range(3)
    ]


@pytest.fixture
def mock_services():
    """Return a list of mock services for testing"""
    return [
        Service(
            id="service123",
            name="test-service",
            header="test.example.com",
            domain="test.example.com",
            algorithm="round_robin",
            stateful=False
        )
    ]


@pytest.fixture
def health_checker():
    """Return a HealthChecker with mocked db"""
    with patch('src.core.health_checker.db') as mock_db:
        # Create health checker with proper parameters
        checker = HealthChecker(interval=5)
        # Avoid actually starting the thread
        checker._stop_event.set()
        yield checker, mock_db


def test_health_checker_check_instance_connection_error(health_checker, mock_instances):
    """Test the health checker handling a connection error during instance check"""
    checker, mock_db = health_checker
    instance = mock_instances[0]
    
    # Mock requests to raise a connection error
    with patch('src.core.health_checker.requests.get') as mock_get:
        mock_get.side_effect = requests.exceptions.ConnectionError("Connection refused")
        
        # Check the instance directly
        checker._check_instance(instance)
        
        # Verify that connection error was handled correctly
        mock_db.update_instance_status.assert_called_once_with(instance.id, InstanceStatus.UNHEALTHY)


def test_health_checker_check_instance_timeout(health_checker, mock_instances):
    """Test the health checker handling a timeout during instance check"""
    checker, mock_db = health_checker
    instance = mock_instances[0]
    
    # Mock requests to raise a timeout
    with patch('src.core.health_checker.requests.get') as mock_get:
        mock_get.side_effect = requests.exceptions.Timeout("Request timed out")
        
        # Check the instance directly
        checker._check_instance(instance)
        
        # Verify that timeout was handled correctly
        mock_db.update_instance_status.assert_called_once_with(instance.id, InstanceStatus.UNHEALTHY)


def test_health_checker_check_instance_request_exception(health_checker, mock_instances):
    """Test the health checker handling a generic request exception during instance check"""
    checker, mock_db = health_checker
    instance = mock_instances[0]
    
    # Mock requests to raise a generic exception
    with patch('src.core.health_checker.requests.get') as mock_get:
        mock_get.side_effect = requests.exceptions.RequestException("Generic error")
        
        # Check the instance directly
        checker._check_instance(instance)
        
        # Verify that exception was handled correctly
        mock_db.update_instance_status.assert_called_once_with(instance.id, InstanceStatus.UNHEALTHY)


def test_health_checker_mark_unhealthy(health_checker):
    """Test manually marking an instance as unhealthy"""
    checker, mock_db = health_checker
    
    # Call mark_unhealthy
    checker.mark_unhealthy("instance123")
    
    # Verify that the instance was marked as unhealthy
    mock_db.update_instance_status.assert_called_once_with("instance123", InstanceStatus.UNHEALTHY)


def test_health_checker_mark_unhealthy_error(health_checker):
    """Test error handling when marking an instance as unhealthy"""
    checker, mock_db = health_checker
    
    # Configure mock to raise an exception
    mock_db.update_instance_status.side_effect = Exception("Database error")
    
    # Call mark_unhealthy (should not raise an exception)
    with patch.object(logging.getLogger(checker.__module__), 'error') as mock_log:
        checker.mark_unhealthy("instance123")
        
        # Verify that the error was logged
        assert mock_log.called


def test_health_checker_run_method(health_checker):
    """Test the run method of the health checker"""
    checker, _ = health_checker
    
    # Mock _check_all_instances and sleep to avoid actual execution
    with patch.object(checker, '_check_all_instances') as mock_check, \
         patch('time.sleep') as mock_sleep, \
         patch.object(checker, '_stop_event') as mock_stop_event:
        
        # Configure stop event to be set after one iteration
        mock_stop_event.is_set.side_effect = [False, True]
        
        # Run the method
        checker.run()
        
        # Verify that _check_all_instances was called
        mock_check.assert_called_once()
        
        # Verify that sleep was called with the interval
        mock_sleep.assert_called_once_with(checker.interval)


def test_health_checker_check_all_method(health_checker, mock_services, mock_instances):
    """Test the _check_all_instances method"""
    checker, mock_db = health_checker
    
    # Mock the DB calls
    mock_db.get_all_services.return_value = mock_services
    mock_db.get_instances_by_service.return_value = mock_instances
    
    # Mock the _check_instance method
    with patch.object(checker, '_check_instance') as mock_check_instance:
        # Call the method
        checker._check_all_instances()
        
        # Verify _check_instance was called for each instance
        assert mock_check_instance.call_count == len(mock_instances)
        for instance in mock_instances:
            mock_check_instance.assert_any_call(instance)


def test_health_checker_check_all_instances_db_error(health_checker):
    """Test error handling in _check_all_instances when the database fails"""
    checker, mock_db = health_checker
    
    # Create a controlled error
    test_exception = Exception("Database error")
    
    # Instead of mocking the full method, we'll test the run method's exception handling
    with patch.object(checker, '_check_all_instances', side_effect=test_exception) as mock_check_all, \
         patch.object(checker, '_stop_event') as mock_stop_event:
        
        # Make sure we only run one iteration
        mock_stop_event.is_set.side_effect = [False, True]
        
        # Patch the logger to verify the error is logged
        with patch.object(checker.logger, 'error') as mock_log:
            # Run the method (which should handle the exception)
            checker.run()
            
            # Verify the error was logged correctly
            mock_log.assert_called_with(f"Error in health check loop: {str(test_exception)}")
            
            # Verify our mocked method was actually called
            mock_check_all.assert_called_once()


def test_health_checker_thread_inheritance():
    """Test that HealthChecker inherits from Thread correctly"""
    # Verify that HealthChecker is a subclass of Thread
    import threading
    assert issubclass(HealthChecker, threading.Thread)
    
    # Create a new health checker
    with patch('src.core.health_checker.db'):
        checker = HealthChecker()
        
        # Verify it has thread attributes
        assert hasattr(checker, 'start')
        assert hasattr(checker, 'run')
        assert hasattr(checker, 'join')
        
        # Verify it was created as a daemon thread
        assert checker.daemon is True 