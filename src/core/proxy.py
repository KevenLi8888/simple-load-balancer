import requests
from flask import Request, Response, stream_with_context
from typing import Dict, List, Tuple
import logging
from src.db.models import Instance

class ProxyHandler:
    def __init__(self, timeout: int = 30):
        self.timeout = timeout
        self.logger = logging.getLogger(__name__)

    def forward_request(self, client_request: Request, instance: Instance, path: str) -> Response:
        """Forward the request to the selected backend instance."""
        url = f"http://{instance.addr}/{path.lstrip('/')}"
        
        # Prepare headers - exclude hop-by-hop headers
        headers = self._prepare_headers(dict(client_request.headers), instance)
        
        try:
            # Forward the request to the backend
            response = requests.request(
                method=client_request.method,
                url=url,
                headers=headers,
                data=client_request.get_data(),
                cookies=client_request.cookies,
                timeout=self.timeout,
                stream=True  # Enable streaming for large responses
            )
            
            # Prepare response headers
            response_headers = self._prepare_response_headers(response.raw.headers)
            
            # Stream the response back to the client
            return Response(
                stream_with_context(response.iter_content(chunk_size=8192)),
                status=response.status_code,
                headers=response_headers
            )
            
        except requests.RequestException as e:
            self.logger.error(f"Error forwarding request to {url}: {str(e)}")
            return Response(f"Error forwarding request: {str(e)}", status=502)

    def _prepare_headers(self, client_headers: Dict[str, str], instance: Instance) -> Dict[str, str]:
        """Prepare headers for the backend request."""
        # Headers that should not be forwarded
        hop_by_hop_headers = {
            'connection', 'keep-alive', 'proxy-authenticate', 'proxy-authorization',
            'te', 'trailers', 'transfer-encoding', 'upgrade'
        }
        
        # Copy headers, excluding hop-by-hop ones
        headers = {
            k: v for k, v in client_headers.items()
            if k.lower() not in hop_by_hop_headers
        }
        
        # Update or set the Host header to match the backend server
        headers['Host'] = instance.addr
        
        # Add X-Forwarded headers
        headers['X-Forwarded-For'] = headers.get('X-Forwarded-For', '')
        if headers['X-Forwarded-For']:
            headers['X-Forwarded-For'] += ', '
        headers['X-Forwarded-For'] += headers.get('X-Real-IP', headers.get('Remote-Addr', ''))
        
        headers['X-Forwarded-Proto'] = 'https' if headers.get('X-Forwarded-Proto') == 'https' else 'http'
        headers['X-Forwarded-Host'] = headers.get('X-Forwarded-Host', client_headers.get('Host', ''))
        
        return headers

    def _prepare_response_headers(self, response_headers: Dict[str, str]) -> List[Tuple[str, str]]:
        """Prepare headers for the client response."""
        excluded_headers = {
            'content-encoding',
            'content-length',
            'transfer-encoding',
            'connection'
        }
        
        return [
            (name, value)
            for name, value in response_headers.items()
            if name.lower() not in excluded_headers
        ]