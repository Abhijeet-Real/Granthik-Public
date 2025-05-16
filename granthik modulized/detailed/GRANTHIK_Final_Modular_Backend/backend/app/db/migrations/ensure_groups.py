"""
Script to ensure the groups table and related association tables exist
"""
import os
import sys
from sqlalchemy import create_engine, inspect, MetaData, Table, Column, Integer, String, ForeignKey, DateTime, func
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

# Add the parent directory to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from app.core.config import settings

# Create SQLAlchemy engine and session
DATABASE_URL = f"postgresql://{settings.POSTGRES_USER}:{settings.POSTGRES_PASSWORD}@{settings.POSTGRES_SERVER}:{settings.POSTGRES_PORT}/{settings.POSTGRES_DB}"
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()
metadata = MetaData()

def run_migration():
    """Run the migration to ensure groups table exists"""
    inspector = inspect(engine)
    
    # Check if groups table exists
    if 'groups' not in inspector.get_table_names():
        print("Creating groups table...")
        groups = Table(
            'groups',
            metadata,
            Column('id', Integer, primary_key=True),
            Column('name', String, unique=True, index=True),
            Column('description', String, nullable=True),
            Column('created_at', DateTime(timezone=True), server_default=func.now()),
            Column('updated_at', DateTime(timezone=True), onupdate=func.now())
        )
        groups.create(engine)
        print("Groups table created successfully.")
    else:
        print("Groups table already exists.")
    
    # Check if user_group association table exists
    if 'user_group' not in inspector.get_table_names():
        print("Creating user_group association table...")
        user_group = Table(
            'user_group',
            metadata,
            Column('user_id', Integer, ForeignKey('users.id')),
            Column('group_id', Integer, ForeignKey('groups.id'))
        )
        user_group.create(engine)
        print("user_group association table created successfully.")
    else:
        print("user_group association table already exists.")
    
    # Check if document_group association table exists
    if 'document_group' not in inspector.get_table_names():
        print("Creating document_group association table...")
        document_group = Table(
            'document_group',
            metadata,
            Column('document_id', Integer, ForeignKey('documents.id')),
            Column('group_id', Integer, ForeignKey('groups.id'))
        )
        document_group.create(engine)
        print("document_group association table created successfully.")
    else:
        print("document_group association table already exists.")
    
    print("Migration completed successfully.")

if __name__ == "__main__":
    run_migration()