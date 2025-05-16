"""
Migration script to add chunking_strategy column to the documents table
"""
import os
import sys
from sqlalchemy import create_engine, text

# Add the parent directory to the path so we can import from app
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.core.config import settings

def run_migration():
    """
    Add chunking_strategy column to the documents table
    """
    print("Starting migration: Adding chunking_strategy column to documents table")
    
    # Create SQLAlchemy engine
    engine = create_engine(settings.SQLALCHEMY_DATABASE_URI)
    
    # Check if the column already exists
    with engine.connect() as conn:
        result = conn.execute(text("""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name='documents' AND column_name='chunking_strategy'
        """))
        columns = [column[0] for column in result.fetchall()]
        
        # Add chunking_strategy column if it doesn't exist
        if "chunking_strategy" not in columns:
            print("Adding chunking_strategy column...")
            conn.execute(text("ALTER TABLE documents ADD COLUMN chunking_strategy VARCHAR(50) DEFAULT 'hybrid'"))
            conn.commit()
            print("Column added successfully")
        else:
            print("chunking_strategy column already exists")
    
    print("Migration completed successfully")

if __name__ == "__main__":
    run_migration()