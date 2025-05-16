"""Ensure groups table exists

Revision ID: 009
Revises: 008
Create Date: 2025-05-16

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '009'
down_revision = '008'
branch_labels = None
depends_on = None


def upgrade():
    # Check if groups table exists
    from sqlalchemy import inspect
    conn = op.get_bind()
    inspector = inspect(conn)
    
    # Create groups table if it doesn't exist
    if 'groups' not in inspector.get_table_names():
        op.create_table(
            'groups',
            sa.Column('id', sa.Integer(), nullable=False),
            sa.Column('name', sa.String(), nullable=False),
            sa.Column('description', sa.String(), nullable=True),
            sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
            sa.Column('updated_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
            sa.PrimaryKeyConstraint('id')
        )
        
        # Create index on group name
        op.create_index(op.f('ix_groups_name'), 'groups', ['name'], unique=True)
    
    # Check if user_groups table exists
    if 'user_groups' not in inspector.get_table_names():
        op.create_table(
            'user_groups',
            sa.Column('user_id', sa.Integer(), nullable=False),
            sa.Column('group_id', sa.Integer(), nullable=False),
            sa.ForeignKeyConstraint(['group_id'], ['groups.id'], ondelete='CASCADE'),
            sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
            sa.PrimaryKeyConstraint('user_id', 'group_id')
        )
    
    # Check if document_groups table exists
    if 'document_groups' not in inspector.get_table_names():
        op.create_table(
            'document_groups',
            sa.Column('document_id', sa.Integer(), nullable=False),
            sa.Column('group_id', sa.Integer(), nullable=False),
            sa.ForeignKeyConstraint(['document_id'], ['documents.id'], ondelete='CASCADE'),
            sa.ForeignKeyConstraint(['group_id'], ['groups.id'], ondelete='CASCADE'),
            sa.PrimaryKeyConstraint('document_id', 'group_id')
        )


def downgrade():
    # We don't want to drop these tables in a downgrade
    pass