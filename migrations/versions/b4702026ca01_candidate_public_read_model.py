"""Create the public-safe 2026 candidate snapshot.

Revision ID: b4702026ca01
Revises: 8c31b79e5a02

The SQL is frozen independently of the ingestion contract and ORM.
"""

from collections.abc import Sequence

from alembic import op

revision: str = "b4702026ca01"
down_revision: str | None = "8c31b79e5a02"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

CREATE_VIEW = """
CREATE MATERIALIZED VIEW analytics.candidate_2026 AS
WITH latest_success AS (
    SELECT r.id
    FROM audit.ingestion_run AS r
    WHERE r.source = 'TSE'
      AND r.dataset = 'candidatos'
      AND r.status = 'success'
      AND r.finished_at IS NOT NULL
    ORDER BY r.finished_at DESC, r.id DESC
    LIMIT 1
)
SELECT
    c.id AS raw_candidate_id,
    c.ingestion_run_id,
    c.ano_eleicao,
    c.cd_eleicao,
    c.nr_turno,
    c.sg_uf,
    c.sg_ue,
    c.nm_ue,
    c.cd_cargo,
    c.ds_cargo,
    c.sq_candidato,
    c.nr_candidato,
    c.nm_urna_candidato,
    c.nr_partido,
    c.sg_partido,
    c.nm_partido,
    c.cd_situacao_candidatura,
    c.ds_situacao_candidatura
FROM raw.tse_candidate AS c
JOIN latest_success AS r ON r.id = c.ingestion_run_id
WHERE c.source_file = 'consulta_cand_2026_BRASIL.csv'
  AND c.ano_eleicao = '2026'
WITH DATA
"""


def upgrade() -> None:
    op.execute(CREATE_VIEW)
    # A full, non-expression unique index supports CONCURRENTLY even with
    # duplicate or sentinel SQ_CANDIDATO values. No speculative query indexes.
    op.execute(
        "CREATE UNIQUE INDEX uq_candidate_2026_raw_candidate_id "
        "ON analytics.candidate_2026 (raw_candidate_id)"
    )
    op.execute("REVOKE ALL ON analytics.candidate_2026 FROM PUBLIC")
    op.execute("REVOKE ALL ON analytics.candidate_2026 FROM wv_eleicoes_ingestion")
    op.execute("REVOKE ALL ON analytics.candidate_2026 FROM wv_eleicoes_api")
    op.execute("GRANT SELECT ON analytics.candidate_2026 TO wv_eleicoes_api")


def downgrade() -> None:
    # RESTRICT (the default) fails safely if downstream objects depend on this view.
    # Its index and grants disappear with it; RAW and audit history remain intact.
    op.execute("DROP MATERIALIZED VIEW analytics.candidate_2026 RESTRICT")
