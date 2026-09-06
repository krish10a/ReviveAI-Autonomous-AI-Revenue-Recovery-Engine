"""add scenario_key to recovery_cases

Revision ID: 4g93108bf291
Revises: 3f82027819f2
Create Date: 2026-09-06 19:06:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '4g93108bf291'
down_revision: Union[str, Sequence[str], None] = '3f82027819f2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    columns = [c['name'] for c in inspector.get_columns('recovery_cases')]
    if 'scenario_key' not in columns:
        op.add_column('recovery_cases', sa.Column('scenario_key', sa.String(length=100), nullable=True))
    indexes = [i['name'] for i in inspector.get_indexes('recovery_cases')]
    if 'ix_recovery_cases_scenario_key' not in indexes:
        op.create_index(op.f('ix_recovery_cases_scenario_key'), 'recovery_cases', ['scenario_key'], unique=True)


def downgrade() -> None:
    """Downgrade schema."""
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    indexes = [i['name'] for i in inspector.get_indexes('recovery_cases')]
    if 'ix_recovery_cases_scenario_key' in indexes:
        op.drop_index(op.f('ix_recovery_cases_scenario_key'), table_name='recovery_cases')
    columns = [c['name'] for c in inspector.get_columns('recovery_cases')]
    if 'scenario_key' in columns:
        op.drop_column('recovery_cases', 'scenario_key')
