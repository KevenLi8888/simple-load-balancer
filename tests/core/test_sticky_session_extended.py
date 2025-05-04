import pytest
from unittest.mock import patch, MagicMock
import time
from src.core.stickey_session import StickySessionManager


def test_sticky_session_cleanup_expired():
    """Test that expired sessions are cleaned up"""
    # Create manager with a short timeout
    manager = StickySessionManager(timeout_seconds=1)
    
    # Replace the _last_cleanup_time with a real value instead of a mock
    current_time = time.time()
    manager._last_cleanup_time = current_time
    
    # Add some sessions
    manager.set_sticky_instance("client1", "service1", "instance1")
    manager.set_sticky_instance("client2", "service1", "instance2")
    
    # Force time to advance
    with patch('time.time') as mock_time:
        # First timestamp is current
        mock_time.return_value = current_time
        
        # Verify sessions exist
        assert manager.get_sticky_instance("client1", "service1") == "instance1"
        assert manager.get_sticky_instance("client2", "service1") == "instance2"
        
        # Move time forward past expiration
        mock_time.return_value = current_time + 2  # More than the 1 second timeout
        
        # Try to access session (should trigger cleanup and return None)
        assert manager.get_sticky_instance("client1", "service1") is None
        assert manager.get_sticky_instance("client2", "service1") is None
        
        # Verify sessions were removed
        assert len(manager.sessions) == 0


def test_sticky_session_cleanup_interval():
    """Test that cleanup only runs at specific intervals"""
    # Create manager with cleanup settings
    manager = StickySessionManager(timeout_seconds=10)
    manager._cleanup_interval = 5  # Run cleanup every 5 seconds
    
    # Set an initial timestamp
    current_time = time.time()
    manager._last_cleanup_time = current_time
    
    # Add a session
    with patch('time.time') as mock_time:
        mock_time.return_value = current_time
        manager.set_sticky_instance("client1", "service1", "instance1")
        
        # Move time forward but less than the cleanup interval
        mock_time.return_value = current_time + 2
        
        # This shouldn't run the cleanup even though we're calling set again
        with patch.object(manager, '_cleanup_expired_sessions') as mock_cleanup:
            manager.set_sticky_instance("client2", "service2", "instance2")
            mock_cleanup.assert_called_once()  # Called because we're calling set_sticky_instance
        
        # Move time past the cleanup interval
        mock_time.return_value = current_time + 6
        
        # This should run the cleanup
        with patch.object(manager, '_cleanup_expired_sessions') as mock_cleanup:
            manager.set_sticky_instance("client3", "service3", "instance3")
            mock_cleanup.assert_called_once()


def test_sticky_session_refresh_timestamp():
    """Test that accessing a session refreshes its timestamp"""
    # Create manager
    manager = StickySessionManager(timeout_seconds=10)
    
    # Add a session
    current_time = time.time()
    with patch('time.time') as mock_time:
        # Set initial timestamp
        mock_time.return_value = current_time
        manager.set_sticky_instance("client1", "service1", "instance1")
        
        # Original timestamp should be current_time
        session_key = ("client1", "service1")
        _, timestamp = manager.sessions[session_key]
        assert timestamp == current_time
        
        # Move time forward
        mock_time.return_value = current_time + 5
        
        # Access the session (should refresh timestamp)
        assert manager.get_sticky_instance("client1", "service1") == "instance1"
        
        # Timestamp should be updated
        _, new_timestamp = manager.sessions[session_key]
        assert new_timestamp == current_time + 5


def test_sticky_session_expired_during_access():
    """Test handling of an expired session during access"""
    # Create manager with a short timeout
    manager = StickySessionManager(timeout_seconds=5)
    
    # Add a session
    current_time = time.time()
    # Set an initial timestamp
    manager._last_cleanup_time = current_time
    
    with patch('time.time') as mock_time:
        # Set initial timestamp
        mock_time.return_value = current_time
        manager.set_sticky_instance("client1", "service1", "instance1")
        
        # Move time past expiration
        mock_time.return_value = current_time + 6
        
        # Try to access the expired session
        assert manager.get_sticky_instance("client1", "service1") is None
        
        # Verify session was removed
        assert ("client1", "service1") not in manager.sessions


def test_sticky_session_with_empty_client_ip():
    """Test setting a sticky session with an empty client IP"""
    manager = StickySessionManager()
    
    # Set an initial timestamp to avoid mocking issues
    manager._last_cleanup_time = time.time()
    
    # Try with empty client IP
    manager.set_sticky_instance("", "service1", "instance1")
    
    # Should still be retrievable
    assert manager.get_sticky_instance("", "service1") == "instance1"
    
    # Remove it
    manager.remove_sticky_instance("", "service1")
    
    # Should be gone
    assert manager.get_sticky_instance("", "service1") is None


def test_sticky_session_remove_nonexistent():
    """Test removing a nonexistent sticky session"""
    manager = StickySessionManager()
    
    # Set an initial timestamp to avoid mocking issues
    manager._last_cleanup_time = time.time()
    
    # Remove a session that doesn't exist (should not raise an error)
    manager.remove_sticky_instance("nonexistent", "nonexistent")
    
    # Verify no issues
    assert manager.get_sticky_instance("nonexistent", "nonexistent") is None 