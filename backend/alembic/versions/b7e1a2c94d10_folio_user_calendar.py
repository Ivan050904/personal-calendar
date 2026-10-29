"""Each Folio account owns its own calendar."""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "b7e1a2c94d10"
down_revision: Union[str, Sequence[str], None] = "a1b2c3d4e5f6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("calendars", sa.Column("folio_user_id", sa.String(length=64), nullable=True))
    op.create_index("ix_calendars_folio_user_id", "calendars", ["folio_user_id"], unique=True)


def downgrade() -> None:
    op.drop_index("ix_calendars_folio_user_id", table_name="calendars")
    op.drop_column("calendars", "folio_user_id")
