import logging  # Add logging import
from flask import Flask, request, jsonify, Blueprint
from src.db import collections as db
from src.db.models import Instance, InstanceStatus, Service
from pymongo.errors import DuplicateKeyError
from pydantic import ValidationError
from typing import Dict, Any

# Using Blueprint for modularity, nested under services
# URL: /services/<service_id>/instances
instance_bp = Blueprint('instance_api', __name__, url_prefix='/services/<string:service_id>/instances')
logger = logging.getLogger(__name__)  # Instantiate logger

@instance_bp.route('/', methods=['POST'])
def create_instance_for_service(service_id: str):
    """API endpoint to create a new instance for a specific service."""
    # Check if the service exists first
    service = db.get_service_by_id(service_id)
    if not service:
        return jsonify({"error": "Service not found"}), 404

    data = request.get_json()
    if not data:
        return jsonify({"error": "Invalid input"}), 400

    try:
        # Add service_id to the instance data before validation
        data['service_id'] = service_id
        instance_data = Instance(**data)

        # MongoDB will handle uniqueness through indices
        created_instance = db.add_instance(instance_data)
        return jsonify(created_instance.model_dump()), 201

    except DuplicateKeyError:
        return jsonify({"error": f"Instance with address '{data.get('addr')}' already exists for this service"}), 409
    except ValidationError as e:
        # Provide specific error if 'addr' is missing
        missing_fields = [err['loc'][0] for err in e.errors() if err['type'] == 'missing']
        if 'addr' in missing_fields:
            return jsonify({"error": "Missing required field: 'addr'"}), 400
        return jsonify({"error": e.errors()}), 400
    except (ConnectionError, RuntimeError) as e:
        logger.error(f"Error creating instance (DB issue): {e}")  # Use logger
        return jsonify({"error": "Database operation failed"}), 500
    except Exception as e:
        logger.error(f"Error creating instance: {e}")  # Use logger
        return jsonify({"error": "An unexpected error occurred"}), 500

@instance_bp.route('/', methods=['GET'])
def get_instances_for_service(service_id: str):
    """API endpoint to retrieve all instances for a specific service."""
    # Check if the service exists (optional, but good practice)
    service = db.get_service_by_id(service_id)
    if not service:
        return jsonify({"error": "Service not found"}), 404

    try:
        instances = db.get_instances_by_service(service_id)
        return jsonify([instance.model_dump() for instance in instances]), 200
    except Exception as e:
        # Log the exception e
        logger.error(f"Error getting instances: {e}")  # Use logger
        return jsonify({"error": "An unexpected error occurred"}), 500

@instance_bp.route('/<string:instance_id>', methods=['GET'])
def get_specific_instance(service_id: str, instance_id: str):
    """API endpoint to retrieve a specific instance within a service."""
    try:
        instance = db.get_instance_by_id(instance_id)
        if instance:
            # Verify the instance belongs to the specified service
            if instance.service_id == service_id:
                return jsonify(instance.model_dump()), 200
            else:
                # Instance exists, but not for this service
                return jsonify({"error": "Instance not found within this service"}), 404
        else:
            return jsonify({"error": "Instance not found"}), 404
    except Exception as e:
        # Log the exception e
        logger.error(f"Error getting instance {instance_id}: {e}")  # Use logger
        return jsonify({"error": "An unexpected error occurred"}), 500

@instance_bp.route('/<string:instance_id>', methods=['DELETE'])
def delete_instance_from_service(service_id: str, instance_id: str):
    """API endpoint to delete an instance."""
    # Check if the instance exists and belongs to the service before deleting
    instance = db.get_instance_by_id(instance_id)
    if not instance or instance.service_id != service_id:
         return jsonify({"error": "Instance not found within this service"}), 404

    try:
        success = db.delete_instance(instance_id)
        if success:
            return jsonify({"message": "Instance deleted successfully"}), 200  # Or 204
        else:
            # Instance existed moments ago but deletion failed (should be rare)
            return jsonify({"error": "Failed to delete instance"}), 500
    except (ConnectionError, RuntimeError) as e:
        logger.error(f"Error deleting instance {instance_id} (DB issue): {e}")  # Use logger
        return jsonify({"error": "Database operation failed"}), 500
    except Exception as e:
        logger.error(f"Error deleting instance {instance_id}: {e}")  # Use logger
        return jsonify({"error": "An unexpected error occurred"}), 500

@instance_bp.route('/<string:instance_id>/status', methods=['PUT'])
def update_instance_status_for_service(service_id: str, instance_id: str):
    """API endpoint to update the status of an instance."""
    data = request.get_json()
    if not data or 'status' not in data:
        return jsonify({"error": "Invalid input, 'status' field required"}), 400

    try:
        # Validate the status value using the enum
        status = InstanceStatus(data['status'])
    except ValueError:
        valid_statuses = [s.value for s in InstanceStatus]
        return jsonify({"error": f"Invalid status. Valid statuses are: {valid_statuses}"}), 400

    # Check if the instance exists and belongs to the service before updating
    # get_instance_by_id is called again inside update_instance_status,
    # but checking here provides a clearer 404 before attempting the update.
    instance = db.get_instance_by_id(instance_id)
    if not instance or instance.service_id != service_id:
         return jsonify({"error": "Instance not found within this service"}), 404

    try:
        # Call the db function which handles update and returns the updated object
        updated_instance = db.update_instance_status(instance_id, status)
        return jsonify(updated_instance.model_dump()), 200
    except ValueError as e:  # Raised by db.update_instance_status if not found during update
        logger.error(f"Error updating status for instance {instance_id}: {e}")  # Use logger
        return jsonify({"error": "Instance not found"}), 404
    except (ConnectionError, RuntimeError) as e:
        logger.error(f"Error updating status for instance {instance_id} (DB issue): {e}")  # Use logger
        return jsonify({"error": "Database operation failed"}), 500
    except Exception as e:
        logger.error(f"Error updating status for instance {instance_id}: {e}")  # Use logger
        return jsonify({"error": "An unexpected error occurred"}), 500
