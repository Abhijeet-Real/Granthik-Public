"""
Script to run database migrations
"""
import os
import sys
import logging
import importlib.util
from sqlalchemy import create_engine
from alembic.config import Config
from alembic import command

from app.core.config import settings
from app.db.session import engine

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def run_migration(migration_name):
    """
    Run a specific migration script
    
    Args:
        migration_name: Name of the migration script (without .py extension)
    """
    try:
        # Import the migration module
        migration_path = os.path.join(os.path.dirname(__file__), "migrations", f"{migration_name}.py")
        if not os.path.exists(migration_path):
            logger.error(f"Migration file not found: {migration_path}")
            return False
        
        # Load the module
        spec = importlib.util.spec_from_file_location(migration_name, migration_path)
        migration = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(migration)
        
        # Run the upgrade function
        logger.info(f"Running migration: {migration_name}")
        migration.upgrade()
        logger.info(f"Migration completed successfully: {migration_name}")
        return True
    except Exception as e:
        logger.error(f"Error running migration: {str(e)}")
        return False

if __name__ == "__main__":
    if len(sys.argv) < 2:
        logger.error("Please provide a migration name")
        sys.exit(1)
    
    migration_name = sys.argv[1]
    success = run_migration(migration_name)
    sys.exit(0 if success else 1)