"""Add missing document fields

Revision ID: 008
Revises: 007
Create Date: 2025-05-15

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '008'
down_revision = '007'
branch_labels = None
depends_on = None


def upgrade():
    # Check if columns exist in documents table
    from sqlalchemy import inspect
    conn = op.get_bind()
    inspector = inspect(conn)
    
    # Get existing columns in documents table
    doc_columns = [col['name'] for col in inspector.get_columns('documents')]
    
    # Add missing columns if they don't exist
    if 'file_size' not in doc_columns:
        op.add_column('documents', sa.Column('file_size', sa.Integer(), nullable=True, server_default='0'))
    
    if 'file_type' not in doc_columns:
        op.add_column('documents', sa.Column('file_type', sa.String(), nullable=True))
    
    if 'document_type' not in doc_columns:
        op.add_column('documents', sa.Column('document_type', sa.String(), nullable=True))
    
    if 'brief_summary' not in doc_columns:
        op.add_column('documents', sa.Column('brief_summary', sa.String(), nullable=True))
    
    if 'ocr_text' not in doc_columns:
        op.add_column('documents', sa.Column('ocr_text', sa.Text(), nullable=True))


def downgrade():
    # We don't want to remove these columns in a downgrade
    pass