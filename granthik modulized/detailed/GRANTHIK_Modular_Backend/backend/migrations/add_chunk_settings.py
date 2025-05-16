"""
Migration script to add chunk_size and chunk_overlap columns to the documents table
"""
import os
import sys
from sqlalchemy import create_engine, text

# Add the parent directory to the path so we can import from app
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.core.config import settings

def run_migration():
    """
    Add chunk_size and chunk_overlap columns to the documents table
    """
    print("Starting migration: Adding chunk_size and chunk_overlap columns to documents table")
    
    # Create SQLAlchemy engine
    engine = create_engine(f"sqlite:///{settings.SQLITE_DB_FILE}")
    
    # Check if the columns already exist
    with engine.connect() as conn:
        result = conn.execute(text("PRAGMA table_info(documents)"))
        columns = [column[1] for column in result.fetchall()]
        
        # Add chunk_size column if it doesn't exist
        if "chunk_size" not in columns:
            print("Adding chunk_size column...")
            conn.execute(text("ALTER TABLE documents ADD COLUMN chunk_size INTEGER DEFAULT 1000"))
        else:
            print("chunk_size column already exists")
        
        # Add chunk_overlap column if it doesn't exist
        if "chunk_overlap" not in columns:
            print("Adding chunk_overlap column...")
            conn.execute(text("ALTER TABLE documents ADD COLUMN chunk_overlap INTEGER DEFAULT 200"))
        else:
            print("chunk_overlap column already exists")
        
        # Commit the changes
        conn.commit()
    
    print("Migration completed successfully")

if __name__ == "__main__":
    run_migration()