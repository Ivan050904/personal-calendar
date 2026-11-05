"""Atomic command receipts, stable confirmations and owner-scoped changes."""
import sqlalchemy as sa
from alembic import op

revision = 'c3d4e5f60718'
down_revision = 'b2c3d4e5f607'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('event_exceptions', sa.Column('override_payload', sa.JSON(), nullable=False, server_default='{}'))
    op.create_table('calendar_write_receipts',
        sa.Column('owner_id', sa.String(64), sa.ForeignKey('calendar_principals.id'), primary_key=True),
        sa.Column('command_id', sa.String(36), primary_key=True), sa.Column('body_hash', sa.String(64), nullable=False),
        sa.Column('result', sa.JSON(), nullable=False), sa.Column('created_at', sa.DateTime(), nullable=False))
    op.create_table('calendar_confirmations',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('owner_id', sa.String(64), sa.ForeignKey('calendar_principals.id'), nullable=False),
        sa.Column('calendar_id', sa.String(64), sa.ForeignKey('calendars.id'), nullable=False),
        sa.Column('entity_id', sa.String(64), nullable=False), sa.Column('kind', sa.String(10), nullable=False),
        sa.Column('occurrence_ref', sa.String(100), nullable=False), sa.Column('revision', sa.Integer(), nullable=False),
        sa.Column('status', sa.String(20), nullable=False), sa.Column('happened_date', sa.Date(), nullable=False),
        sa.Column('happened_at', sa.DateTime()), sa.Column('time_zone', sa.String(64), nullable=False),
        sa.Column('title', sa.String(255), nullable=False), sa.Column('recorded_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False), sa.Column('audit', sa.JSON(), nullable=False),
        sa.Column('previous_due_date', sa.Date()), sa.Column('next_due_date', sa.Date()),
        sa.UniqueConstraint('owner_id','entity_id','occurrence_ref',name='uq_calendar_fact_occurrence'))
    for column in ('owner_id','calendar_id','entity_id','happened_date'):
        op.create_index(f'ix_calendar_confirmations_{column}', 'calendar_confirmations', [column])
    op.create_table('calendar_changes',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('owner_id', sa.String(64), sa.ForeignKey('calendar_principals.id'), nullable=False),
        sa.Column('calendar_id', sa.String(64), sa.ForeignKey('calendars.id'), nullable=False),
        sa.Column('entity_id', sa.String(64), nullable=False), sa.Column('kind', sa.String(20), nullable=False),
        sa.Column('operation', sa.String(20), nullable=False), sa.Column('revision', sa.Integer(), nullable=False),
        sa.Column('changed_at', sa.DateTime(), nullable=False), sa.Column('deleted', sa.Boolean(), nullable=False))
    for column in ('owner_id','calendar_id'):
        op.create_index(f'ix_calendar_changes_{column}', 'calendar_changes', [column])


def downgrade():
    raise RuntimeError('Command history downgrade is destructive; restore a reviewed backup instead.')
