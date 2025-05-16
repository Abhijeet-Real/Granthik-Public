"""Add document processing columns

Revision ID: 006
Revises: 005
Create Date: 2023-05-15

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '006'
down_revision = '005'
branch_labels = None
depends_on = None


def upgrade():
    # Check if columns exist in documents table
    from sqlalchemy import inspect
    conn = op.get_bind()
    inspector = inspect(conn)
    columns = [c['name'] for c in inspector.get_columns('documents')]
    
    # Add missing columns if they don't exist
    if 'chunk_size' not in columns:
        op.add_column('documents', sa.Column('chunk_size', sa.Integer(), nullable=True, server_default='1000'))
    
    if 'chunk_overlap' not in columns:
        op.add_column('documents', sa.Column('chunk_overlap', sa.Integer(), nullable=True, server_default='200'))
    
    if 'chunking_strategy' not in columns:
        op.add_column('documents', sa.Column('chunking_strategy', sa.String(), nullable=True, server_default='hybrid'))
    
    if 'processing_status' not in columns:
        op.add_column('documents', sa.Column('processing_status', sa.String(), nullable=True, server_default='pending'))
    
    if 'processing_progress' not in columns:
        op.add_column('documents', sa.Column('processing_progress', sa.Integer(), nullable=True, server_default='0'))
    
    if 'processing_message' not in columns:
        op.add_column('documents', sa.Column('processing_message', sa.String(), nullable=True))


def downgrade():
    # We don't want to remove these columns in a downgrade
    pass