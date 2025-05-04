from flask import Request, Response
import logging
from typing import Optional, List
from src.algorithms.algorithm_factory import AlgorithmFactory
from src.db.models import Service, Instance, Algorithm, InstanceStatus
from src.core.proxy import ProxyHandler
from src.core.stickey_session import StickySessionManager
from src.db import collections as db
from src.utils.config import get_config
import copy

class LoadBalancer:
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        config = get_config().get('lb', {})
        self.proxy = ProxyHandler(timeout=config.get('timeout', 30))
        self.sticky_sessions = StickySessionManager()

    def route_request(self, client_request: Request, path: str) -> Response:
        """Route an incoming request to an appropriate backend instance."""
        try:
            # Extract the host header for service routing
            host_header = client_request.headers.get('Host')
            if not host_header:
                return Response("Missing Host header", status=400)

            # Get the service based on the host header
            service = db.get_service_by_header(host_header)
            if not service:
                return Response(f"No service found for host: {host_header}", status=404)

            # Get healthy instances for this service
            instances = self._get_healthy_instances(service.id)
            if not instances:
                return Response("No healthy instances available", status=503)

            # Get client IP for potential sticky session or algorithm
            client_ip = self._get_client_ip(client_request)

            # Attempt to route the request with retry logic
            return self._route_with_retries(client_request, service, instances, client_ip, path)

        except Exception as e:
            self.logger.error(f"Error routing request: {str(e)}")
            return Response("Internal server error", status=500)

    def _route_with_retries(self, client_request: Request, service: Service, 
                           instances: List[Instance], client_ip: str, path: str) -> Response:
        """Route a request with retry logic if instances fail."""
        # Make a copy of instances so we can remove failed ones
        available_instances = copy.copy(instances)
        tried_instances = set()
        last_error = None
        
        while available_instances:
            # Select instance using sticky session or load balancing algorithm
            instance = self._select_instance(service, available_instances, client_ip)
            if not instance or instance.id in tried_instances:
                # No new instance to try
                break
                
            tried_instances.add(instance.id)
            
            # Forward the request
            try:
                response = self.proxy.forward_request(client_request, instance, path)
                
                # If the request was successful and sticky sessions are enabled,
                # update the sticky session mapping
                if service.stateful and response.status_code < 500:
                    self.sticky_sessions.set_sticky_instance(client_ip, service.id, instance.id)
                    
                return response
            except Exception as e:
                last_error = e
                self.logger.warning(f"Request to instance {instance.id} failed: {str(e)}")
                
                # If sticky sessions are enabled, remove the mapping on failure
                if service.stateful:
                    self.sticky_sessions.remove_sticky_instance(client_ip, service.id)
                
                # Mark the instance as unhealthy
                try:
                    db.update_instance_status(instance.id, InstanceStatus.UNHEALTHY)
                    self.logger.info(f"Marked instance {instance.id} as unhealthy")
                except Exception as db_error:
                    self.logger.error(f"Failed to update instance status: {str(db_error)}")
                
                # Remove failed instance from available instances
                available_instances = [i for i in available_instances if i.id != instance.id]
                
                # Continue to retry with remaining instances
                if available_instances:
                    self.logger.info(f"Retrying with {len(available_instances)} other available instances")
                else:
                    self.logger.error("No more instances available for retry")
        
        error_msg = f"All instances failed to process the request: {str(last_error)}" if last_error else "All instances failed to process the request"
        return Response(error_msg, status=503)

    def _get_healthy_instances(self, service_id: str) -> List[Instance]:
        """Get all healthy instances for a service."""
        instances = db.get_instances_by_service(service_id)
        return [i for i in instances if i.status == InstanceStatus.HEALTHY]

    def _get_client_ip(self, request: Request) -> str:
        """Extract the client's real IP address from headers or remote address."""
        return (
            request.headers.get('X-Forwarded-For', '').split(',')[0].strip() or
            request.headers.get('X-Real-IP') or
            request.remote_addr or
            '0.0.0.0'
        )

    def _select_instance(self, service: Service, instances: List[Instance], client_ip: str) -> Optional[Instance]:
        """Select an instance using sticky session or the service's configured algorithm."""
        try:
            # First check for sticky session if enabled
            if service.stateful:
                sticky_instance_id = self.sticky_sessions.get_sticky_instance(client_ip, service.id)
                if sticky_instance_id:
                    # Find the sticky instance in our available instances
                    for instance in instances:
                        if instance.id == sticky_instance_id:
                            return instance
                    # If we get here, the sticky instance is no longer available
                    self.sticky_sessions.remove_sticky_instance(client_ip, service.id)

            # Fall back to regular load balancing algorithm
            algorithm = AlgorithmFactory.get_algorithm(
                service.algorithm,
                instances,
                client_ip
            )
            return algorithm.select_instance()
        except Exception as e:
            self.logger.error(f"Error selecting instance: {str(e)}")
            return None