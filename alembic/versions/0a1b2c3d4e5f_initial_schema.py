"""initial schema

Revision ID: 0a1b2c3d4e5f
Revises: 
Create Date: 2026-09-16 16:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '0a1b2c3d4e5f'
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table('orders',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('customer_name', sa.String(), nullable=True),
    sa.Column('item', sa.String(), nullable=True),
    sa.Column('quantity', sa.Float(), nullable=True),
    sa.Column('date', sa.DateTime(), nullable=True),
    sa.Column('status', sa.String(), nullable=True),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_orders_id'), 'orders', ['id'], unique=False)

    op.create_table('releases',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('version', sa.String(), nullable=True),
    sa.Column('environment', sa.String(), nullable=True),
    sa.Column('deployment_status', sa.String(), nullable=True),
    sa.Column('health_status', sa.String(), nullable=True),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_releases_id'), 'releases', ['id'], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f('ix_releases_id'), table_name='releases')
    op.drop_table('releases')
    op.drop_index(op.f('ix_orders_id'), table_name='orders')
    op.drop_table('orders')
