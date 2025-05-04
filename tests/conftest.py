import pytest
import sys
import os
from unittest.mock import MagicMock
from flask import Flask, Request
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.db.models import Service, Instance, Algorithm, InstanceStatus


@pytest.fixture
def mock_service():
    """Returns a mock service object for testing"""
    return Service(
        id="service123",
        name="test-service",
        header="test.example.com",
        domain="test.example.com",
        algorithm=Algorithm.ROUND_ROBIN,
        stateful=False
    )


@pytest.fixture
def mock_instances():
    """Returns a list of mock instances for testing"""
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
def flask_app():
    """Creates a Flask app for testing"""
    app = Flask(__name__)
    app.config['TESTING'] = True
    return app


@pytest.fixture
def mock_request():
    """Creates a mock Flask request"""
    request = MagicMock(spec=Request)
    request.headers = {'Host': 'test.example.com'}
    request.method = 'GET'
    request.remote_addr = '192.168.1.1'
    request.path = '/'
    request.args = {}
    request.form = {}
    request.data = b''
    return request


@pytest.fixture
def mock_db_collections():
    """Mock the database collections module"""
    mock_db = MagicMock()
    mock_db.get_service_by_header.return_value = None
    mock_db.get_instances_by_service.return_value = []
    mock_db.get_all_services.return_value = []
    mock_db.update_instance_status = MagicMock()
    return mock_db 