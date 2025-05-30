import yaml
import logging
from typing import Dict, Any

CONFIG: Dict[str, Any] = {}
logger = logging.getLogger(__name__)

def load_config(path: str = 'config.yaml') -> None:
    """Loads configuration from a YAML file."""
    global CONFIG
    try:
        with open(path, 'r') as f:
            CONFIG = yaml.safe_load(f)
    except FileNotFoundError:
        logger.error(f"Configuration file '{path}' not found.")
        # Potentially load default config or exit
        CONFIG = {} # Initialize with empty dict or defaults
    except yaml.YAMLError as e:
        logger.error(f"Error parsing configuration file '{path}': {e}")
        CONFIG = {}

def get_config() -> Dict[str, Any]:
    """Returns the loaded configuration."""
    if not CONFIG:
        load_config() # Load if not already loaded
    return CONFIG