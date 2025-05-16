"""
Script to run database migrations
"""
import os
import sys
import psycopg2
from app.core.config import settings

def run_chunk_size_migration():
    """
    Run the SQL migration to add chunk_size and chunk_overlap columns
    """
    print("Starting migration to add chunk_size and chunk_overlap columns")
    
    # Connect to the PostgreSQL database
    conn = psycopg2.connect(
        host=settings.POSTGRES_SERVER,
        port=settings.POSTGRES_PORT,
        user=settings.POSTGRES_USER,
        password=settings.POSTGRES_PASSWORD,
        dbname=settings.POSTGRES_DB
    )
    
    # Create a cursor
    cursor = conn.cursor()
    
    try:
        # Check if the columns already exist
        cursor.execute("""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name='documents' AND column_name IN ('chunk_size', 'chunk_overlap')
        """)
        existing_columns = [col[0] for col in cursor.fetchall()]
        
        # Add chunk_size column if it doesn't exist
        if 'chunk_size' not in existing_columns:
            print("Adding chunk_size column...")
            cursor.execute("ALTER TABLE documents ADD COLUMN chunk_size INTEGER DEFAULT 1000")
        else:
            print("chunk_size column already exists")
        
        # Add chunk_overlap column if it doesn't exist
        if 'chunk_overlap' not in existing_columns:
            print("Adding chunk_overlap column...")
            cursor.execute("ALTER TABLE documents ADD COLUMN chunk_overlap INTEGER DEFAULT 200")
        else:
            print("chunk_overlap column already exists")
        
        # Commit the changes
        conn.commit()
        print("Migration completed successfully")
    except Exception as e:
        conn.rollback()
        print(f"Error during migration: {str(e)}")
    finally:
        cursor.close()
        conn.close()

def run_chunking_strategy_migration():
    """
    Run the SQL migration to add chunking_strategy column
    """
    print("Starting migration to add chunking_strategy column")
    
    # Connect to the PostgreSQL database
    conn = psycopg2.connect(
        host=settings.POSTGRES_SERVER,
        port=settings.POSTGRES_PORT,
        user=settings.POSTGRES_USER,
        password=settings.POSTGRES_PASSWORD,
        dbname=settings.POSTGRES_DB
    )
    
    # Create a cursor
    cursor = conn.cursor()
    
    try:
        # Check if the column already exists
        cursor.execute("""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name='documents' AND column_name='chunking_strategy'
        """)
        existing_columns = [col[0] for col in cursor.fetchall()]
        
        # Add chunking_strategy column if it doesn't exist
        if 'chunking_strategy' not in existing_columns:
            print("Adding chunking_strategy column...")
            cursor.execute("ALTER TABLE documents ADD COLUMN chunking_strategy VARCHAR(50) DEFAULT 'hybrid'")
            conn.commit()
            print("Column added successfully")
        else:
            print("chunking_strategy column already exists")
        
        # Commit the changes
        conn.commit()
        print("Migration completed successfully")
    except Exception as e:
        conn.rollback()
        print(f"Error during migration: {str(e)}")
    finally:
        cursor.close()
        conn.close()

def run_migration():
    """
    Run all migrations
    """
    run_chunk_size_migration()
    run_chunking_strategy_migration()

if __name__ == "__main__":
    run_migration()