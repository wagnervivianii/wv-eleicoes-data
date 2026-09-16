"""Create temporal RAW storage and audit deltas for TSE declared assets.

Revision ID: h0362026as01
Revises: g9252026hi02
"""

from alembic import op

revision = "h0362026as01"
down_revision = "g9252026hi02"
branch_labels = None
depends_on = None

CREATE_RAW = """
CREATE TABLE raw.tse_candidate_asset (
    id bigserial PRIMARY KEY,
    ingestion_run_id bigint NOT NULL REFERENCES audit.ingestion_run(id),
    valid_from_run_id bigint NOT NULL REFERENCES audit.ingestion_run(id),
    valid_to_run_id bigint REFERENCES audit.ingestion_run(id),
    content_hash varchar(64) NOT NULL,
    source_file text NOT NULL,
    source_row_number bigint NOT NULL,
    ingested_at timestamptz NOT NULL DEFAULT now(),
    dt_geracao text NOT NULL,
    hh_geracao text NOT NULL,
    ano_eleicao text NOT NULL,
    cd_tipo_eleicao text NOT NULL,
    nm_tipo_eleicao text NOT NULL,
    cd_eleicao text NOT NULL,
    ds_eleicao text NOT NULL,
    dt_eleicao text NOT NULL,
    sg_uf text NOT NULL,
    sg_ue text NOT NULL,
    nm_ue text NOT NULL,
    sq_candidato text NOT NULL,
    nr_ordem_bem_candidato text NOT NULL,
    cd_tipo_bem_candidato text NOT NULL,
    ds_tipo_bem_candidato text NOT NULL,
    ds_bem_candidato text NOT NULL,
    vr_bem_candidato text NOT NULL,
    dt_ult_atual_bem_candidato text NOT NULL,
    hh_ult_atual_bem_candidato text NOT NULL,
    CONSTRAINT uq_tse_candidate_asset_source_row
        UNIQUE (ingestion_run_id, source_file, source_row_number)
)
"""

CREATE_CHANGE = """
CREATE TABLE audit.asset_change (
    id bigserial PRIMARY KEY,
    run_id bigint NOT NULL REFERENCES audit.ingestion_run(id),
    change_type varchar(1) NOT NULL,
    ano_eleicao text NOT NULL,
    cd_eleicao text NOT NULL,
    sq_candidato text NOT NULL,
    nr_ordem_bem_candidato text NOT NULL,
    old_raw_asset_id bigint REFERENCES raw.tse_candidate_asset(id),
    new_raw_asset_id bigint REFERENCES raw.tse_candidate_asset(id),
    source_snapshot_at timestamptz NOT NULL,
    detected_at timestamptz NOT NULL DEFAULT now(),
    changed_fields jsonb,
    UNIQUE (
        run_id,
        ano_eleicao,
        cd_eleicao,
        sq_candidato,
        nr_ordem_bem_candidato
    ),
    CONSTRAINT asset_change_shape CHECK (
        (change_type = 'A' AND old_raw_asset_id IS NULL
         AND new_raw_asset_id IS NOT NULL
         AND changed_fields IS NULL) OR
        (change_type = 'M' AND old_raw_asset_id IS NOT NULL
         AND new_raw_asset_id IS NOT NULL
         AND old_raw_asset_id <> new_raw_asset_id
         AND changed_fields IS NOT NULL
         AND CASE
             WHEN jsonb_typeof(changed_fields) = 'array'
             THEN jsonb_array_length(changed_fields) > 0
             ELSE FALSE
         END) OR
        (change_type = 'D' AND old_raw_asset_id IS NOT NULL
         AND new_raw_asset_id IS NULL
         AND changed_fields IS NULL)
    )
)
"""


def upgrade() -> None:
    op.execute(CREATE_RAW)
    op.execute(
        "CREATE UNIQUE INDEX uq_tse_candidate_asset_active "
        "ON raw.tse_candidate_asset "
        "(ano_eleicao, cd_eleicao, sq_candidato, nr_ordem_bem_candidato) "
        "WHERE valid_to_run_id IS NULL"
    )
    op.execute(
        "CREATE INDEX ix_tse_candidate_asset_active_candidacy "
        "ON raw.tse_candidate_asset (ano_eleicao, cd_eleicao, sq_candidato) "
        "WHERE valid_to_run_id IS NULL"
    )
    op.execute(
        "CREATE INDEX ix_tse_candidate_asset_history "
        "ON raw.tse_candidate_asset "
        "(ano_eleicao, cd_eleicao, sq_candidato, nr_ordem_bem_candidato, valid_from_run_id)"
    )

    op.execute(CREATE_CHANGE)
    op.execute("CREATE INDEX ix_audit_asset_change_run_id ON audit.asset_change (run_id)")
    op.execute(
        "CREATE INDEX ix_audit_asset_change_election_run "
        "ON audit.asset_change (ano_eleicao, run_id)"
    )
    op.execute(
        "CREATE INDEX ix_audit_asset_change_candidacy_history "
        "ON audit.asset_change "
        "(ano_eleicao, cd_eleicao, sq_candidato, nr_ordem_bem_candidato, detected_at, id)"
    )

    op.execute(
        "REVOKE ALL ON raw.tse_candidate_asset "
        "FROM PUBLIC, wv_eleicoes_api, wv_eleicoes_ingestion"
    )
    op.execute(
        "GRANT SELECT, INSERT ON raw.tse_candidate_asset TO wv_eleicoes_ingestion"
    )
    op.execute(
        "GRANT UPDATE (valid_to_run_id, content_hash) "
        "ON raw.tse_candidate_asset TO wv_eleicoes_ingestion"
    )
    op.execute(
        "GRANT USAGE, SELECT ON SEQUENCE raw.tse_candidate_asset_id_seq "
        "TO wv_eleicoes_ingestion"
    )

    op.execute(
        "REVOKE ALL ON audit.asset_change "
        "FROM PUBLIC, wv_eleicoes_api, wv_eleicoes_ingestion"
    )
    op.execute("GRANT SELECT, INSERT ON audit.asset_change TO wv_eleicoes_ingestion")
    op.execute(
        "GRANT USAGE, SELECT ON SEQUENCE audit.asset_change_id_seq "
        "TO wv_eleicoes_ingestion"
    )


def downgrade() -> None:
    raise RuntimeError(
        "Declared-asset temporal history cannot be safely removed; restore backup instead"
    )
