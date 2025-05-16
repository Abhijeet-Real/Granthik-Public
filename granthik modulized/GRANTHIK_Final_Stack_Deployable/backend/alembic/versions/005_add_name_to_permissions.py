"""Add name column to permissions table

Revision ID: 005
Revises: 004
Create Date: 2023-05-15

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '005'
down_revision = '004'
branch_labels = None
depends_on = None


def upgrade():
    # Check if the name column exists in permissions table
    from sqlalchemy import inspect
    conn = op.get_bind()
    inspector = inspect(conn)
    columns = [c['name'] for c in inspector.get_columns('permissions')]
    
    # Add name column if it doesn't exist
    if 'name' not in columns:
        op.add_column('permissions', sa.Column('name', sa.String(), nullable=True))
        
        # Update the name column with a combination of resource and action
        op.execute("""
        UPDATE permissions 
        SET name = CONCAT(resource, '_', action)
        """)
        
        # Make the name column not nullable and create a unique index
        op.alter_column('permissions', 'name', nullable=False)
        op.create_index('idx_permissions_name', 'permissions', ['name'], unique=True)


def downgrade():
    # Check if the name column exists before trying to drop it
    from sqlalchemy import inspect
    conn = op.get_bind()
    inspector = inspect(conn)
    columns = [c['name'] for c in inspector.get_columns('permissions')]
    
    if 'name' in columns:
        op.drop_index('idx_permissions_name', table_name='permissions')
        op.drop_column('permissions', 'name')