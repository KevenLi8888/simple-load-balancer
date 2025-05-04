import threading
import time
import requests
import logging
from typing import Dict
from src.db import collections as db
from src.db.models import Instance, InstanceStatus

class HealthChecker(threading.Thread):
    def __init__(self, interval: int = 5, timeout: int = 2, retries: int = 3):
        super().__init__(daemon=True)  # Run as daemon thread
        self.interval = interval
        self.timeout = timeout
        self.retries = retries
        self.logger = logging.getLogger(__name__)
        self._stop_event = threading.Event()
        self._failed_checks: Dict[str, int] = {}  # instance_id -> failure count

    def stop(self):
        """Stop the health checker thread."""
        self._stop_event.set()

    def run(self):
        """Main health check loop."""
        while not self._stop_event.is_set():
            try:
                self._check_all_instances()
            except Exception as e:
                self.logger.error(f"Error in health check loop: {str(e)}")
            finally:
                # Sleep for the interval period
                time.sleep(self.interval)

    def _check_all_instances(self):
        """Check health of all instances."""
        instances = db.get_all_services()
        for service in instances:
            service_instances = db.get_instances_by_service(service.id)
            for instance in service_instances:
                self._check_instance(instance)

    def _check_instance(self, instance: Instance):
        """Check health of a single instance by making a request to the root path."""
        url = f"http://{instance.addr}/"  # Use root path instead of /health
        is_healthy = False

        for _ in range(self.retries):
            try:
                response = requests.get(url, timeout=self.timeout)
                # Any response means the instance is healthy, regardless of status code
                is_healthy = True
                self.logger.debug(f"Health check passed for {instance.addr} with status {response.status_code}")
                break
            except requests.RequestException as e:
                self.logger.warning(f"Health check failed for {instance.addr}: {str(e)}")
                time.sleep(1)  # Brief pause between retries

        # Update instance status if it changed
        new_status = InstanceStatus.HEALTHY if is_healthy else InstanceStatus.UNHEALTHY
        if new_status != instance.status:
            try:
                db.update_instance_status(instance.id, new_status)
                if new_status == InstanceStatus.UNHEALTHY:
                    self.logger.warning(f"Instance {instance.addr} marked as unhealthy")
                else:
                    self.logger.info(f"Instance {instance.addr} marked as healthy")
            except Exception as e:
                self.logger.error(f"Error updating instance status: {str(e)}")

    def mark_unhealthy(self, instance_id: str):
        """Manually mark an instance as unhealthy, e.g., after a failed request."""
        try:
            db.update_instance_status(instance_id, InstanceStatus.UNHEALTHY)
            self.logger.warning(f"Instance {instance_id} manually marked as unhealthy")
        except Exception as e:
            self.logger.error(f"Error marking instance as unhealthy: {str(e)}")