"""Typed longitudinal candidate contract and public query indexes.

Revision ID: c5812026ca02
Revises: b4702026ca01

Frozen SQL; the bootstrap is the adapter for the currently supported source.
"""
from collections.abc import Sequence

from alembic import op

revision: str = "c5812026ca02"
down_revision: str | None = "b4702026ca01"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

CREATE_CORE = """
CREATE VIEW core.candidate AS
WITH normalized AS (
SELECT raw_candidate_id, ingestion_run_id,
    CASE WHEN btrim(ano_eleicao) IN ('', '#NULO', '#NE', 'NÃO DIVULGÁVEL', '-1', '-3', '-4')
         THEN NULL ELSE btrim(ano_eleicao) END AS election_year,
    CASE WHEN btrim(cd_eleicao) IN ('', '#NULO', '#NE', 'NÃO DIVULGÁVEL', '-1', '-3', '-4')
         THEN NULL ELSE btrim(cd_eleicao) END AS election_code,
    CASE WHEN btrim(nr_turno) IN ('', '#NULO', '#NE', 'NÃO DIVULGÁVEL', '-1', '-3', '-4')
         THEN NULL ELSE btrim(nr_turno) END AS election_round,
    CASE WHEN btrim(sg_uf) IN ('', '#NULO', '#NE', 'NÃO DIVULGÁVEL', '-1', '-3', '-4')
         THEN NULL ELSE btrim(sg_uf) END AS uf,
    CASE WHEN btrim(sg_ue) IN ('', '#NULO', '#NE', 'NÃO DIVULGÁVEL', '-1', '-3', '-4')
         THEN NULL ELSE btrim(sg_ue) END AS electoral_unit,
    CASE WHEN btrim(nm_ue) IN ('', '#NULO', '#NE', 'NÃO DIVULGÁVEL', '-1', '-3', '-4')
         THEN NULL ELSE btrim(nm_ue) END AS electoral_unit_name,
    CASE WHEN btrim(cd_cargo) IN ('', '#NULO', '#NE', 'NÃO DIVULGÁVEL', '-1', '-3', '-4')
         THEN NULL ELSE btrim(cd_cargo) END AS office_code,
    CASE WHEN btrim(ds_cargo) IN ('', '#NULO', '#NE', 'NÃO DIVULGÁVEL', '-1', '-3', '-4')
         THEN NULL ELSE btrim(ds_cargo) END AS office_name,
    CASE WHEN btrim(sq_candidato) IN ('', '#NULO', '#NE', 'NÃO DIVULGÁVEL', '-1', '-3', '-4')
         THEN NULL ELSE btrim(sq_candidato) END AS candidacy_sequence,
    CASE WHEN btrim(nr_candidato) IN ('', '#NULO', '#NE', 'NÃO DIVULGÁVEL', '-1', '-3', '-4')
         THEN NULL ELSE btrim(nr_candidato) END AS ballot_number,
    CASE WHEN btrim(nm_urna_candidato) IN ('', '#NULO', '#NE', 'NÃO DIVULGÁVEL', '-1', '-3', '-4')
         THEN NULL ELSE btrim(nm_urna_candidato) END AS ballot_name,
    CASE WHEN btrim(nr_partido) IN ('', '#NULO', '#NE', 'NÃO DIVULGÁVEL', '-1', '-3', '-4')
         THEN NULL ELSE btrim(nr_partido) END AS party_number,
    CASE WHEN btrim(sg_partido) IN ('', '#NULO', '#NE', 'NÃO DIVULGÁVEL', '-1', '-3', '-4')
         THEN NULL ELSE btrim(sg_partido) END AS party_acronym,
    CASE WHEN btrim(nm_partido) IN ('', '#NULO', '#NE', 'NÃO DIVULGÁVEL', '-1', '-3', '-4')
         THEN NULL ELSE btrim(nm_partido) END AS party_name,
    CASE WHEN btrim(cd_situacao_candidatura) IN
         ('', '#NULO', '#NE', 'NÃO DIVULGÁVEL', '-1', '-3', '-4')
         THEN NULL ELSE btrim(cd_situacao_candidatura) END AS status_code,
    CASE WHEN btrim(ds_situacao_candidatura) IN
         ('', '#NULO', '#NE', 'NÃO DIVULGÁVEL', '-1', '-3', '-4')
         THEN NULL ELSE btrim(ds_situacao_candidatura) END AS status_name
FROM analytics.candidate_2026
)
SELECT raw_candidate_id, ingestion_run_id,
    CASE WHEN election_year ~ '^[0-9]{4}$' AND election_year <> '0000'
         THEN election_year::smallint END AS election_year,
    election_code,
    CASE WHEN election_round ~ '^[1-9][0-9]{0,1}$'
         THEN election_round::smallint END AS election_round,
    uf,
    electoral_unit,
    electoral_unit_name,
    office_code,
    office_name,
    candidacy_sequence,
    ballot_number,
    ballot_name,
    party_number,
    party_acronym,
    party_name,
    status_code,
    status_name
FROM normalized
"""

CREATE_PUBLIC = """
CREATE MATERIALIZED VIEW analytics.candidate AS
SELECT raw_candidate_id, ingestion_run_id,
    election_year, election_code, election_round, uf, electoral_unit,
    electoral_unit_name, office_code, office_name, candidacy_sequence,
    ballot_number, ballot_name, party_number, party_acronym, party_name,
    status_code, status_name
FROM core.candidate
WITH DATA
"""

INDEXES = (
    "CREATE UNIQUE INDEX uq_candidate_raw ON analytics.candidate (raw_candidate_id)",
    "CREATE INDEX ix_candidate_filter ON analytics.candidate "
    "(election_year, uf, office_code, raw_candidate_id)",
    "CREATE INDEX ix_candidate_party ON analytics.candidate "
    "(election_year, uf, office_code, party_number, raw_candidate_id)",
    "CREATE INDEX ix_candidate_number ON analytics.candidate "
    "(election_year, uf, office_code, ballot_number, raw_candidate_id)",
    "CREATE INDEX ix_candidate_name ON analytics.candidate USING gin "
    "(to_tsvector('simple'::regconfig, coalesce(ballot_name, '')))",
)


def upgrade() -> None:
    op.execute(CREATE_CORE)
    op.execute(CREATE_PUBLIC)
    for statement in INDEXES:
        op.execute(statement)
    for relation in ("core.candidate", "analytics.candidate"):
        for role in ("PUBLIC", "wv_eleicoes_ingestion", "wv_eleicoes_api"):
            op.execute(f"REVOKE ALL ON {relation} FROM {role}")
        op.execute(f"GRANT SELECT ON {relation} TO wv_eleicoes_api")


def downgrade() -> None:
    op.execute("DROP MATERIALIZED VIEW analytics.candidate RESTRICT")
    op.execute("DROP VIEW core.candidate RESTRICT")
