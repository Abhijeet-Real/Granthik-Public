#!/usr/bin/env python3
"""
Script to list all active users in the database.
"""

import os
import sys
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

# Get database connection details from environment variables
POSTGRES_SERVER = os.getenv("POSTGRES_SERVER", "localhost")
POSTGRES_PORT = os.getenv("POSTGRES_PORT", "8803")
POSTGRES_USER = os.getenv("POSTGRES_USER", "postgres")
POSTGRES_PASSWORD = os.getenv("POSTGRES_PASSWORD", "postgres")
POSTGRES_DB = os.getenv("POSTGRES_DB", "granthik")

# Database connection string
DATABASE_URL = f"postgresql://{POSTGRES_USER}:{POSTGRES_PASSWORD}@{POSTGRES_SERVER}:{POSTGRES_PORT}/{POSTGRES_DB}"

def list_users():
    """List all active users in the database."""
    try:
        # Create database engine
        engine = create_engine(DATABASE_URL)
        
        # Create session
        Session = sessionmaker(bind=engine)
        session = Session()
        
        # Query all users
        query = text("""
            SELECT id, email, username, is_active, is_superuser, approval_status
            FROM users
            ORDER BY id
        """)
        
        users = session.execute(query).fetchall()
        
        # Print user information
        print("\n=== GRANTHIK Users ===\n")
        print(f"{'ID':<5} {'Email':<30} {'Username':<20} {'Active':<10} {'Admin':<10} {'Status':<10}")
        print("-" * 85)
        
        for user in users:
            print(f"{user.id:<5} {user.email:<30} {user.username:<20} {'Yes' if user.is_active else 'No':<10} {'Yes' if user.is_superuser else 'No':<10} {user.approval_status:<10}")
        
        print("\n=== Active Users ===\n")
        active_users = [u for u in users if u.is_active]
        
        if active_users:
            for user in active_users:
                print(f"Username: {user.username}")
                print(f"Email: {user.email}")
                print(f"Admin: {'Yes' if user.is_superuser else 'No'}")
                print("-" * 30)
        else:
            print("No active users found.")
        
        # Close session
        session.close()
        
    except Exception as e:
        print(f"Error: {e}")
        return False
    
    return True

if __name__ == "__main__":
    if not list_users():
        sys.exit(1)
    
    sys.exit(0)