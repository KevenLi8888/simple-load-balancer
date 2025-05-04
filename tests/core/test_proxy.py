import pytest
from unittest.mock import patch, Mock, MagicMock
from src.core.proxy import ProxyHandler
from src.db.models import Instance
import requests

# Flask Response might need some mocking
class MockResponse:
    def __init__(self, data=None, status_code=200, headers=None):
        self.data = data or b""
        self.status_code = status_code
        self.headers = headers or {}
        
    def __iter__(self):
        yield self.data

@pytest.fixture
def proxy_handler():
    return ProxyHandler(timeout=5)

@pytest.fixture
def mock_instance():
    return Instance(id="test-instance", service_id="test-service", addr="127.0.0.1:8080", weight=1, status="healthy")

@pytest.fixture
def mock_request():
    mock_req = Mock()
    mock_req.method = "GET"
    mock_req.headers = {
        "Host": "example.com",
        "User-Agent": "test-agent",
        "Connection": "keep-alive",  # Hop-by-hop header that should be filtered
        "X-Real-IP": "192.168.1.10"
    }
    mock_req.cookies = {}
    mock_req.get_data = Mock(return_value=b"")
    return mock_req

def test_prepare_headers(proxy_handler, mock_instance, mock_request):
    # Test header preparation
    headers = proxy_handler._prepare_headers(dict(mock_request.headers), mock_instance)
    
    # Host should be replaced with the instance address
    assert headers["Host"] == mock_instance.addr
    
    # Hop-by-hop headers should be removed
    assert "Connection" not in headers
    
    # X-Forwarded headers should be added
    assert "X-Forwarded-For" in headers
    assert "192.168.1.10" in headers["X-Forwarded-For"]
    assert "X-Forwarded-Proto" in headers
    assert "X-Forwarded-Host" in headers

def test_prepare_response_headers(proxy_handler):
    # Create mock response headers
    response_headers = {
        "Content-Type": "application/json",
        "Content-Length": "1000",  # Should be excluded
        "Server": "TestServer",
        "Connection": "keep-alive"  # Should be excluded
    }
    
    # Process headers
    processed_headers = proxy_handler._prepare_response_headers(response_headers)
    
    # Check that excluded headers are removed
    header_names = [name.lower() for name, _ in processed_headers]
    assert "content-type" in header_names
    assert "server" in header_names
    assert "content-length" not in header_names
    assert "connection" not in header_names

@pytest.mark.skip(reason="Requires Flask request context")
@patch("requests.request")
@patch("src.core.proxy.Response")
def test_forward_request_success(mock_response_cls, mock_request_fn, proxy_handler, mock_instance, mock_request):
    # Setup mock response
    mock_response = Mock()
    mock_response.status_code = 200
    mock_response.raw = Mock()
    mock_response.raw.headers = {"Content-Type": "text/html"}
    mock_response.iter_content = Mock(return_value=[b"test content"])
    mock_request_fn.return_value = mock_response
    
    # Setup mock Flask Response
    mock_flask_response = MockResponse()
    mock_response_cls.return_value = mock_flask_response
    
    # Forward request
    response = proxy_handler.forward_request(mock_request, mock_instance, "test/path")
    
    # Check that requests.request was called with correct arguments
    mock_request_fn.assert_called_once()
    call_args = mock_request_fn.call_args[1]
    assert call_args["method"] == "GET"
    assert call_args["url"] == "http://127.0.0.1:8080/test/path"
    assert call_args["timeout"] == 5
    assert call_args["stream"] is True
    
    # Check that Flask Response was called
    mock_response_cls.assert_called_once()

@patch("requests.request")
def test_forward_request_error(mock_request_fn, proxy_handler, mock_instance, mock_request):
    # Setup request to raise an exception
    mock_request_fn.side_effect = requests.RequestException("Connection error")
    
    # Test that the exception is propagated
    with pytest.raises(requests.RequestException):
        proxy_handler.forward_request(mock_request, mock_instance, "test/path")

@pytest.mark.skip(reason="Requires Flask request context")
@patch("requests.request")
@patch("src.core.proxy.Response")
def test_forward_request_with_path_normalization(mock_response_cls, mock_request_fn, proxy_handler, mock_instance, mock_request):
    # Setup mock response
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.raw.headers = {}
    mock_request_fn.return_value = mock_response
    
    # Setup mock Flask Response
    mock_flask_response = MockResponse()
    mock_response_cls.return_value = mock_flask_response
    
    # Test with path that has leading slash
    proxy_handler.forward_request(mock_request, mock_instance, "/test/path")
    
    # Verify the correct URL was used (leading slash should be removed)
    assert mock_request_fn.call_args[1]["url"] == "http://127.0.0.1:8080/test/path" 