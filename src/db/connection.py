from pymongo import MongoClient
from pymongo.database import Database
from typing import Optional
from src.utils.config import get_config

_client: Optional[MongoClient] = None
_db: Optional[Database] = None

def connect_to_mongo() -> None:
    """Establishes connection to MongoDB Atlas using connection string details from config."""
    global _client, _db
    if _client is not None and _db is not None:
        return # Already connected

    config = get_config().get('mongodb', {})
    host = config.get('host') # e.g., db.jsgffyl.mongodb.net
    db_name = config.get('name')
    username = config.get('username')
    password = config.get('password')

    if not all([host, username, password]):
        print("Error: MongoDB Atlas connection details (host, username, password) missing in config.")
        # Consider raising an exception or handling the failure appropriately
        return

    try:
        # Construct the Atlas connection string
        # Note: You might need to adjust query parameters like retryWrites, w, appName based on your specific Atlas setup
        mongo_uri = f"mongodb+srv://{username}:{password}@{host}/?retryWrites=true&w=majority"
        # If your Atlas setup requires specifying the appName, add it:
        # app_name = config.get('appName', 'defaultAppName') # Get appName from config or use a default
        # mongo_uri += f"&appName={app_name}"

        _client = MongoClient(mongo_uri)
        # Ping the server to check connection
        _client.admin.command('ping')
        _db = _client[db_name] # Select the database
        print(f"Successfully connected to MongoDB Atlas database '{db_name}' at {host}")
    except Exception as e:
        print(f"Error connecting to MongoDB Atlas: {e}")
        _client = None
        _db = None
        # Consider raising an exception or handling the failure appropriately

def get_db() -> Optional[Database]:
    """Returns the database instance, connecting if necessary."""
    if _db is None:
        connect_to_mongo()
    return _db

def close_mongo_connection() -> None:
    """Closes the MongoDB connection."""
    global _client, _db
    if _client:
        _client.close()
        _client = None
        _db = None
        print("MongoDB connection closed.")
