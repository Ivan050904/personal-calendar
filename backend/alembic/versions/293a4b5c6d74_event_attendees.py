"""Shared events (D38, wave 6): attendees invited by login."""
import sqlalchemy as sa
from alembic import op

revision = '293a4b5c6d74'
down_revision = '18293a4b5c63'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('event_attendees',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('event_id', sa.String(64), sa.ForeignKey('events.id'), nullable=False),
        sa.Column('principal_id', sa.String(64), sa.ForeignKey('calendar_principals.id'), nullable=False),
        sa.Column('status', sa.String(16), nullable=False), sa.Column('invited_at', sa.DateTime(), nullable=False),
        sa.Column('responded_at', sa.DateTime()),
        sa.UniqueConstraint('event_id', 'principal_id', name='uq_event_attendee'))
    op.create_index('ix_event_attendees_event_id', 'event_attendees', ['event_id'])
    op.create_index('ix_event_attendees_principal_id', 'event_attendees', ['principal_id'])


def downgrade():
    # The table's indexes go with it (MySQL/MariaDB refuse to drop an index a foreign key uses).
    op.drop_table('event_attendees')
