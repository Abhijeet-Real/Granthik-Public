#!/usr/bin/env python3
"""
Database migration script for Docker deployment.
This script runs all pending Alembic migrations to ensure the database schema is up-to-date.
"""

import os
import sys
import time
import logging
from sqlalchemy import create_engine
from sqlalchemy.exc import OperationalError
from alembic.config import Config
from alembic import command

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Get database connection details from environment variables
POSTGRES_SERVER = os.getenv("POSTGRES_SERVER", "localhost")
POSTGRES_PORT = os.getenv("POSTGRES_PORT", "5432")
POSTGRES_USER = os.getenv("POSTGRES_USER", "postgres")
POSTGRES_PASSWORD = os.getenv("POSTGRES_PASSWORD", "postgres")
POSTGRES_DB = os.getenv("POSTGRES_DB", "granthik")

# Database connection string
DATABASE_URL = f"postgresql://{POSTGRES_USER}:{POSTGRES_PASSWORD}@{POSTGRES_SERVER}:{POSTGRES_PORT}/{POSTGRES_DB}"

def wait_for_database(max_retries=30, retry_interval=2):
    """Wait for the database to be available."""
    logger.info(f"Waiting for database at {POSTGRES_SERVER}:{POSTGRES_PORT}...")
    
    retries = 0
    while retries < max_retries:
        try:
            engine = create_engine(DATABASE_URL)
            conn = engine.connect()
            conn.close()
            logger.info("Database is available!")
            return True
        except OperationalError as e:
            logger.warning(f"Database not available yet: {e}")
            retries += 1
            time.sleep(retry_interval)
    
    logger.error(f"Could not connect to database after {max_retries} attempts")
    return False

def run_migrations():
    """Run all pending Alembic migrations."""
    logger.info("Running database migrations...")
    
    try:
        # Get the Alembic configuration
        alembic_cfg = Config("alembic.ini")
        
        # Run the migrations
        command.upgrade(alembic_cfg, "head")
        
        logger.info("Database migrations completed successfully!")
        return True
    except Exception as e:
        logger.error(f"Error running migrations: {e}")
        return False

if __name__ == "__main__":
    if not wait_for_database():
        logger.error("Failed to connect to database. Exiting.")
        sys.exit(1)
    
    if not run_migrations():
        logger.error("Failed to run migrations. Exiting.")
        sys.exit(1)
    
    logger.info("Migration process completed successfully.")
    sys.exit(0)