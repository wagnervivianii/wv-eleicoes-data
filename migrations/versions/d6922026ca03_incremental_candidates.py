"""Incremental candidate versions and current-state public projections.

Legacy hashes are bootstrapped transactionally by the first changed artifact.
"""

from alembic import op

revision = "d6922026ca03"
down_revision = "c5812026ca02"
branch_labels = None
depends_on = None

CREATE_VIEW = """
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
WHERE c.valid_to_run_id IS NULL AND c.source_file = 'consulta_cand_2026_BRASIL.csv'
  AND c.ano_eleicao = '2026'
WITH DATA
"""

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


def rebuild() -> None:
    op.execute(CREATE_VIEW)
    op.execute(
        "CREATE UNIQUE INDEX uq_candidate_2026_raw_candidate_id "
        "ON analytics.candidate_2026 (raw_candidate_id)"
    )
    op.execute(CREATE_CORE)
    op.execute(CREATE_PUBLIC)
    for statement in INDEXES:
        op.execute(statement)
    for relation in ("analytics.candidate_2026", "core.candidate", "analytics.candidate"):
        for role in ("PUBLIC", "wv_eleicoes_ingestion", "wv_eleicoes_api"):
            op.execute(f"REVOKE ALL ON {relation} FROM {role}")
        op.execute(f"GRANT SELECT ON {relation} TO wv_eleicoes_api")


def upgrade() -> None:
    op.execute(
        "ALTER TABLE raw.tse_candidate "
        "ADD COLUMN valid_from_run_id bigint REFERENCES audit.ingestion_run(id), "
        "ADD COLUMN valid_to_run_id bigint REFERENCES audit.ingestion_run(id), "
        "ADD COLUMN content_hash varchar(64)"
    )
    # Close every row first, including unsuccessful legacy rows. Rank successful
    # rows by completion order (not start/id order); retain every physical row.
    op.execute(
        "UPDATE raw.tse_candidate SET valid_from_run_id = ingestion_run_id, "
        "valid_to_run_id = ingestion_run_id"
    )
    op.execute("""
        WITH ranked AS (
            SELECT c.id, lead(c.ingestion_run_id) OVER (
                PARTITION BY c.ano_eleicao, c.cd_eleicao, c.sq_candidato
                ORDER BY r.finished_at NULLS FIRST, r.id, c.id
            ) AS next_run
            FROM raw.tse_candidate c JOIN audit.ingestion_run r ON r.id = c.ingestion_run_id
            WHERE r.status = 'success' AND r.source = 'TSE' AND r.dataset = 'candidatos'
        )
        UPDATE raw.tse_candidate c SET valid_to_run_id = ranked.next_run
        FROM ranked WHERE ranked.id = c.id
    """)
    op.execute("ALTER TABLE raw.tse_candidate ALTER COLUMN valid_from_run_id SET NOT NULL")
    op.execute("REVOKE UPDATE, DELETE ON raw.tse_candidate FROM wv_eleicoes_ingestion")
    op.execute(
        "GRANT UPDATE (valid_to_run_id, content_hash) ON raw.tse_candidate TO wv_eleicoes_ingestion"
    )
    op.execute(
        "CREATE UNIQUE INDEX uq_tse_candidate_active ON raw.tse_candidate "
        "(ano_eleicao, cd_eleicao, sq_candidato) WHERE valid_to_run_id IS NULL"
    )
    op.execute(
        "ALTER TABLE audit.ingestion_run ADD COLUMN rows_added integer, "
        "ADD COLUMN rows_removed integer, ADD COLUMN rows_unchanged integer"
    )
    op.execute("""
        CREATE TABLE audit.candidate_change (
            id bigserial PRIMARY KEY,
            run_id bigint NOT NULL REFERENCES audit.ingestion_run(id),
            change_type varchar(1) NOT NULL,
            ano_eleicao text NOT NULL, cd_eleicao text NOT NULL, sq_candidato text NOT NULL,
            old_raw_candidate_id bigint REFERENCES raw.tse_candidate(id),
            new_raw_candidate_id bigint REFERENCES raw.tse_candidate(id),
            source_snapshot_at timestamptz NOT NULL,
            detected_at timestamptz NOT NULL DEFAULT now(),
            changed_fields jsonb,
            UNIQUE (run_id, ano_eleicao, cd_eleicao, sq_candidato),
            CONSTRAINT change_shape CHECK (
                (change_type = 'A' AND old_raw_candidate_id IS NULL
                 AND new_raw_candidate_id IS NOT NULL
                 AND changed_fields IS NULL) OR
                (change_type = 'M' AND old_raw_candidate_id IS NOT NULL
                 AND new_raw_candidate_id IS NOT NULL
                 AND old_raw_candidate_id <> new_raw_candidate_id
                 AND changed_fields IS NOT NULL
                 AND CASE
                     WHEN jsonb_typeof(changed_fields) = 'array'
                     THEN jsonb_array_length(changed_fields) > 0
                     ELSE FALSE
                 END) OR
                (change_type = 'D' AND old_raw_candidate_id IS NOT NULL
                 AND new_raw_candidate_id IS NULL
                 AND changed_fields IS NULL))
        )
    """)
    op.execute("CREATE INDEX ix_audit_candidate_change_run_id ON audit.candidate_change (run_id)")
    op.execute(
        "CREATE INDEX ix_audit_candidate_change_election_run "
        "ON audit.candidate_change (ano_eleicao, run_id)"
    )
    op.execute(
        "CREATE INDEX ix_audit_candidate_change_candidacy_history "
        "ON audit.candidate_change "
        "(ano_eleicao, cd_eleicao, sq_candidato, detected_at, id)"
    )
    op.execute("REVOKE ALL ON audit.candidate_change FROM PUBLIC, wv_eleicoes_api")
    op.execute("GRANT SELECT, INSERT ON audit.candidate_change TO wv_eleicoes_ingestion")
    op.execute(
        "GRANT USAGE, SELECT ON SEQUENCE audit.candidate_change_id_seq TO wv_eleicoes_ingestion"
    )
    op.execute("DROP MATERIALIZED VIEW analytics.candidate RESTRICT")
    op.execute("DROP VIEW core.candidate RESTRICT")
    op.execute("DROP MATERIALIZED VIEW analytics.candidate_2026 RESTRICT")
    rebuild()


def downgrade() -> None:
    raise RuntimeError("Incremental history cannot safely revert to full snapshots; restore backup")
