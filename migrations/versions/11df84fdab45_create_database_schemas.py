"""Create database schemas.

Revision ID: 11df84fdab45
Revises:
Create Date: 2026-09-11

"""

from collections.abc import Sequence

from alembic import op
from sqlalchemy.schema import CreateSchema, DropSchema

revision: str = "11df84fdab45"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


SCHEMAS = (
    "raw",
    "staging",
    "core",
    "analytics",
    "audit",
)


def upgrade() -> None:
    """Cria os schemas estruturais do WV Eleições."""

    for schema in SCHEMAS:
        op.execute(CreateSchema(schema, if_not_exists=True))


def downgrade() -> None:
    """Remove os schemas estruturais do WV Eleições."""

    for schema in reversed(SCHEMAS):
        op.execute(
            DropSchema(
                schema,
                cascade=True,
                if_exists=True,
            )
        )
