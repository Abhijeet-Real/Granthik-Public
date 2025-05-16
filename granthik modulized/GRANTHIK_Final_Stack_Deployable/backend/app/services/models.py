"""
Module for managing LLM models
"""
from typing import List, Dict, Any
import os
import json
from pathlib import Path

# Path to the models configuration file
MODELS_CONFIG_PATH = os.path.join(os.path.dirname(__file__), "models_config.json")

def get_available_models() -> List[Dict[str, Any]]:
    """
    Get a list of available models
    
    Returns:
        List of model objects with id and name
    """
    # Check if models config file exists
    if os.path.exists(MODELS_CONFIG_PATH):
        try:
            with open(MODELS_CONFIG_PATH, "r") as f:
                return json.load(f)
        except Exception as e:
            import logging
            logger = logging.getLogger("uvicorn")
            logger.error(f"Error loading models config: {str(e)}")
    
    # Default models if config file doesn't exist or has an error
    return [
        {"id": "phi4:latest", "name": "Phi-4"},
        {"id": "llama3.2:latest", "name": "Llama 3.2"},
        {"id": "mistral:latest", "name": "Mistral"},
    ]

def save_models(models: List[Dict[str, Any]]) -> bool:
    """
    Save the list of models to the config file
    
    Args:
        models: List of model objects with id and name
        
    Returns:
        True if successful, False otherwise
    """
    try:
        # Ensure directory exists
        os.makedirs(os.path.dirname(MODELS_CONFIG_PATH), exist_ok=True)
        
        with open(MODELS_CONFIG_PATH, "w") as f:
            json.dump(models, f, indent=2)
        return True
    except Exception as e:
        import logging
        logger = logging.getLogger("uvicorn")
        logger.error(f"Error saving models config: {str(e)}")
        return False