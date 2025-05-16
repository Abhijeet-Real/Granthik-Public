"""
Migration script to add user approval fields to the users table
"""
import logging
from sqlalchemy import Column, String, Boolean, text
from alembic import op

logger = logging.getLogger("uvicorn")

def upgrade():
    """
    Add user approval fields to the users table
    """
    try:
        # Add is_approved column
        op.add_column('users', Column('is_approved', Boolean, nullable=True))
        
        # Add approval_status column
        op.add_column('users', Column('approval_status', String, nullable=True))
        
        # Add password_reset_required column
        op.add_column('users', Column('password_reset_required', Boolean, nullable=True))
        
        # Set default values for existing records
        # Existing users are considered approved
        op.execute(text("UPDATE users SET is_approved = TRUE, approval_status = 'approved', password_reset_required = FALSE WHERE is_active = TRUE"))
        op.execute(text("UPDATE users SET is_approved = FALSE, approval_status = 'pending', password_reset_required = TRUE WHERE (is_approved IS NULL OR approval_status IS NULL)"))
        
        logger.info("Successfully added user approval fields to users table")
    except Exception as e:
        logger.error(f"Error adding user approval fields: {str(e)}")
        raise

def downgrade():
    """
    Remove user approval fields from the users table
    """
    try:
        op.drop_column('users', 'password_reset_required')
        op.drop_column('users', 'approval_status')
        op.drop_column('users', 'is_approved')
        
        logger.info("Successfully removed user approval fields from users table")
    except Exception as e:
        logger.error(f"Error removing user approval fields: {str(e)}")
        raise