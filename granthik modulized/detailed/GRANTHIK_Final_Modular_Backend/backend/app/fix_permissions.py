"""
Script to fix the permissions table by adding the missing 'name' column
"""
import logging
from sqlalchemy import text
from app.db.session import SessionLocal

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def fix_permissions_table():
    db = SessionLocal()
    try:
        # Check if the name column exists
        try:
            db.execute(text("SELECT name FROM permissions LIMIT 1"))
            logger.info("Name column already exists in permissions table")
        except Exception:
            # Add the name column
            logger.info("Adding name column to permissions table")
            db.execute(text("ALTER TABLE permissions ADD COLUMN name VARCHAR"))
            
            # Update the name column with a combination of resource and action
            db.execute(text("UPDATE permissions SET name = CONCAT(resource, '_', action)"))
            
            # Make the name column unique and not null
            db.execute(text("ALTER TABLE permissions ALTER COLUMN name SET NOT NULL"))
            db.execute(text("CREATE UNIQUE INDEX IF NOT EXISTS idx_permissions_name ON permissions (name)"))
            
            db.commit()
            logger.info("Successfully added and populated name column in permissions table")
    except Exception as e:
        logger.error(f"Error fixing permissions table: {str(e)}")
        db.rollback()
    finally:
        db.close()

def main():
    logger.info("Starting permissions table fix")
    fix_permissions_table()
    logger.info("Completed permissions table fix")

if __name__ == "__main__":
    main()