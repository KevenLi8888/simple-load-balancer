import pytest
import json
from unittest.mock import patch, MagicMock
from flask import Flask
from src.api.service import service_bp
from src.db.models import Service, Algorithm


@pytest.fixture
def app():
    """Create a Flask app with the service blueprint registered"""
    app = Flask(__name__)
    app.config['TESTING'] = True
    app.register_blueprint(service_bp)
    return app


@pytest.fixture
def client(app):
    """Create a test client for the Flask app"""
    return app.test_client()


def test_create_service_missing_field(client):
    """Test creating a service with validation errors (missing fields)"""
    with patch('src.api.service.db') as mock_db:
        # Service data with missing required fields
        service_data = {
            "name": "test-service"
            # missing header, domain, algorithm
        }
        
        # Make the API call
        response = client.post(
            '/services/',
            data=json.dumps(service_data),
            content_type='application/json'
        )
        
        # Check the response
        assert response.status_code == 400
        response_data = json.loads(response.data)
        assert "error" in response_data


def test_create_service_empty_payload(client):
    """Test creating a service with an empty payload"""
    # Make the API call with empty data
    response = client.post(
        '/services/',
        data=json.dumps({}),
        content_type='application/json'
    )
    
    # Check the response
    assert response.status_code == 400
    response_data = json.loads(response.data)
    assert "Invalid input" in response_data["error"]


def test_create_service_db_error(client):
    """Test creating a service with a database error"""
    with patch('src.api.service.db') as mock_db:
        # Configure mock to raise a connection error
        mock_db.add_service.side_effect = ConnectionError("Database connection error")
        
        # Service data
        service_data = {
            "name": "test-service",
            "header": "test.example.com",
            "domain": "test.example.com",
            "algorithm": "round_robin",
            "stateful": False
        }
        
        # Make the API call
        response = client.post(
            '/services/',
            data=json.dumps(service_data),
            content_type='application/json'
        )
        
        # Check the response
        assert response.status_code == 500
        response_data = json.loads(response.data)
        assert "Database operation failed" in response_data["error"]


def test_create_service_unexpected_error(client):
    """Test creating a service with an unexpected error"""
    with patch('src.api.service.db') as mock_db:
        # Configure mock to raise an unexpected error
        mock_db.add_service.side_effect = Exception("Unexpected error")
        
        # Service data
        service_data = {
            "name": "test-service",
            "header": "test.example.com",
            "domain": "test.example.com",
            "algorithm": "round_robin",
            "stateful": False
        }
        
        # Make the API call
        response = client.post(
            '/services/',
            data=json.dumps(service_data),
            content_type='application/json'
        )
        
        # Check the response
        assert response.status_code == 500
        response_data = json.loads(response.data)
        assert "An unexpected error occurred" in response_data["error"]


def test_get_services_error(client):
    """Test handling of errors when retrieving all services"""
    with patch('src.api.service.db') as mock_db:
        # Configure mock to raise an error
        mock_db.get_all_services.side_effect = Exception("Database error")
        
        # Make the API call
        response = client.get('/services/')
        
        # Check the response
        assert response.status_code == 500
        response_data = json.loads(response.data)
        assert "An unexpected error occurred" in response_data["error"]


def test_get_service_db_error(client):
    """Test handling of database errors when retrieving a service by ID"""
    with patch('src.api.service.db') as mock_db:
        # Configure mock to raise a connection error
        mock_db.get_service_by_id.side_effect = ConnectionError("Database connection error")
        
        # Make the API call
        response = client.get('/services/service123')
        
        # Check the response
        assert response.status_code == 500
        response_data = json.loads(response.data)
        assert "Database operation failed" in response_data["error"]


def test_get_service_unexpected_error(client):
    """Test handling of unexpected errors when retrieving a service by ID"""
    with patch('src.api.service.db') as mock_db:
        # Configure mock to raise an unexpected error
        mock_db.get_service_by_id.side_effect = Exception("Unexpected error")
        
        # Make the API call
        response = client.get('/services/service123')
        
        # Check the response
        assert response.status_code == 500
        response_data = json.loads(response.data)
        assert "An unexpected error occurred" in response_data["error"]


def test_get_service_by_hdr(client):
    """Test retrieving a service by header"""
    with patch('src.api.service.db') as mock_db:
        # Mock service
        service = Service(
            id="service123",
            name="Test Service",
            header="test.example.com",
            domain="test.example.com",
            algorithm=Algorithm.ROUND_ROBIN,
            stateful=False
        )
        
        mock_db.get_service_by_header.return_value = service
        
        # Make the API call
        response = client.get('/services/header/test.example.com')
        
        # Check the response
        assert response.status_code == 200
        response_data = json.loads(response.data)
        assert response_data["id"] == "service123"
        assert response_data["name"] == "Test Service"


def test_get_service_by_hdr_not_found(client):
    """Test retrieving a non-existent service by header"""
    with patch('src.api.service.db') as mock_db:
        mock_db.get_service_by_header.return_value = None
        
        # Make the API call
        response = client.get('/services/header/nonexistent.example.com')
        
        # Check the response
        assert response.status_code == 404
        response_data = json.loads(response.data)
        assert "not found" in response_data["error"]


def test_get_service_by_hdr_db_error(client):
    """Test handling of database errors when retrieving a service by header"""
    with patch('src.api.service.db') as mock_db:
        # Configure mock to raise a connection error
        mock_db.get_service_by_header.side_effect = ConnectionError("Database connection error")
        
        # Make the API call
        response = client.get('/services/header/test.example.com')
        
        # Check the response
        assert response.status_code == 500
        response_data = json.loads(response.data)
        assert "Database operation failed" in response_data["error"]


def test_update_service_empty_payload(client):
    """Test updating a service with an empty payload"""
    # Make the API call with empty data
    response = client.put(
        '/services/service123',
        data=json.dumps({}),
        content_type='application/json'
    )
    
    # Check the response
    assert response.status_code == 400
    response_data = json.loads(response.data)
    assert "Invalid input" in response_data["error"]


def test_update_service_invalid_algorithm(client):
    """Test updating a service with an invalid algorithm"""
    # Make the API call with invalid algorithm
    response = client.put(
        '/services/service123',
        data=json.dumps({"algorithm": "invalid_algorithm"}),
        content_type='application/json'
    )
    
    # Check the response
    assert response.status_code == 400
    response_data = json.loads(response.data)
    assert "Invalid algorithm" in response_data["error"]


def test_update_service_service_not_found(client):
    """Test updating a non-existent service"""
    with patch('src.api.service.db') as mock_db:
        # Configure mock to raise a value error (service not found)
        mock_db.update_service.side_effect = ValueError("Service not found")
        
        # Make the API call
        response = client.put(
            '/services/nonexistent',
            data=json.dumps({"name": "Updated Service"}),
            content_type='application/json'
        )
        
        # Check the response
        assert response.status_code == 404
        response_data = json.loads(response.data)
        assert "not found" in str(response_data["error"]).lower()


def test_update_service_duplicate(client):
    """Test updating a service with a duplicate name/header"""
    with patch('src.api.service.db') as mock_db:
        # Configure mock to raise DuplicateKeyError
        from pymongo.errors import DuplicateKeyError
        mock_db.update_service.side_effect = DuplicateKeyError(
            "E11000 duplicate key error collection: test.services index: name_1 dup key: { name: \"another-service\" }"
        )
        
        # Make the API call
        response = client.put(
            '/services/service123',
            data=json.dumps({"name": "another-service"}),
            content_type='application/json'
        )
        
        # Check the response
        assert response.status_code == 409
        response_data = json.loads(response.data)
        assert "already has this" in response_data["error"]


def test_update_service_db_error(client):
    """Test updating a service with a database error"""
    with patch('src.api.service.db') as mock_db:
        # Configure mock to raise a connection error
        mock_db.update_service.side_effect = ConnectionError("Database connection error")
        
        # Make the API call
        response = client.put(
            '/services/service123',
            data=json.dumps({"name": "Updated Service"}),
            content_type='application/json'
        )
        
        # Check the response
        assert response.status_code == 500
        response_data = json.loads(response.data)
        assert "Database operation failed" in response_data["error"]


def test_delete_service_not_found(client):
    """Test deleting a non-existent service"""
    with patch('src.api.service.db') as mock_db:
        # Configure mock to return False (service not found)
        mock_db.delete_service.return_value = False
        
        # Make the API call
        response = client.delete('/services/nonexistent')
        
        # Check the response
        assert response.status_code == 404
        response_data = json.loads(response.data)
        assert "not found" in response_data["error"]


def test_delete_service_db_error(client):
    """Test deleting a service with a database error"""
    with patch('src.api.service.db') as mock_db:
        # Configure mock to raise a connection error
        mock_db.delete_service.side_effect = ConnectionError("Database connection error")
        
        # Make the API call
        response = client.delete('/services/service123')
        
        # Check the response
        assert response.status_code == 500
        response_data = json.loads(response.data)
        assert "Database operation failed" in response_data["error"]


def test_delete_service_unexpected_error(client):
    """Test deleting a service with an unexpected error"""
    with patch('src.api.service.db') as mock_db:
        # Configure mock to raise an unexpected error
        mock_db.delete_service.side_effect = Exception("Unexpected error")
        
        # Make the API call
        response = client.delete('/services/service123')
        
        # Check the response
        assert response.status_code == 500
        response_data = json.loads(response.data)
        assert "An unexpected error occurred" in response_data["error"] 