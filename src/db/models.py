from typing import Optional, List
from pydantic import BaseModel, Field
from enum import Enum
import uuid

class Algorithm(str, Enum):
    ROUND_ROBIN = "round_robin"
    IP_HASH = "ip_hash"
    LEAST_CONNECTION = "least_connection"
    WEIGHTED_ROUND_ROBIN = "weighted_round_robin"

class InstanceStatus(str, Enum):
    HEALTHY = "healthy"
    UNHEALTHY = "unhealthy"
    UNKNOWN = "unknown" # Initial state or after error

class Instance(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    service_id: str # Reference to the parent Service
    addr: str # Combined host:port or domain name
    status: InstanceStatus = InstanceStatus.UNKNOWN
    # Optional: Add weight, metadata, etc.

    class Config:
        use_enum_values = True # Store enum values as strings in DB

class Service(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str # Should be compound unique with header
    header: str # Host header identifier, should be compound unique with name
    algorithm: Algorithm = Algorithm.ROUND_ROBIN
    stateful: bool = False # For sticky sessions

    class Config:
        use_enum_values = True
        # Note: Pydantic doesn't enforce DB uniqueness.
        # This needs to be handled by DB indexes or application logic.
