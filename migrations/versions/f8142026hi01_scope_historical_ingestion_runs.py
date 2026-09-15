"""Scope TSE candidate ingestion runs by election year.

Revision ID: f8142026hi01
Revises: e7032026id01
"""

import sqlalchemy as sa
from alembic import op

revision = "f8142026hi01"
down_revision = "e7032026id01"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "ingestion_run",
        sa.Column(
            "scope_key",
            sa.String(length=120),
            server_default=sa.text("'global'"),
            nullable=False,
        ),
        schema="audit",
    )
    # Before this revision, the only persisted TSE/candidatos pipeline was 2026.
    # Preserve that historical meaning before 2022 starts sharing the logical dataset.
    op.execute(
        "UPDATE audit.ingestion_run "
        "SET scope_key = 'election-year:2026' "
        "WHERE source = 'TSE' AND dataset = 'candidatos'"
    )
    op.create_check_constraint(
        "ck_ingestion_run_scope_key_not_blank",
        "ingestion_run",
        "btrim(scope_key) <> ''",
        schema="audit",
    )
    op.create_index(
        "ix_ingestion_run_source_dataset_scope_status",
        "ingestion_run",
        ["source", "dataset", "scope_key", "status", "finished_at", "id"],
        unique=False,
        schema="audit",
    )


def downgrade() -> None:
    op.drop_index(
        "ix_ingestion_run_source_dataset_scope_status",
        table_name="ingestion_run",
        schema="audit",
    )
    op.drop_constraint(
        "ck_ingestion_run_scope_key_not_blank",
        "ingestion_run",
        type_="check",
        schema="audit",
    )
    op.drop_column("ingestion_run", "scope_key", schema="audit")
