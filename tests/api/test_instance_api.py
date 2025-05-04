import pytest
import json
from unittest.mock import patch, MagicMock
from flask import Flask
from src.api.instance import instance_bp
from src.db.models import Instance, InstanceStatus, Service


@pytest.fixture
def app():
    """Create a Flask app with the instance blueprint registered"""
    app = Flask(__name__)
    app.config['TESTING'] = True
    # Register service blueprint for the parent routes
    app.register_blueprint(instance_bp)
    return app


@pytest.fixture
def client(app):
    """Create a test client for the Flask app"""
    return app.test_client()


@pytest.fixture
def valid_instance_data():
    """Return valid instance data for testing"""
    return {
        "addr": "127.0.0.1:8080",
        "weight": 1,
        "status": "healthy"
    }


def test_create_instance_for_service(client, valid_instance_data):
    """Test creating a new instance for a service"""
    with patch('src.api.instance.db') as mock_db:
        # Mock the service
        mock_service = Service(
            id="service123",
            name="test-service",
            header="test.example.com",
            domain="test.example.com",
            algorithm="round_robin",
            stateful=False
        )
        mock_db.get_service_by_id.return_value = mock_service
        
        # Mock the created instance
        instance_data = valid_instance_data.copy()
        instance_data['service_id'] = "service123"
        instance_data['id'] = "instance123"
        mock_instance = Instance(**instance_data)
        mock_db.add_instance.return_value = mock_instance
        
        # Make the API call
        response = client.post(
            '/services/service123/instances/',
            data=json.dumps(valid_instance_data),
            content_type='application/json'
        )
        
        # Check the response
        assert response.status_code == 201
        response_data = json.loads(response.data)
        assert response_data["addr"] == "127.0.0.1:8080"
        assert response_data["service_id"] == "service123"
        
        # Verify the DB calls
        mock_db.get_service_by_id.assert_called_once_with("service123")
        mock_db.add_instance.assert_called_once()


def test_create_instance_for_nonexistent_service(client, valid_instance_data):
    """Test creating an instance for a service that doesn't exist"""
    with patch('src.api.instance.db') as mock_db:
        # Service not found
        mock_db.get_service_by_id.return_value = None
        
        # Make the API call
        response = client.post(
            '/services/nonexistent/instances/',
            data=json.dumps(valid_instance_data),
            content_type='application/json'
        )
        
        # Check the response
        assert response.status_code == 404
        response_data = json.loads(response.data)
        assert "Service not found" in response_data["error"]


def test_create_instance_invalid_input(client):
    """Test creating an instance with invalid input"""
    with patch('src.api.instance.db') as mock_db:
        # Mock the service
        mock_service = MagicMock()
        mock_db.get_service_by_id.return_value = mock_service
        
        # Make the API call with empty data
        response = client.post(
            '/services/service123/instances/',
            data=json.dumps({}),
            content_type='application/json'
        )
        
        # Check the response
        assert response.status_code == 400
        response_data = json.loads(response.data)
        assert "Invalid input" in response_data["error"]


def test_create_instance_missing_addr(client):
    """Test creating an instance with missing required addr field"""
    with patch('src.api.instance.db') as mock_db:
        # Mock the service
        mock_service = MagicMock()
        mock_db.get_service_by_id.return_value = mock_service
        
        # Make the API call with missing addr
        response = client.post(
            '/services/service123/instances/',
            data=json.dumps({"weight": 1}),
            content_type='application/json'
        )
        
        # Check the response - should fail validation
        assert response.status_code == 400
        response_data = json.loads(response.data)
        assert "Missing required field: 'addr'" in str(response_data)


def test_create_instance_duplicate(client, valid_instance_data):
    """Test creating an instance with a duplicate address"""
    with patch('src.api.instance.db') as mock_db:
        # Mock the service
        mock_service = MagicMock()
        mock_db.get_service_by_id.return_value = mock_service
        
        # Mock DuplicateKeyError
        from pymongo.errors import DuplicateKeyError
        mock_db.add_instance.side_effect = DuplicateKeyError("duplicate key error")
        
        # Make the API call
        response = client.post(
            '/services/service123/instances/',
            data=json.dumps(valid_instance_data),
            content_type='application/json'
        )
        
        # Check the response
        assert response.status_code == 409
        response_data = json.loads(response.data)
        assert "already exists" in response_data["error"]


def test_create_instance_database_error(client, valid_instance_data):
    """Test creating an instance with a database error"""
    with patch('src.api.instance.db') as mock_db:
        # Mock the service
        mock_service = MagicMock()
        mock_db.get_service_by_id.return_value = mock_service
        
        # Mock database error
        mock_db.add_instance.side_effect = ConnectionError("Database connection error")
        
        # Make the API call
        response = client.post(
            '/services/service123/instances/',
            data=json.dumps(valid_instance_data),
            content_type='application/json'
        )
        
        # Check the response
        assert response.status_code == 500
        response_data = json.loads(response.data)
        assert "Database operation failed" in response_data["error"]


def test_create_instance_unexpected_error(client, valid_instance_data):
    """Test creating an instance with an unexpected error"""
    with patch('src.api.instance.db') as mock_db:
        # Mock the service
        mock_service = MagicMock()
        mock_db.get_service_by_id.return_value = mock_service
        
        # Mock unexpected error
        mock_db.add_instance.side_effect = Exception("Unexpected error")
        
        # Make the API call
        response = client.post(
            '/services/service123/instances/',
            data=json.dumps(valid_instance_data),
            content_type='application/json'
        )
        
        # Check the response
        assert response.status_code == 500
        response_data = json.loads(response.data)
        assert "An unexpected error occurred" in response_data["error"]


def test_get_instances_for_service(client):
    """Test getting all instances for a service"""
    with patch('src.api.instance.db') as mock_db:
        # Mock the service
        mock_service = MagicMock()
        mock_db.get_service_by_id.return_value = mock_service
        
        # Mock instances
        mock_instances = [
            Instance(
                id=f"instance{i}",
                service_id="service123",
                addr=f"127.0.0.1:{8000+i}",
                weight=1,
                status=InstanceStatus.HEALTHY
            )
            for i in range(3)
        ]
        mock_db.get_instances_by_service.return_value = mock_instances
        
        # Make the API call
        response = client.get('/services/service123/instances/')
        
        # Check the response
        assert response.status_code == 200
        response_data = json.loads(response.data)
        assert len(response_data) == 3
        assert response_data[0]["addr"] == "127.0.0.1:8000"
        assert response_data[2]["addr"] == "127.0.0.1:8002"


def test_get_instances_service_not_found(client):
    """Test getting instances for a nonexistent service"""
    with patch('src.api.instance.db') as mock_db:
        # Service not found
        mock_db.get_service_by_id.return_value = None
        
        # Make the API call
        response = client.get('/services/nonexistent/instances/')
        
        # Check the response
        assert response.status_code == 404
        response_data = json.loads(response.data)
        assert "Service not found" in response_data["error"]


def test_get_instances_error(client):
    """Test getting instances with an error"""
    with patch('src.api.instance.db') as mock_db:
        # Mock the service
        mock_service = MagicMock()
        mock_db.get_service_by_id.return_value = mock_service
        
        # Mock error
        mock_db.get_instances_by_service.side_effect = Exception("Database error")
        
        # Make the API call
        response = client.get('/services/service123/instances/')
        
        # Check the response
        assert response.status_code == 500
        response_data = json.loads(response.data)
        assert "An unexpected error occurred" in response_data["error"]


def test_get_specific_instance(client):
    """Test getting a specific instance"""
    with patch('src.api.instance.db') as mock_db:
        # Mock the instance
        mock_instance = Instance(
            id="instance123",
            service_id="service123",
            addr="127.0.0.1:8080",
            weight=1,
            status=InstanceStatus.HEALTHY
        )
        mock_db.get_instance_by_id.return_value = mock_instance
        
        # Make the API call
        response = client.get('/services/service123/instances/instance123')
        
        # Check the response
        assert response.status_code == 200
        response_data = json.loads(response.data)
        assert response_data["id"] == "instance123"
        assert response_data["addr"] == "127.0.0.1:8080"


def test_get_specific_instance_not_found(client):
    """Test getting a nonexistent instance"""
    with patch('src.api.instance.db') as mock_db:
        # Instance not found
        mock_db.get_instance_by_id.return_value = None
        
        # Make the API call
        response = client.get('/services/service123/instances/nonexistent')
        
        # Check the response
        assert response.status_code == 404
        response_data = json.loads(response.data)
        assert "Instance not found" in response_data["error"]


def test_get_specific_instance_wrong_service(client):
    """Test getting an instance that belongs to a different service"""
    with patch('src.api.instance.db') as mock_db:
        # Mock the instance with a different service_id
        mock_instance = Instance(
            id="instance123",
            service_id="different_service",
            addr="127.0.0.1:8080",
            weight=1,
            status=InstanceStatus.HEALTHY
        )
        mock_db.get_instance_by_id.return_value = mock_instance
        
        # Make the API call
        response = client.get('/services/service123/instances/instance123')
        
        # Check the response
        assert response.status_code == 404
        response_data = json.loads(response.data)
        assert "Instance not found within this service" in response_data["error"]


def test_get_specific_instance_error(client):
    """Test getting a specific instance with an error"""
    with patch('src.api.instance.db') as mock_db:
        # Mock error
        mock_db.get_instance_by_id.side_effect = Exception("Database error")
        
        # Make the API call
        response = client.get('/services/service123/instances/instance123')
        
        # Check the response
        assert response.status_code == 500
        response_data = json.loads(response.data)
        assert "An unexpected error occurred" in response_data["error"]


def test_delete_instance(client):
    """Test deleting an instance"""
    with patch('src.api.instance.db') as mock_db:
        # Mock the instance
        mock_instance = Instance(
            id="instance123",
            service_id="service123",
            addr="127.0.0.1:8080",
            weight=1,
            status=InstanceStatus.HEALTHY
        )
        mock_db.get_instance_by_id.return_value = mock_instance
        mock_db.delete_instance.return_value = True
        
        # Make the API call
        response = client.delete('/services/service123/instances/instance123')
        
        # Check the response
        assert response.status_code == 200
        response_data = json.loads(response.data)
        assert "deleted successfully" in response_data["message"]


def test_delete_instance_not_found(client):
    """Test deleting a nonexistent instance"""
    with patch('src.api.instance.db') as mock_db:
        # Instance not found
        mock_db.get_instance_by_id.return_value = None
        
        # Make the API call
        response = client.delete('/services/service123/instances/nonexistent')
        
        # Check the response
        assert response.status_code == 404
        response_data = json.loads(response.data)
        assert "Instance not found" in response_data["error"]


def test_delete_instance_wrong_service(client):
    """Test deleting an instance that belongs to a different service"""
    with patch('src.api.instance.db') as mock_db:
        # Mock the instance with a different service_id
        mock_instance = Instance(
            id="instance123",
            service_id="different_service",
            addr="127.0.0.1:8080",
            weight=1,
            status=InstanceStatus.HEALTHY
        )
        mock_db.get_instance_by_id.return_value = mock_instance
        
        # Make the API call
        response = client.delete('/services/service123/instances/instance123')
        
        # Check the response
        assert response.status_code == 404
        response_data = json.loads(response.data)
        assert "Instance not found within this service" in response_data["error"]


def test_delete_instance_db_error(client):
    """Test deleting an instance with a database error"""
    with patch('src.api.instance.db') as mock_db:
        # Mock the instance
        mock_instance = Instance(
            id="instance123",
            service_id="service123",
            addr="127.0.0.1:8080",
            weight=1,
            status=InstanceStatus.HEALTHY
        )
        mock_db.get_instance_by_id.return_value = mock_instance
        mock_db.delete_instance.side_effect = ConnectionError("Database error")
        
        # Make the API call
        response = client.delete('/services/service123/instances/instance123')
        
        # Check the response
        assert response.status_code == 500
        response_data = json.loads(response.data)
        assert "Database operation failed" in response_data["error"]


def test_update_instance_status(client):
    """Test updating an instance status"""
    with patch('src.api.instance.db') as mock_db:
        # Mock the instance
        mock_instance = Instance(
            id="instance123",
            service_id="service123",
            addr="127.0.0.1:8080",
            weight=1,
            status=InstanceStatus.HEALTHY
        )
        mock_db.get_instance_by_id.return_value = mock_instance
        
        # Mock the updated instance
        updated_instance = mock_instance.model_copy()
        updated_instance.status = InstanceStatus.UNHEALTHY
        mock_db.update_instance_status.return_value = updated_instance
        
        # Make the API call
        response = client.put(
            '/services/service123/instances/instance123/status',
            data=json.dumps({"status": "unhealthy"}),
            content_type='application/json'
        )
        
        # Check the response
        assert response.status_code == 200
        response_data = json.loads(response.data)
        assert response_data["status"] == "unhealthy"


def test_update_instance_status_invalid_input(client):
    """Test updating an instance status with invalid input"""
    # Make the API call with empty data
    response = client.put(
        '/services/service123/instances/instance123/status',
        data=json.dumps({}),
        content_type='application/json'
    )
    
    # Check the response
    assert response.status_code == 400
    response_data = json.loads(response.data)
    assert "Invalid input" in response_data["error"]


def test_update_instance_status_invalid_status(client):
    """Test updating an instance status with an invalid status value"""
    # Make the API call with invalid status
    response = client.put(
        '/services/service123/instances/instance123/status',
        data=json.dumps({"status": "invalid_status"}),
        content_type='application/json'
    )
    
    # Check the response
    assert response.status_code == 400
    response_data = json.loads(response.data)
    assert "Invalid status" in response_data["error"]


def test_update_instance_status_not_found(client):
    """Test updating a nonexistent instance status"""
    with patch('src.api.instance.db') as mock_db:
        # Instance not found
        mock_db.get_instance_by_id.return_value = None
        
        # Make the API call
        response = client.put(
            '/services/service123/instances/nonexistent/status',
            data=json.dumps({"status": "unhealthy"}),
            content_type='application/json'
        )
        
        # Check the response
        assert response.status_code == 404
        response_data = json.loads(response.data)
        assert "Instance not found" in response_data["error"]


def test_update_instance_status_wrong_service(client):
    """Test updating an instance status that belongs to a different service"""
    with patch('src.api.instance.db') as mock_db:
        # Mock the instance with a different service_id
        mock_instance = Instance(
            id="instance123",
            service_id="different_service",
            addr="127.0.0.1:8080",
            weight=1,
            status=InstanceStatus.HEALTHY
        )
        mock_db.get_instance_by_id.return_value = mock_instance
        
        # Make the API call
        response = client.put(
            '/services/service123/instances/instance123/status',
            data=json.dumps({"status": "unhealthy"}),
            content_type='application/json'
        )
        
        # Check the response
        assert response.status_code == 404
        response_data = json.loads(response.data)
        assert "Instance not found within this service" in response_data["error"]


def test_update_instance_status_db_error(client):
    """Test updating an instance status with a database error"""
    with patch('src.api.instance.db') as mock_db:
        # Mock the instance
        mock_instance = Instance(
            id="instance123",
            service_id="service123",
            addr="127.0.0.1:8080",
            weight=1,
            status=InstanceStatus.HEALTHY
        )
        mock_db.get_instance_by_id.return_value = mock_instance
        mock_db.update_instance_status.side_effect = ConnectionError("Database error")
        
        # Make the API call
        response = client.put(
            '/services/service123/instances/instance123/status',
            data=json.dumps({"status": "unhealthy"}),
            content_type='application/json'
        )
        
        # Check the response
        assert response.status_code == 500
        response_data = json.loads(response.data)
        assert "Database operation failed" in response_data["error"] 