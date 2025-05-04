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


def test_create_service(client):
    """Test creating a new service via the API"""
    with patch('src.api.service.db') as mock_db:
        # Configure mock
        service_data = {
            "id": "service123",
            "name": "test-service",
            "header": "test.example.com",
            "domain": "test.example.com",
            "algorithm": "round_robin",
            "stateful": False
        }
        
        # Mock the service returned after creation
        mock_service = Service(**service_data)
        mock_db.add_service.return_value = mock_service
        
        # Make the API call
        response = client.post(
            '/services/',
            data=json.dumps(service_data),
            content_type='application/json'
        )
        
        # Check the response
        assert response.status_code == 201
        response_data = json.loads(response.data)
        assert response_data["name"] == "test-service"
        assert response_data["algorithm"] == "round_robin"
        
        # Verify the DB call
        mock_db.add_service.assert_called_once()


def test_create_service_duplicate(client):
    """Test creating a service with a duplicate name"""
    with patch('src.api.service.db') as mock_db:
        # Configure mock to raise DuplicateKeyError
        from pymongo.errors import DuplicateKeyError
        mock_db.add_service.side_effect = DuplicateKeyError(
            "E11000 duplicate key error collection: test.services index: name_1 dup key: { name: \"test-service\" }"
        )
        
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
        assert response.status_code == 409  # Conflict
        response_data = json.loads(response.data)
        assert "already exists" in response_data["error"]


def test_get_services(client):
    """Test retrieving all services"""
    with patch('src.api.service.db') as mock_db:
        # Mock services
        services = [
            Service(
                id="service1",
                name="Service 1",
                header="s1.example.com",
                domain="s1.example.com",
                algorithm=Algorithm.ROUND_ROBIN,
                stateful=False
            ),
            Service(
                id="service2",
                name="Service 2",
                header="s2.example.com",
                domain="s2.example.com",
                algorithm=Algorithm.IP_HASH,
                stateful=True
            )
        ]
        
        mock_db.get_all_services.return_value = services
        
        # Make the API call
        response = client.get('/services/')
        
        # Check the response
        assert response.status_code == 200
        response_data = json.loads(response.data)
        assert len(response_data) == 2
        assert response_data[0]["name"] == "Service 1"
        assert response_data[1]["name"] == "Service 2"


def test_get_service_by_id(client):
    """Test retrieving a service by ID"""
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
        
        mock_db.get_service_by_id.return_value = service
        
        # Make the API call
        response = client.get('/services/service123')
        
        # Check the response
        assert response.status_code == 200
        response_data = json.loads(response.data)
        assert response_data["id"] == "service123"
        assert response_data["name"] == "Test Service"


def test_get_service_by_id_not_found(client):
    """Test retrieving a non-existent service by ID"""
    with patch('src.api.service.db') as mock_db:
        mock_db.get_service_by_id.return_value = None
        
        # Make the API call
        response = client.get('/services/nonexistent')
        
        # Check the response
        assert response.status_code == 404
        response_data = json.loads(response.data)
        assert "not found" in response_data["error"]


def test_update_service(client):
    """Test updating a service"""
    with patch('src.api.service.db') as mock_db:
        # Updated service data
        update_data = {
            "name": "Updated Service",
            "algorithm": "ip_hash"
        }
        
        # Mock the updated service
        updated_service = Service(
            id="service123",
            name="Updated Service",
            header="test.example.com",
            domain="test.example.com",
            algorithm=Algorithm.IP_HASH,
            stateful=False
        )
        
        mock_db.update_service.return_value = updated_service
        
        # Make the API call
        response = client.put(
            '/services/service123',
            data=json.dumps(update_data),
            content_type='application/json'
        )
        
        # Check the response
        assert response.status_code == 200
        response_data = json.loads(response.data)
        assert response_data["name"] == "Updated Service"
        assert response_data["algorithm"] == "ip_hash"
        
        # Verify the DB call with correct parameters
        mock_db.update_service.assert_called_once_with(
            "service123", 
            {"name": "Updated Service", "algorithm": "ip_hash"}
        )


def test_delete_service(client):
    """Test deleting a service"""
    with patch('src.api.service.db') as mock_db:
        mock_db.delete_service.return_value = True
        
        # Make the API call
        response = client.delete('/services/service123')
        
        # Check the response
        assert response.status_code == 200
        response_data = json.loads(response.data)
        assert "deleted successfully" in response_data["message"]
        
        # Verify the DB call
        mock_db.delete_service.assert_called_once_with("service123") 