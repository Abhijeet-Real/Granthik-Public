"""Add summary_type and created_by_id columns to document_summaries table

Revision ID: add_summary_type_column
Revises: 
Create Date: 2023-07-10 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'add_summary_type_column'
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    # Add summary_type column with default value
    op.add_column('document_summaries', sa.Column('summary_type', sa.String(), nullable=True, server_default='comprehensive'))
    
    # Add created_by_id column
    op.add_column('document_summaries', sa.Column('created_by_id', sa.Integer(), nullable=True))
    
    # Add foreign key constraint
    op.create_foreign_key(
        'fk_document_summaries_created_by_id_users',
        'document_summaries', 'users',
        ['created_by_id'], ['id']
    )


def downgrade():
    # Drop foreign key constraint
    op.drop_constraint('fk_document_summaries_created_by_id_users', 'document_summaries', type_='foreignkey')
    
    # Drop columns
    op.drop_column('document_summaries', 'created_by_id')
    op.drop_column('document_summaries', 'summary_type')