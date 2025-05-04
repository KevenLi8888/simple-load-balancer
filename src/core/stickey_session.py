import time
from typing import Dict, Optional, Tuple

class StickySessionManager:
    def __init__(self, timeout_seconds: int = 300):
        # Store mapping: (client_ip, service_id) -> (instance_id, timestamp)
        self.sessions: Dict[Tuple[str, str], Tuple[str, float]] = {}
        self.timeout = timeout_seconds
        self._cleanup_interval = 60 # Run cleanup every 60 seconds
        self._last_cleanup_time = time.time()

    def get_sticky_instance(self, client_ip: str, service_id: str) -> Optional[str]:
        """Get the sticky instance ID for a client and service, if valid and not expired."""
        self._cleanup_expired_sessions()
        session_key = (client_ip, service_id)
        if session_key in self.sessions:
            instance_id, timestamp = self.sessions[session_key]
            if time.time() - timestamp < self.timeout:
                # Refresh timestamp on access
                self.sessions[session_key] = (instance_id, time.time())
                return instance_id
            else:
                # Session expired
                del self.sessions[session_key]
        return None

    def set_sticky_instance(self, client_ip: str, service_id: str, instance_id: str):
        """Set or update the sticky instance for a client and service."""
        session_key = (client_ip, service_id)
        self.sessions[session_key] = (instance_id, time.time())
        self._cleanup_expired_sessions() # Clean up periodically

    def remove_sticky_instance(self, client_ip: str, service_id: str):
        """Remove a specific sticky session mapping."""
        session_key = (client_ip, service_id)
        if session_key in self.sessions:
            del self.sessions[session_key]

    def _cleanup_expired_sessions(self):
        """Remove sessions that have exceeded the timeout."""
        now = time.time()
        # Avoid cleaning up too frequently
        if now - self._last_cleanup_time < self._cleanup_interval:
            return

        expired_keys = [
            key for key, (_, timestamp) in self.sessions.items()
            if now - timestamp >= self.timeout
        ]
        for key in expired_keys:
            del self.sessions[key]
        self._last_cleanup_time = now
