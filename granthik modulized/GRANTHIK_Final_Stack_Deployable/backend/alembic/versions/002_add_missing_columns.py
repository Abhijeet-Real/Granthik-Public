"""Add missing columns

Revision ID: 002
Revises: 001
Create Date: 2025-05-13

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '002'
down_revision = '001'
branch_labels = None
depends_on = None


def upgrade():
    # Add missing columns to documents table
    from sqlalchemy.exc import ProgrammingError
    from sqlalchemy import inspect
    from sqlalchemy.engine.reflection import Inspector
    from alembic import op
    
    # Get database connection
    conn = op.get_bind()
    inspector = inspect(conn)
    
    # Check if columns exist before adding them
    doc_columns = [col['name'] for col in inspector.get_columns('documents')]
    if 'chunk_size' not in doc_columns:
        op.add_column('documents', sa.Column('chunk_size', sa.Integer(), nullable=False, server_default='1000'))
    if 'chunk_overlap' not in doc_columns:
        op.add_column('documents', sa.Column('chunk_overlap', sa.Integer(), nullable=False, server_default='200'))
    if 'chunking_strategy' not in doc_columns:
        op.add_column('documents', sa.Column('chunking_strategy', sa.String(), nullable=False, server_default='hybrid'))
    
    # Check if columns exist in document_summaries
    summary_columns = [col['name'] for col in inspector.get_columns('document_summaries')]
    if 'summary_type' not in summary_columns:
        op.add_column('document_summaries', sa.Column('summary_type', sa.String(), nullable=False, server_default='comprehensive'))
    if 'created_by_id' not in summary_columns:
        op.add_column('document_summaries', sa.Column('created_by_id', sa.Integer(), nullable=True))
        # Add foreign key only if column was added
        op.create_foreign_key(None, 'document_summaries', 'users', ['created_by_id'], ['id'], ondelete='SET NULL')
    
    # Check if tags table exists
    tables = inspector.get_table_names()
    if 'tags' not in tables:
        # Create tags table
        op.create_table(
            'tags',
            sa.Column('id', sa.Integer(), nullable=False),
            sa.Column('name', sa.String(), nullable=False),
            sa.Column('color', sa.String(), nullable=False, server_default='#3f51b5'),
            sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.PrimaryKeyConstraint('id'),
            sa.UniqueConstraint('name')
        )
    
    # Check if document_tag table exists
    if 'document_tag' not in tables:
        # Create document_tag association table
        op.create_table(
            'document_tag',
            sa.Column('document_id', sa.Integer(), nullable=False),
            sa.Column('tag_id', sa.Integer(), nullable=False),
            sa.ForeignKeyConstraint(['document_id'], ['documents.id'], ondelete='CASCADE'),
            sa.ForeignKeyConstraint(['tag_id'], ['tags.id'], ondelete='CASCADE'),
            sa.PrimaryKeyConstraint('document_id', 'tag_id')
        )


def downgrade():
    # Drop document_tag association table
    op.drop_table('document_tag')
    
    # Drop tags table
    op.drop_table('tags')
    
    # Drop foreign key constraint for created_by_id
    op.drop_constraint(None, 'document_summaries', type_='foreignkey')
    
    # Remove columns from document_summaries table
    op.drop_column('document_summaries', 'created_by_id')
    op.drop_column('document_summaries', 'summary_type')
    
    # Remove columns from documents table
    op.drop_column('documents', 'chunking_strategy')
    op.drop_column('documents', 'chunk_overlap')
    op.drop_column('documents', 'chunk_size')