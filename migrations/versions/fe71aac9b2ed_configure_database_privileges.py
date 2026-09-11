"""Configure database privileges.

Revision ID: fe71aac9b2ed
Revises: 11df84fdab45
Create Date: 2026-09-11

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "fe71aac9b2ed"
down_revision: str | None = "11df84fdab45"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


OWNER_ROLE = "wv_eleicoes_owner"
INGESTION_ROLE = "wv_eleicoes_ingestion"
API_ROLE = "wv_eleicoes_api"

INGESTION_WRITE_SCHEMAS = (
    "raw",
    "staging",
    "core",
    "analytics",
)

API_READ_SCHEMAS = (
    "core",
    "analytics",
)

AUDIT_SCHEMA = "audit"


def _execute(statement: str) -> None:
    """Executa DDL administrativo dentro da migration."""

    op.execute(sa.text(statement))


def _grant_ingestion_schema(schema: str) -> None:
    """Concede à ingestão acesso aos dados, mas não à estrutura."""

    _execute(f"GRANT USAGE ON SCHEMA {schema} TO {INGESTION_ROLE}")

    _execute(
        f"GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA {schema} TO {INGESTION_ROLE}"
    )

    _execute(f"GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA {schema} TO {INGESTION_ROLE}")

    _execute(
        f"ALTER DEFAULT PRIVILEGES "
        f"FOR ROLE {OWNER_ROLE} "
        f"IN SCHEMA {schema} "
        f"GRANT SELECT, INSERT, UPDATE, DELETE "
        f"ON TABLES TO {INGESTION_ROLE}"
    )

    _execute(
        f"ALTER DEFAULT PRIVILEGES "
        f"FOR ROLE {OWNER_ROLE} "
        f"IN SCHEMA {schema} "
        f"GRANT USAGE, SELECT "
        f"ON SEQUENCES TO {INGESTION_ROLE}"
    )


def _grant_api_schema(schema: str) -> None:
    """Concede à API somente leitura nos schemas publicados."""

    _execute(f"GRANT USAGE ON SCHEMA {schema} TO {API_ROLE}")

    _execute(f"GRANT SELECT ON ALL TABLES IN SCHEMA {schema} TO {API_ROLE}")

    _execute(
        f"ALTER DEFAULT PRIVILEGES "
        f"FOR ROLE {OWNER_ROLE} "
        f"IN SCHEMA {schema} "
        f"GRANT SELECT ON TABLES TO {API_ROLE}"
    )


def _grant_audit_schema() -> None:
    """Permite registrar e atualizar execuções do pipeline."""

    _execute(f"GRANT USAGE ON SCHEMA {AUDIT_SCHEMA} TO {INGESTION_ROLE}")

    _execute(
        f"GRANT SELECT, INSERT, UPDATE ON ALL TABLES IN SCHEMA {AUDIT_SCHEMA} TO {INGESTION_ROLE}"
    )

    _execute(f"GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA {AUDIT_SCHEMA} TO {INGESTION_ROLE}")

    _execute(
        f"ALTER DEFAULT PRIVILEGES "
        f"FOR ROLE {OWNER_ROLE} "
        f"IN SCHEMA {AUDIT_SCHEMA} "
        f"GRANT SELECT, INSERT, UPDATE "
        f"ON TABLES TO {INGESTION_ROLE}"
    )

    _execute(
        f"ALTER DEFAULT PRIVILEGES "
        f"FOR ROLE {OWNER_ROLE} "
        f"IN SCHEMA {AUDIT_SCHEMA} "
        f"GRANT USAGE, SELECT "
        f"ON SEQUENCES TO {INGESTION_ROLE}"
    )


def upgrade() -> None:
    """Configura privilégios seguindo o princípio de menor privilégio."""

    for schema in INGESTION_WRITE_SCHEMAS:
        _grant_ingestion_schema(schema)

    _grant_audit_schema()

    for schema in API_READ_SCHEMAS:
        _grant_api_schema(schema)


def downgrade() -> None:
    """Remove os privilégios configurados por esta migration."""

    for schema in API_READ_SCHEMAS:
        _execute(
            f"ALTER DEFAULT PRIVILEGES "
            f"FOR ROLE {OWNER_ROLE} "
            f"IN SCHEMA {schema} "
            f"REVOKE SELECT ON TABLES FROM {API_ROLE}"
        )

        _execute(f"REVOKE SELECT ON ALL TABLES IN SCHEMA {schema} FROM {API_ROLE}")

        _execute(f"REVOKE USAGE ON SCHEMA {schema} FROM {API_ROLE}")

    _execute(
        f"ALTER DEFAULT PRIVILEGES "
        f"FOR ROLE {OWNER_ROLE} "
        f"IN SCHEMA {AUDIT_SCHEMA} "
        f"REVOKE SELECT, INSERT, UPDATE "
        f"ON TABLES FROM {INGESTION_ROLE}"
    )

    _execute(
        f"ALTER DEFAULT PRIVILEGES "
        f"FOR ROLE {OWNER_ROLE} "
        f"IN SCHEMA {AUDIT_SCHEMA} "
        f"REVOKE USAGE, SELECT "
        f"ON SEQUENCES FROM {INGESTION_ROLE}"
    )

    _execute(
        f"REVOKE SELECT, INSERT, UPDATE "
        f"ON ALL TABLES IN SCHEMA {AUDIT_SCHEMA} "
        f"FROM {INGESTION_ROLE}"
    )

    _execute(
        f"REVOKE USAGE, SELECT ON ALL SEQUENCES IN SCHEMA {AUDIT_SCHEMA} FROM {INGESTION_ROLE}"
    )

    _execute(f"REVOKE USAGE ON SCHEMA {AUDIT_SCHEMA} FROM {INGESTION_ROLE}")

    for schema in reversed(INGESTION_WRITE_SCHEMAS):
        _execute(
            f"ALTER DEFAULT PRIVILEGES "
            f"FOR ROLE {OWNER_ROLE} "
            f"IN SCHEMA {schema} "
            f"REVOKE SELECT, INSERT, UPDATE, DELETE "
            f"ON TABLES FROM {INGESTION_ROLE}"
        )

        _execute(
            f"ALTER DEFAULT PRIVILEGES "
            f"FOR ROLE {OWNER_ROLE} "
            f"IN SCHEMA {schema} "
            f"REVOKE USAGE, SELECT "
            f"ON SEQUENCES FROM {INGESTION_ROLE}"
        )

        _execute(
            f"REVOKE SELECT, INSERT, UPDATE, DELETE "
            f"ON ALL TABLES IN SCHEMA {schema} "
            f"FROM {INGESTION_ROLE}"
        )

        _execute(f"REVOKE USAGE, SELECT ON ALL SEQUENCES IN SCHEMA {schema} FROM {INGESTION_ROLE}")

        _execute(f"REVOKE USAGE ON SCHEMA {schema} FROM {INGESTION_ROLE}")
