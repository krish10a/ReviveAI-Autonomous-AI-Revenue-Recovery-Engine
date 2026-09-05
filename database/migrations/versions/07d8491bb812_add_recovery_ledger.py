"""add recovery ledger

Revision ID: 07d8491bb812
Revises: 06c7389ae737
Create Date: 2026-09-05 12:00:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '07d8491bb812'
down_revision: Union[str, Sequence[str], None] = '06c7389ae737'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'recovery_ledger',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('case_id', sa.Integer(), nullable=False),
        sa.Column('payment_id', sa.Integer(), nullable=False),
        sa.Column('gross_amount', sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column('action_cost', sa.Numeric(precision=10, scale=2), nullable=False, server_default='0.00'),
        sa.Column('net_recovered', sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column('recovery_action', sa.String(length=50), nullable=False),
        sa.Column('provider_reference', sa.String(length=100), nullable=True),
        sa.Column('recovered_at', sa.DateTime(), nullable=False),
        sa.Column('details', sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(['case_id'], ['recovery_cases.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['payment_id'], ['payments.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_recovery_ledger_id'), 'recovery_ledger', ['id'], unique=False)
    op.create_index(op.f('ix_recovery_ledger_case_id'), 'recovery_ledger', ['case_id'], unique=False)
    op.create_index(op.f('ix_recovery_ledger_payment_id'), 'recovery_ledger', ['payment_id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_recovery_ledger_payment_id'), table_name='recovery_ledger')
    op.drop_index(op.f('ix_recovery_ledger_case_id'), table_name='recovery_ledger')
    op.drop_index(op.f('ix_recovery_ledger_id'), table_name='recovery_ledger')
    op.drop_table('recovery_ledger')
