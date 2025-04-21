from flask import Flask, request, jsonify, Blueprint
from src.db import collections as db
from src.db.models import Service, Algorithm
from pymongo.errors import DuplicateKeyError
from pydantic import ValidationError
from typing import Dict, Any

# Using Blueprint for modularity
service_bp = Blueprint('service_api', __name__, url_prefix='/services')

@service_bp.route('/', methods=['POST'])
def create_service():
    """API endpoint to create a new service."""
    data = request.get_json()
    if not data:
        return jsonify({"error": "Invalid input"}), 400

    try:
        # Pydantic validation
        service_data = Service(**data)
        # MongoDB will handle uniqueness through indices
        created_service = db.add_service(service_data)
        return jsonify(created_service.model_dump()), 201

    except DuplicateKeyError as e:
        # Extract the duplicate key field from MongoDB error
        error_msg = str(e)
        if "name" in error_msg:
            field = "name"
        elif "header" in error_msg:
            field = "header"
        else:
            field = "field"
        return jsonify({"error": f"Service with this {field} already exists"}), 409
    except ValidationError as e:
        return jsonify({"error": e.errors()}), 400
    except (ConnectionError, RuntimeError) as e:
        print(f"Error creating service (DB issue): {e}") # Basic logging
        return jsonify({"error": "Database operation failed"}), 500
    except Exception as e:
        print(f"Error creating service: {e}") # Basic logging
        return jsonify({"error": "An unexpected error occurred"}), 500

@service_bp.route('/', methods=['GET'])
def get_services():
    """API endpoint to retrieve all services (without instances)."""
    try:
        services = db.get_all_services()
        # Convert list of Service models to list of dicts
        # Instances are not included here; use instance endpoints if needed.
        return jsonify([service.model_dump() for service in services]), 200
    except Exception as e:
        # Log the exception e
        print(f"Error getting services: {e}") # Basic logging
        return jsonify({"error": "An unexpected error occurred"}), 500

@service_bp.route('/<string:service_id>', methods=['GET'])
def get_service(service_id: str):
    """API endpoint to retrieve a specific service by ID (without instances)."""
    try:
        service = db.get_service_by_id(service_id)
        if service:
            return jsonify(service.model_dump()), 200
        else:
            return jsonify({"error": "Service not found"}), 404
    except (ConnectionError, RuntimeError) as e:
        print(f"Error getting service {service_id} (DB issue): {e}")
        return jsonify({"error": "Database operation failed"}), 500
    except Exception as e:
        print(f"Error getting service {service_id}: {e}") # Basic logging
        return jsonify({"error": "An unexpected error occurred"}), 500

@service_bp.route('/header/<string:header>', methods=['GET'])
def get_service_by_hdr(header: str):
    """API endpoint to retrieve a specific service by header (without instances)."""
    try:
        service = db.get_service_by_header(header)
        if service:
            return jsonify(service.model_dump()), 200
        else:
            return jsonify({"error": "Service not found for this header"}), 404
    except (ConnectionError, RuntimeError) as e:
        print(f"Error getting service by header {header} (DB issue): {e}")
        return jsonify({"error": "Database operation failed"}), 500
    except Exception as e:
        print(f"Error getting service by header {header}: {e}") # Basic logging
        return jsonify({"error": "An unexpected error occurred"}), 500

@service_bp.route('/<string:service_id>', methods=['PUT'])
def update_service_endpoint(service_id: str):
    """API endpoint to update an existing service.
       Allows updating name, header, algorithm, stateful status.
       Does not allow updating instances via this endpoint.
    """
    data = request.get_json()
    if not data:
        return jsonify({"error": "Invalid input"}), 400

    # Fields allowed to be updated
    allowed_updates: Dict[str, Any] = {}
    if 'name' in data: allowed_updates['name'] = data['name']
    if 'header' in data: allowed_updates['header'] = data['header']
    if 'algorithm' in data:
        try:
            # Validate algorithm enum
            algo = Algorithm(data['algorithm'])
            allowed_updates['algorithm'] = algo.value
        except ValueError:
            return jsonify({"error": f"Invalid algorithm: {data['algorithm']}"}), 400
    if 'stateful' in data: allowed_updates['stateful'] = bool(data['stateful'])

    if not allowed_updates:
         return jsonify({"error": "No valid fields provided for update"}), 400

    try:
        # MongoDB will handle uniqueness through indices
        updated_service = db.update_service(service_id, allowed_updates)
        return jsonify(updated_service.model_dump()), 200

    except DuplicateKeyError as e:
        # Extract the duplicate key field from MongoDB error
        error_msg = str(e)
        if "name" in error_msg:
            field = "name"
        elif "header" in error_msg:
            field = "header"
        else:
            field = "field"
        return jsonify({"error": f"Another service already has this {field}"}), 409
    except ValueError as e: # Raised by db.update_service if service_id not found
        return jsonify({"error": str(e)}), 404 # Not Found
    except (ConnectionError, RuntimeError) as e:
        print(f"Error updating service {service_id} (DB issue): {e}")
        return jsonify({"error": "Database operation failed"}), 500
    except Exception as e:
        print(f"Error updating service {service_id}: {e}") # Basic logging
        return jsonify({"error": "An unexpected error occurred"}), 500

@service_bp.route('/<string:service_id>', methods=['DELETE'])
def delete_service_endpoint(service_id: str):
    """API endpoint to delete a service and its associated instances."""
    try:
        # Check if service exists before attempting delete (optional, db layer also checks)
        # existing_service = db.get_service_by_id(service_id)
        # if not existing_service:
        #     return jsonify({"error": "Service not found"}), 404

        # The db.delete_service function handles deleting associated instances
        success = db.delete_service(service_id)
        if success:
            return jsonify({"message": "Service and associated instances deleted successfully"}), 200 # 204 No Content is also valid
        else:
            # If delete_service returns False, it likely means the service wasn't found
            return jsonify({"error": "Service not found"}), 404
    except (ConnectionError, RuntimeError) as e:
        print(f"Error deleting service {service_id} (DB issue): {e}")
        return jsonify({"error": "Database operation failed"}), 500
    except Exception as e:
        print(f"Error deleting service {service_id}: {e}") # Basic logging
        return jsonify({"error": "An unexpected error occurred"}), 500
