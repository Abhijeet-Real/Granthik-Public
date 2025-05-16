"""
Migration script to add new fields to the Document model
"""
import os
import sys
import logging
from sqlalchemy import create_engine, Column, Integer, String, Text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from alembic import op
import sqlalchemy as sa

# Add parent directory to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.config import settings

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def upgrade():
    """
    Add new fields to the documents table
    """
    try:
        logger.info("Starting migration to add new document fields")
        
        # Create database connection
        engine = create_engine(settings.DATABASE_URI)
        SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
        db = SessionLocal()
        
        # Add new columns if they don't exist
        inspector = sa.inspect(engine)
        columns = [col['name'] for col in inspector.get_columns('documents')]
        
        # Add file_size column
        if 'file_size' not in columns:
            logger.info("Adding file_size column to documents table")
            op.add_column('documents', sa.Column('file_size', sa.Integer(), nullable=True, server_default='0'))
        
        # Add file_type column
        if 'file_type' not in columns:
            logger.info("Adding file_type column to documents table")
            op.add_column('documents', sa.Column('file_type', sa.String(), nullable=True))
        
        # Add document_type column
        if 'document_type' not in columns:
            logger.info("Adding document_type column to documents table")
            op.add_column('documents', sa.Column('document_type', sa.String(), nullable=True))
        
        # Add brief_summary column
        if 'brief_summary' not in columns:
            logger.info("Adding brief_summary column to documents table")
            op.add_column('documents', sa.Column('brief_summary', sa.String(), nullable=True))
        
        # Add ocr_text column
        if 'ocr_text' not in columns:
            logger.info("Adding ocr_text column to documents table")
            op.add_column('documents', sa.Column('ocr_text', sa.Text(), nullable=True))
        
        db.commit()
        logger.info("Migration completed successfully")
    
    except Exception as e:
        logger.error(f"Error during migration: {str(e)}")
        raise

def downgrade():
    """
    Remove the added columns
    """
    try:
        logger.info("Starting downgrade to remove new document fields")
        
        # Create database connection
        engine = create_engine(settings.DATABASE_URI)
        
        # Remove columns
        op.drop_column('documents', 'file_size')
        op.drop_column('documents', 'file_type')
        op.drop_column('documents', 'document_type')
        op.drop_column('documents', 'brief_summary')
        op.drop_column('documents', 'ocr_text')
        
        logger.info("Downgrade completed successfully")
    
    except Exception as e:
        logger.error(f"Error during downgrade: {str(e)}")
        raise

if __name__ == "__main__":
    upgrade()