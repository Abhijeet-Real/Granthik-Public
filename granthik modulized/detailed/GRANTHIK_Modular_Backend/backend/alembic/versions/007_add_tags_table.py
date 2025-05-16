"""Add tags table

Revision ID: 007
Revises: 006
Create Date: 2023-05-15

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '007'
down_revision = '006'
branch_labels = None
depends_on = None


def upgrade():
    # Check if tables already exist
    from sqlalchemy import inspect
    conn = op.get_bind()
    inspector = inspect(conn)
    existing_tables = inspector.get_table_names()
    
    # Create tags table if it doesn't exist
    if 'tags' not in existing_tables:
        op.create_table(
            'tags',
            sa.Column('id', sa.Integer(), nullable=False),
            sa.Column('name', sa.String(), nullable=False),
            sa.Column('color', sa.String(), nullable=False, server_default='#3f51b5'),
            sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.PrimaryKeyConstraint('id'),
            sa.UniqueConstraint('name')
        )
    
    # Create document_tag association table if it doesn't exist
    if 'document_tag' not in existing_tables:
        op.create_table(
            'document_tag',
            sa.Column('document_id', sa.Integer(), nullable=False),
            sa.Column('tag_id', sa.Integer(), nullable=False),
            sa.ForeignKeyConstraint(['document_id'], ['documents.id'], ondelete='CASCADE'),
            sa.ForeignKeyConstraint(['tag_id'], ['tags.id'], ondelete='CASCADE'),
            sa.PrimaryKeyConstraint('document_id', 'tag_id')
        )


def downgrade():
    op.drop_table('document_tag')
    op.drop_table('tags')