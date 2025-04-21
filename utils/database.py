import json
import os
import logging
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)

# Directory for storing user data
DATA_DIR = "user_data"

def ensure_data_dir():
    """Ensure the data directory exists."""
    if not os.path.exists(DATA_DIR):
        try:
            os.makedirs(DATA_DIR)
        except Exception as e:
            logger.error(f"Failed to create data directory: {e}")
            raise

def save_user_data(user_id: str, data: Dict[str, Any]) -> bool:
    """Save user data to file.
    
    Args:
        user_id: Discord user ID
        data: User data dictionary to save
        
    Returns:
        bool: True if successful, False otherwise
    """
    ensure_data_dir()
    file_path = os.path.join(DATA_DIR, f"{user_id}.json")
    
    try:
        with open(file_path, 'w') as f:
            json.dump(data, f, indent=4)
        return True
    except Exception as e:
        logger.error(f"Error saving user data: {e}")
        return False

def load_user_data(user_id: str) -> Optional[Dict[str, Any]]:
    """Load user data from file.
    
    Args:
        user_id: Discord user ID
        
    Returns:
        Optional[Dict[str, Any]]: User data or None if not found
    """
    ensure_data_dir()
    file_path = os.path.join(DATA_DIR, f"{user_id}.json")
    
    if not os.path.exists(file_path):
        return None
    
    try:
        with open(file_path, 'r') as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"Error loading user data: {e}")
        return None

def delete_user_data(user_id: str) -> bool:
    """Delete user data file.
    
    Args:
        user_id: Discord user ID
        
    Returns:
        bool: True if successful, False otherwise
    """
    file_path = os.path.join(DATA_DIR, f"{user_id}.json")
    
    if not os.path.exists(file_path):
        return True
    
    try:
        os.remove(file_path)
        return True
    except Exception as e:
        logger.error(f"Error deleting user data: {e}")
        return False

def list_users() -> list:
    """List all user IDs with saved data.
    
    Returns:
        list: List of user IDs
    """
    ensure_data_dir()
    
    try:
        files = os.listdir(DATA_DIR)
        return [f.replace('.json', '') for f in files if f.endswith('.json')]
    except Exception as e:
        logger.error(f"Error listing users: {e}")
        return []
