"""Add roles table

Revision ID: 004
Revises: 003
Create Date: 2023-05-14

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '004'
down_revision = '003'
branch_labels = None
depends_on = None


def upgrade():
    # Check if tables already exist
    from sqlalchemy import inspect
    from sqlalchemy.sql import text
    conn = op.get_bind()
    inspector = inspect(conn)
    existing_tables = inspector.get_table_names()
    
    # Create roles table if it doesn't exist
    if 'roles' not in existing_tables:
        op.create_table(
            'roles',
            sa.Column('id', sa.Integer(), nullable=False),
            sa.Column('name', sa.String(), nullable=False),
            sa.Column('description', sa.String(), nullable=True),
            sa.Column('is_default', sa.Boolean(), nullable=False, default=False),
            sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.Column('updated_at', sa.DateTime(timezone=True), onupdate=sa.func.now(), nullable=True),
            sa.PrimaryKeyConstraint('id'),
            sa.UniqueConstraint('name')
        )
    
    # Create permissions table if it doesn't exist
    if 'permissions' not in existing_tables:
        op.create_table(
            'permissions',
            sa.Column('id', sa.Integer(), nullable=False),
            sa.Column('resource', sa.String(), nullable=False),
            sa.Column('action', sa.String(), nullable=False),
            sa.Column('description', sa.String(), nullable=True),
            sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.PrimaryKeyConstraint('id'),
            sa.UniqueConstraint('resource', 'action', name='uix_resource_action')
        )
    
    # Create user_role association table if it doesn't exist
    if 'user_role' not in existing_tables:
        op.create_table(
            'user_role',
            sa.Column('user_id', sa.Integer(), nullable=False),
            sa.Column('role_id', sa.Integer(), nullable=False),
            sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
            sa.ForeignKeyConstraint(['role_id'], ['roles.id'], ondelete='CASCADE'),
            sa.PrimaryKeyConstraint('user_id', 'role_id')
        )
    
    # Create role_permission association table if it doesn't exist
    if 'role_permission' not in existing_tables:
        op.create_table(
            'role_permission',
            sa.Column('role_id', sa.Integer(), nullable=False),
            sa.Column('permission_id', sa.Integer(), nullable=False),
            sa.ForeignKeyConstraint(['role_id'], ['roles.id'], ondelete='CASCADE'),
            sa.ForeignKeyConstraint(['permission_id'], ['permissions.id'], ondelete='CASCADE'),
            sa.PrimaryKeyConstraint('role_id', 'permission_id')
        )
    
    # Check if default roles exist
    conn = op.get_bind()
    user_role_exists = conn.execute(sa.text("SELECT COUNT(*) FROM roles WHERE name = 'User'")).scalar()
    admin_role_exists = conn.execute(sa.text("SELECT COUNT(*) FROM roles WHERE name = 'Admin'")).scalar()
    
    # Create default roles if they don't exist
    if not user_role_exists:
        op.execute("""
        INSERT INTO roles (name, description, is_default) 
        VALUES ('User', 'Regular user with basic permissions', TRUE)
        """)
    
    if not admin_role_exists:
        op.execute("""
        INSERT INTO roles (name, description, is_default) 
        VALUES ('Admin', 'Administrator with full permissions', FALSE)
        """)
    
    # Check if permissions exist
    permissions_exist = conn.execute(sa.text("SELECT COUNT(*) FROM permissions")).scalar() > 0
    
    # Create basic permissions if they don't exist
    if not permissions_exist:
        op.execute("""
        INSERT INTO permissions (resource, action, description)
        VALUES 
        ('document', 'read', 'Read documents'),
        ('document', 'create', 'Create documents'),
        ('document', 'update', 'Update documents'),
        ('document', 'delete', 'Delete documents'),
        ('chat', 'use', 'Use chat functionality')
        """)
        
        # Assign permissions to roles
        op.execute("""
        INSERT INTO role_permission (role_id, permission_id)
        SELECT 
            (SELECT id FROM roles WHERE name = 'User'), 
            id 
        FROM permissions 
        WHERE (resource = 'document' AND action IN ('read', 'create')) 
           OR (resource = 'chat' AND action = 'use')
        """)
        
        op.execute("""
        INSERT INTO role_permission (role_id, permission_id)
        SELECT 
            (SELECT id FROM roles WHERE name = 'Admin'), 
            id 
        FROM permissions
        """)


def downgrade():
    op.drop_table('role_permission')
    op.drop_table('user_role')
    op.drop_table('permissions')
    op.drop_table('roles')