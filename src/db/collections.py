from pymongo.collection import Collection
from pymongo.database import Database
from pymongo.errors import DuplicateKeyError
from typing import Optional, List, Dict, Any
from src.db.connection import get_db
from src.db.models import Service, Instance, InstanceStatus

# --- Collection Names ---
SERVICE_COLLECTION = "services"
INSTANCE_COLLECTION = "instances"

# --- Helper to get collections ---
def _get_collection(collection_name: str) -> Optional[Collection]:
    db = get_db()
    return db[collection_name] if db is not None else None

# --- Service Operations ---

def add_service(service_data: Service) -> Service:
    """Adds a new service to the database.
       Raises DuplicateKeyError if name or header already exists (due to unique index).
       Returns the created Service object.
    """
    collection = _get_collection(SERVICE_COLLECTION)
    if collection is None:
        raise ConnectionError("Database connection not available")

    service_dict = service_data.model_dump(by_alias=True)
    # Let MongoDB handle uniqueness through its indices
    result = collection.insert_one(service_dict)
    
    if not result.inserted_id:
        raise RuntimeError("Failed to insert service into database")
    
    # Fetch and return the created service object
    created_service = get_service_by_id(service_data.id)
    if not created_service:
        raise RuntimeError(f"Failed to retrieve newly created service with ID {service_data.id}")
    return created_service

def get_service_by_id(service_id: str) -> Optional[Service]:
    """Retrieves a service by its ID."""
    collection = _get_collection(SERVICE_COLLECTION)
    if collection is None: return None
    data = collection.find_one({"id": service_id})
    return Service(**data) if data else None

def get_service_by_header(header: str) -> Optional[Service]:
    """Retrieves a service by its Host header identifier."""
    collection = _get_collection(SERVICE_COLLECTION)
    if collection is None: return None
    data = collection.find_one({"header": header})
    return Service(**data) if data else None

def get_all_services() -> List[Service]:
    """Retrieves all services."""
    collection = _get_collection(SERVICE_COLLECTION)
    if collection is None: return []
    services_data = list(collection.find())
    return [Service(**data) for data in services_data]

def update_service(service_id: str, update_data: Dict[str, Any]) -> Service:
    """Updates an existing service.
       MongoDB's unique indices will handle uniqueness constraints.
       Raises ValueError if the service is not found.
       Returns the updated Service object.
    """
    collection = _get_collection(SERVICE_COLLECTION)
    if collection is None: 
        raise ConnectionError("Database connection not available")

    # Check if service exists first
    if not collection.find_one({"id": service_id}):
        raise ValueError(f"Service with ID '{service_id}' not found.")

    # Let MongoDB handle uniqueness through its indices
    result = collection.update_one({"id": service_id}, {"$set": update_data})

    if result.modified_count > 0 or result.matched_count > 0:
        # Get the updated or unchanged service
        updated_service = get_service_by_id(service_id)
        if updated_service:
            return updated_service
        else:
            raise RuntimeError(f"Failed to retrieve service with ID {service_id}")
    else:
        raise ValueError(f"Service with ID '{service_id}' not found during update.")

def delete_service(service_id: str) -> bool:
    """Deletes a service and its associated instances."""
    service_collection = _get_collection(SERVICE_COLLECTION)
    if service_collection is None: return False

    # First, delete associated instances
    deleted_instances_count = delete_instances_by_service(service_id)
    print(f"Deleted {deleted_instances_count} instances for service {service_id}")

    # Then, delete the service itself
    result = service_collection.delete_one({"id": service_id})
    return result.deleted_count > 0

# --- Instance Operations (Separate Collection) ---

def add_instance(instance_data: Instance) -> Instance:
    """Adds a new instance to the database.
       MongoDB's unique index will handle uniqueness constraint for addr within service.
       Returns the created Instance object.
    """
    collection = _get_collection(INSTANCE_COLLECTION)
    if collection is None: 
        raise ConnectionError("Database connection not available")

    instance_dict = instance_data.model_dump(by_alias=True)
    result = collection.insert_one(instance_dict)
    
    if not result.inserted_id:
        raise RuntimeError("Failed to insert instance into database")
        
    # Fetch and return the created instance
    created_instance = get_instance_by_id(instance_data.id)
    if not created_instance:
        raise RuntimeError(f"Failed to retrieve newly created instance with ID {instance_data.id}")
    return created_instance

def get_instance_by_id(instance_id: str) -> Optional[Instance]:
    """Retrieves an instance by its ID."""
    collection = _get_collection(INSTANCE_COLLECTION)
    if collection is None: return None
    data = collection.find_one({"id": instance_id})
    return Instance(**data) if data else None

def get_instances_by_service(service_id: str) -> List[Instance]:
    """Retrieves all instances for a given service."""
    collection = _get_collection(INSTANCE_COLLECTION)
    if collection is None: return []
    instances_data = list(collection.find({"service_id": service_id}))
    return [Instance(**data) for data in instances_data]

def update_instance_status(instance_id: str, status: InstanceStatus) -> Instance:
    """Updates the status of an instance.
       Raises ValueError if the instance is not found.
       Returns the updated Instance object.
    """
    collection = _get_collection(INSTANCE_COLLECTION)
    if collection is None: 
        raise ConnectionError("Database connection not available")

    result = collection.update_one(
        {"id": instance_id},
        {"$set": {"status": status.value}}
    )
    if result.modified_count > 0 or result.matched_count > 0:
        updated_instance = get_instance_by_id(instance_id)
        if updated_instance:
            return updated_instance
        else:
            raise RuntimeError(f"Failed to retrieve instance with ID {instance_id}")
    else:
        raise ValueError(f"Instance with ID '{instance_id}' not found.")

def delete_instance(instance_id: str) -> bool:
    """Deletes an instance."""
    collection = _get_collection(INSTANCE_COLLECTION)
    if collection is None: return False
    result = collection.delete_one({"id": instance_id})
    return result.deleted_count > 0

def delete_instances_by_service(service_id: str) -> int:
    """Deletes all instances associated with a service."""
    collection = _get_collection(INSTANCE_COLLECTION)
    if collection is None: return 0
    result = collection.delete_many({"service_id": service_id})
    return result.deleted_count
