from __future__ import annotations

from alembic import op

from loltimecheck.storage.models import Base

revision = "0001_initial_mysql_schema"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    Base.metadata.create_all(bind)


def downgrade() -> None:
    bind = op.get_bind()
    Base.metadata.drop_all(bind)
