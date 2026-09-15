"""Publish active TSE candidacies as a longitudinal read model.

Revision ID: g9252026hi02
Revises: f8142026hi01
"""

from alembic import op

revision = "g9252026hi02"
down_revision = "f8142026hi01"
branch_labels = None
depends_on = None

CREATE_CORE_LONGITUDINAL = """
CREATE VIEW core.candidate AS
WITH normalized AS (
SELECT
    c.id AS raw_candidate_id,
    c.ingestion_run_id,
    CASE WHEN btrim(c.ano_eleicao) IN ('', '#NULO', '#NE', 'NÃO DIVULGÁVEL', '-1', '-3', '-4')
         THEN NULL ELSE btrim(c.ano_eleicao) END AS election_year,
    CASE WHEN btrim(c.cd_eleicao) IN ('', '#NULO', '#NE', 'NÃO DIVULGÁVEL', '-1', '-3', '-4')
         THEN NULL ELSE btrim(c.cd_eleicao) END AS election_code,
    CASE WHEN btrim(c.nr_turno) IN ('', '#NULO', '#NE', 'NÃO DIVULGÁVEL', '-1', '-3', '-4')
         THEN NULL ELSE btrim(c.nr_turno) END AS election_round,
    CASE WHEN btrim(c.sg_uf) IN ('', '#NULO', '#NE', 'NÃO DIVULGÁVEL', '-1', '-3', '-4')
         THEN NULL ELSE btrim(c.sg_uf) END AS uf,
    CASE WHEN btrim(c.sg_ue) IN ('', '#NULO', '#NE', 'NÃO DIVULGÁVEL', '-1', '-3', '-4')
         THEN NULL ELSE btrim(c.sg_ue) END AS electoral_unit,
    CASE WHEN btrim(c.nm_ue) IN ('', '#NULO', '#NE', 'NÃO DIVULGÁVEL', '-1', '-3', '-4')
         THEN NULL ELSE btrim(c.nm_ue) END AS electoral_unit_name,
    CASE WHEN btrim(c.cd_cargo) IN ('', '#NULO', '#NE', 'NÃO DIVULGÁVEL', '-1', '-3', '-4')
         THEN NULL ELSE btrim(c.cd_cargo) END AS office_code,
    CASE WHEN btrim(c.ds_cargo) IN ('', '#NULO', '#NE', 'NÃO DIVULGÁVEL', '-1', '-3', '-4')
         THEN NULL ELSE btrim(c.ds_cargo) END AS office_name,
    CASE WHEN btrim(c.sq_candidato) IN ('', '#NULO', '#NE', 'NÃO DIVULGÁVEL', '-1', '-3', '-4')
         THEN NULL ELSE btrim(c.sq_candidato) END AS candidacy_sequence,
    CASE WHEN btrim(c.nr_candidato) IN ('', '#NULO', '#NE', 'NÃO DIVULGÁVEL', '-1', '-3', '-4')
         THEN NULL ELSE btrim(c.nr_candidato) END AS ballot_number,
    CASE WHEN btrim(c.nm_urna_candidato) IN ('', '#NULO', '#NE', 'NÃO DIVULGÁVEL', '-1', '-3', '-4')
         THEN NULL ELSE btrim(c.nm_urna_candidato) END AS ballot_name,
    CASE WHEN btrim(c.nr_partido) IN ('', '#NULO', '#NE', 'NÃO DIVULGÁVEL', '-1', '-3', '-4')
         THEN NULL ELSE btrim(c.nr_partido) END AS party_number,
    CASE WHEN btrim(c.sg_partido) IN ('', '#NULO', '#NE', 'NÃO DIVULGÁVEL', '-1', '-3', '-4')
         THEN NULL ELSE btrim(c.sg_partido) END AS party_acronym,
    CASE WHEN btrim(c.nm_partido) IN ('', '#NULO', '#NE', 'NÃO DIVULGÁVEL', '-1', '-3', '-4')
         THEN NULL ELSE btrim(c.nm_partido) END AS party_name,
    CASE WHEN btrim(c.cd_situacao_candidatura) IN
         ('', '#NULO', '#NE', 'NÃO DIVULGÁVEL', '-1', '-3', '-4')
         THEN NULL ELSE btrim(c.cd_situacao_candidatura) END AS status_code,
    CASE WHEN btrim(c.ds_situacao_candidatura) IN
         ('', '#NULO', '#NE', 'NÃO DIVULGÁVEL', '-1', '-3', '-4')
         THEN NULL ELSE btrim(c.ds_situacao_candidatura) END AS status_name
FROM raw.tse_candidate AS c
JOIN audit.ingestion_run AS r ON r.id = c.ingestion_run_id
WHERE c.valid_to_run_id IS NULL
  AND r.status = 'success'
  AND r.source = 'TSE'
  AND r.dataset = 'candidatos'
  AND r.scope_key = 'election-year:' || btrim(c.ano_eleicao)
)
SELECT
    raw_candidate_id,
    ingestion_run_id,
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
SELECT
    raw_candidate_id,
    ingestion_run_id,
    election_year,
    election_code,
    election_round,
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
    "CREATE INDEX ix_candidate_identity_scope ON analytics.candidate "
    "(election_year, election_code, candidacy_sequence, raw_candidate_id)",
    "CREATE INDEX ix_candidate_name ON analytics.candidate USING gin "
    "(to_tsvector('simple'::regconfig, coalesce(ballot_name, '')))",
)

LEGACY_CREATE_2026 = """
CREATE MATERIALIZED VIEW analytics.candidate_2026 AS
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
WHERE c.valid_to_run_id IS NULL
  AND c.source_file = 'consulta_cand_2026_BRASIL.csv'
  AND c.ano_eleicao = '2026'
WITH DATA
"""

LEGACY_CREATE_CORE = """
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


def _grant_public_reads(relations: tuple[str, ...]) -> None:
    for relation in relations:
        for role in ("PUBLIC", "wv_eleicoes_ingestion", "wv_eleicoes_api"):
            op.execute(f"REVOKE ALL ON {relation} FROM {role}")
        op.execute(f"GRANT SELECT ON {relation} TO wv_eleicoes_api")


def _create_public_indexes(include_identity_scope: bool) -> None:
    statements = INDEXES if include_identity_scope else tuple(
        statement for statement in INDEXES if "ix_candidate_identity_scope" not in statement
    )
    for statement in statements:
        op.execute(statement)


def upgrade() -> None:
    op.execute("DROP MATERIALIZED VIEW analytics.candidate RESTRICT")
    op.execute("DROP VIEW core.candidate RESTRICT")
    op.execute("DROP MATERIALIZED VIEW analytics.candidate_2026 RESTRICT")

    op.execute(CREATE_CORE_LONGITUDINAL)
    op.execute(CREATE_PUBLIC)
    _create_public_indexes(include_identity_scope=True)
    _grant_public_reads(("core.candidate", "analytics.candidate"))


def downgrade() -> None:
    op.execute("DROP MATERIALIZED VIEW analytics.candidate RESTRICT")
    op.execute("DROP VIEW core.candidate RESTRICT")

    op.execute(LEGACY_CREATE_2026)
    op.execute(
        "CREATE UNIQUE INDEX uq_candidate_2026_raw_candidate_id "
        "ON analytics.candidate_2026 (raw_candidate_id)"
    )
    op.execute(LEGACY_CREATE_CORE)
    op.execute(CREATE_PUBLIC)
    _create_public_indexes(include_identity_scope=False)
    _grant_public_reads(("analytics.candidate_2026", "core.candidate", "analytics.candidate"))
