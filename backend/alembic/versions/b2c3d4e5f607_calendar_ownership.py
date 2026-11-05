"""Add principal ownership without guessing the owner of existing personal data."""
import sqlalchemy as sa
from alembic import op

revision = 'b2c3d4e5f607'
down_revision = 'a1b2c3d4e5f6'
branch_labels = None
depends_on = None

REVISION_TABLES = ('calendars','events','recurrence_rules','event_exceptions','plans','plan_tasks','tasks','lists','list_items','categories','reminders','settings')


def upgrade():
    op.create_table('calendar_principals',
        sa.Column('id', sa.String(64), primary_key=True), sa.Column('folio_user_id', sa.String(64), unique=True),
        sa.Column('legacy_alias', sa.String(255), unique=True), sa.Column('active', sa.Boolean(), nullable=False))
    for table in REVISION_TABLES:
        op.add_column(table, sa.Column('revision', sa.Integer(), server_default='1', nullable=False))
    for table in ('calendars','recurrence_rules','settings','ai_drafts'):
        with op.batch_alter_table(table) as batch:
            batch.add_column(sa.Column('owner_id', sa.String(64), nullable=True))
            batch.create_foreign_key(f'fk_{table}_owner', 'calendar_principals', ['owner_id'], ['id'])
            batch.create_index(f'ix_{table}_owner_id', ['owner_id'])
    with op.batch_alter_table('calendars') as batch:
        batch.add_column(sa.Column('default_owner', sa.String(64), nullable=True))
        batch.create_unique_constraint('uq_calendars_default_owner', ['default_owner'])
    with op.batch_alter_table('recurrence_rules') as batch:
        batch.add_column(sa.Column('dst_gap_policy', sa.String(16), nullable=False, server_default='skip'))
        batch.add_column(sa.Column('dst_fold_policy', sa.String(16), nullable=False, server_default='earlier'))
    with op.batch_alter_table('events') as batch:
        batch.alter_column('start_at', existing_type=sa.DateTime(), nullable=True)
        batch.alter_column('end_at', existing_type=sa.DateTime(), nullable=True)
        batch.add_column(sa.Column('start_date', sa.Date()))
        batch.add_column(sa.Column('end_date_exclusive', sa.Date()))
        batch.add_column(sa.Column('location', sa.String(255)))
    with op.batch_alter_table('reminders') as batch:
        batch.add_column(sa.Column('enabled', sa.Boolean(), server_default=sa.true(), nullable=False))
        batch.add_column(sa.Column('reminder_time', sa.String(5)))
    # SQLite may reflect an unnamed constraint; give it a stable batch name.
    unique_keys = [item for item in sa.inspect(op.get_bind()).get_unique_constraints('settings') if item['column_names'] == ['key']]
    with op.batch_alter_table('settings', naming_convention={'uq':'uq_%(table_name)s_%(column_0_name)s'}) as batch:
        for key in unique_keys:
            batch.drop_constraint(key['name'] or 'uq_settings_key', type_='unique')
        batch.create_unique_constraint('uq_owner_setting', ['owner_id','key'])
    op.create_table('calendar_sessions',
        sa.Column('id', sa.String(64), primary_key=True), sa.Column('token_hash', sa.String(64), unique=True, nullable=False),
        sa.Column('principal_id', sa.String(64), sa.ForeignKey('calendar_principals.id'), nullable=False),
        sa.Column('expires_at', sa.DateTime(), nullable=False), sa.Column('revoked_at', sa.DateTime()))
    op.create_index('ix_calendar_sessions_principal_id','calendar_sessions',['principal_id'])


def downgrade():
    raise RuntimeError('Ownership downgrade is destructive; restore a reviewed backup instead.')
