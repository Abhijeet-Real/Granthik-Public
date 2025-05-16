"""Initial migration

Revision ID: 001
Revises: 
Create Date: 2023-10-01

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '001'
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    # Create users table
    op.create_table(
        'users',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('email', sa.String(), nullable=False),
        sa.Column('username', sa.String(), nullable=False),
        sa.Column('hashed_password', sa.String(), nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=False, default=True),
        sa.Column('is_superuser', sa.Boolean(), nullable=False, default=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), onupdate=sa.func.now(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('email'),
        sa.UniqueConstraint('username')
    )
    
    # Create groups table
    op.create_table(
        'groups',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(), nullable=False),
        sa.Column('description', sa.String(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), onupdate=sa.func.now(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('name')
    )
    
    # Create user_group association table
    op.create_table(
        'user_group',
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('group_id', sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['group_id'], ['groups.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('user_id', 'group_id')
    )
    
    # Create documents table
    op.create_table(
        'documents',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('filename', sa.String(), nullable=False),
        sa.Column('file_path', sa.String(), nullable=False),
        sa.Column('file_id', sa.String(), nullable=False),
        sa.Column('owner_id', sa.Integer(), nullable=False),
        sa.Column('is_public', sa.Boolean(), nullable=False, default=False),
        sa.Column('chunk_count', sa.Integer(), nullable=False, default=0),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), onupdate=sa.func.now(), nullable=True),
        sa.ForeignKeyConstraint(['owner_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('file_id')
    )
    
    # Create document_group association table
    op.create_table(
        'document_group',
        sa.Column('document_id', sa.Integer(), nullable=False),
        sa.Column('group_id', sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(['document_id'], ['documents.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['group_id'], ['groups.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('document_id', 'group_id')
    )
    
    # Create document_summaries table
    op.create_table(
        'document_summaries',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('document_id', sa.Integer(), nullable=False),
        sa.Column('summary_text', sa.Text(), nullable=False),
        sa.Column('model_used', sa.String(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(['document_id'], ['documents.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    
    # Create chat_history table
    op.create_table(
        'chat_history',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('query', sa.Text(), nullable=False),
        sa.Column('answer', sa.Text(), nullable=False),
        sa.Column('model_used', sa.String(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )


def downgrade():
    op.drop_table('chat_history')
    op.drop_table('document_summaries')
    op.drop_table('document_group')
    op.drop_table('documents')
    op.drop_table('user_group')
    op.drop_table('groups')
    op.drop_table('users')