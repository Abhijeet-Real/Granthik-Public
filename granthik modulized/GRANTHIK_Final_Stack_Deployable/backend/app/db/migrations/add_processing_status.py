"""
Migration script to add processing status fields to the documents table
"""
import logging
from sqlalchemy import Column, String, Integer, text
from alembic import op

logger = logging.getLogger("uvicorn")

def upgrade():
    """
    Add processing status fields to the documents table
    """
    try:
        # Add processing_status column
        op.add_column('documents', Column('processing_status', String, nullable=True))
        
        # Add processing_progress column
        op.add_column('documents', Column('processing_progress', Integer, nullable=True))
        
        # Add processing_message column
        op.add_column('documents', Column('processing_message', String, nullable=True))
        
        # Set default values for existing records
        op.execute(text("UPDATE documents SET processing_status = 'completed', processing_progress = 100 WHERE chunk_count > 0"))
        op.execute(text("UPDATE documents SET processing_status = 'pending', processing_progress = 0 WHERE (processing_status IS NULL OR processing_status = '')"))
        
        logger.info("Successfully added processing status fields to documents table")
    except Exception as e:
        logger.error(f"Error adding processing status fields: {str(e)}")
        raise

def downgrade():
    """
    Remove processing status fields from the documents table
    """
    try:
        op.drop_column('documents', 'processing_message')
        op.drop_column('documents', 'processing_progress')
        op.drop_column('documents', 'processing_status')
        
        logger.info("Successfully removed processing status fields from documents table")
    except Exception as e:
        logger.error(f"Error removing processing status fields: {str(e)}")
        raise