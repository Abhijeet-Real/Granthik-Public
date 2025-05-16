"""
Simple script to add chunk_size and chunk_overlap columns to the documents table
"""
import os
import sqlite3
from app.core.config import settings

def add_columns():
    """
    Add chunk_size and chunk_overlap columns to the documents table
    """
    print(f"Database file: {settings.SQLITE_DB_FILE}")
    
    if not os.path.exists(settings.SQLITE_DB_FILE):
        print(f"Database file not found: {settings.SQLITE_DB_FILE}")
        return
    
    print("Starting migration: Adding chunk_size and chunk_overlap columns to documents table")
    
    # Connect to the database
    conn = sqlite3.connect(settings.SQLITE_DB_FILE)
    cursor = conn.cursor()
    
    try:
        # Check if the columns already exist
        cursor.execute("PRAGMA table_info(documents)")
        columns = [column[1] for column in cursor.fetchall()]
        
        # Add chunk_size column if it doesn't exist
        if "chunk_size" not in columns:
            print("Adding chunk_size column...")
            cursor.execute("ALTER TABLE documents ADD COLUMN chunk_size INTEGER DEFAULT 1000")
        else:
            print("chunk_size column already exists")
        
        # Add chunk_overlap column if it doesn't exist
        if "chunk_overlap" not in columns:
            print("Adding chunk_overlap column...")
            cursor.execute("ALTER TABLE documents ADD COLUMN chunk_overlap INTEGER DEFAULT 200")
        else:
            print("chunk_overlap column already exists")
        
        # Commit the changes
        conn.commit()
        print("Migration completed successfully")
    except Exception as e:
        print(f"Error during migration: {str(e)}")
    finally:
        conn.close()

if __name__ == "__main__":
    add_columns()