"""Add user approval fields

Revision ID: 003
Revises: 002
Create Date: 2023-05-14 10:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import Column, String, Boolean, text


# revision identifiers, used by Alembic.
revision = '003'
down_revision = '002'
branch_labels = None
depends_on = None


def upgrade():
    # Add is_approved column
    op.add_column('users', sa.Column('is_approved', sa.Boolean(), nullable=True))
    
    # Add approval_status column
    op.add_column('users', sa.Column('approval_status', sa.String(), nullable=True))
    
    # Add password_reset_required column
    op.add_column('users', sa.Column('password_reset_required', sa.Boolean(), nullable=True))
    
    # Set default values for existing records
    # Existing users are considered approved
    op.execute(text("UPDATE users SET is_approved = TRUE, approval_status = 'approved', password_reset_required = FALSE WHERE is_active = TRUE"))
    op.execute(text("UPDATE users SET is_approved = FALSE, approval_status = 'pending', password_reset_required = TRUE WHERE (is_approved IS NULL OR approval_status IS NULL)"))


def downgrade():
    # Remove columns
    op.drop_column('users', 'password_reset_required')
    op.drop_column('users', 'approval_status')
    op.drop_column('users', 'is_approved')