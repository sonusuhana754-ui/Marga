"""Initial schema with database_test table

Revision ID: 1a2b3c4d5e6f
Revises: 
Create Date: 2026-08-29 19:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '1a2b3c4d5e6f'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'database_test',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('value', sa.String(length=255), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_database_test_id'), 'database_test', ['id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_database_test_id'), table_name='database_test')
    op.drop_table('database_test')
