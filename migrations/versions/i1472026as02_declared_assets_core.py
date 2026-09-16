"""Create typed longitudinal CORE projection for TSE declared assets.

Revision ID: i1472026as02
Revises: h0362026as01
"""

from alembic import op

revision = "i1472026as02"
down_revision = "h0362026as01"
branch_labels = None
depends_on = None

CREATE_CORE = r"""
CREATE VIEW core.candidate_asset AS
WITH source_rows AS (
    SELECT
        a.id AS raw_asset_id,
        a.ingestion_run_id,
        r.source_updated_at AS source_snapshot_at,
        identifier.person_id,
        btrim(a.ano_eleicao) AS election_year_text,
        btrim(a.cd_eleicao) AS election_code,
        btrim(a.sq_candidato) AS candidacy_sequence,
        btrim(a.nr_ordem_bem_candidato) AS asset_order_text,
        btrim(a.cd_tipo_bem_candidato) AS asset_type_code_text,
        btrim(a.ds_tipo_bem_candidato) AS asset_type_name_text,
        btrim(a.ds_bem_candidato) AS asset_description_text,
        btrim(a.vr_bem_candidato) AS declared_value_text,
        btrim(a.dt_ult_atual_bem_candidato) AS asset_updated_date_text,
        btrim(a.hh_ult_atual_bem_candidato) AS asset_updated_time_text
    FROM raw.tse_candidate_asset AS a
    JOIN audit.ingestion_run AS r
      ON r.id = a.ingestion_run_id
     AND r.status = 'success'
     AND r.source = 'TSE'
     AND r.dataset = 'bens_candidatos'
     AND r.scope_key = 'election-year:' || btrim(a.ano_eleicao)
    JOIN core.person_external_identifier AS identifier
      ON identifier.source_system = 'TSE'
     AND identifier.identifier_type = 'candidacy_sequence'
     AND identifier.identifier_value = btrim(a.sq_candidato)
     AND identifier.scope_key =
         'election:' || btrim(a.ano_eleicao) || ':' || btrim(a.cd_eleicao)
    WHERE a.valid_to_run_id IS NULL
), typed AS (
    SELECT
        raw_asset_id,
        ingestion_run_id,
        source_snapshot_at,
        person_id,
        CASE
            WHEN election_year_text ~ '^[0-9]{4}$' AND election_year_text <> '0000'
            THEN election_year_text::smallint
        END AS election_year,
        election_code,
        candidacy_sequence,
        CASE
            WHEN asset_order_text ~ '^[1-9][0-9]*$'
            THEN asset_order_text::integer
        END AS asset_order,
        CASE
            WHEN asset_type_code_text IN
                 ('', '#NULO', '#NE', 'NÃO DIVULGÁVEL', '-1', '-3', '-4')
            THEN NULL
            ELSE asset_type_code_text
        END AS asset_type_code,
        CASE
            WHEN asset_type_name_text IN
                 ('', '#NULO', '#NE', 'NÃO DIVULGÁVEL', '-1', '-3', '-4')
            THEN NULL
            ELSE asset_type_name_text
        END AS asset_type_name,
        CASE
            WHEN asset_description_text IN
                 ('', '#NULO', '#NE', 'NÃO DIVULGÁVEL', '-1', '-3', '-4')
            THEN NULL
            ELSE asset_description_text
        END AS asset_description,
        CASE
            WHEN declared_value_text IN
                 ('', '#NULO', '#NE', 'NÃO DIVULGÁVEL', '-1', '-3', '-4')
            THEN NULL
            WHEN declared_value_text ~ '^[+-]?[0-9]+$'
            THEN declared_value_text::numeric
            WHEN declared_value_text ~ '^[+-]?[0-9]+,[0-9]+$'
            THEN replace(declared_value_text, ',', '.')::numeric
            WHEN declared_value_text ~ '^[+-]?[0-9]+\.[0-9]+$'
            THEN declared_value_text::numeric
            WHEN declared_value_text ~ '^[+-]?[0-9]{1,3}(\.[0-9]{3})+,[0-9]+$'
            THEN replace(replace(declared_value_text, '.', ''), ',', '.')::numeric
            WHEN declared_value_text ~ '^[+-]?[0-9]{1,3}(,[0-9]{3})+\.[0-9]+$'
            THEN replace(declared_value_text, ',', '')::numeric
        END AS declared_value,
        CASE
            WHEN declared_value_text IN
                 ('', '#NULO', '#NE', 'NÃO DIVULGÁVEL', '-1', '-3', '-4')
            THEN 'missing'
            WHEN declared_value_text ~ '^[+-]?[0-9]+$'
              OR declared_value_text ~ '^[+-]?[0-9]+,[0-9]+$'
              OR declared_value_text ~ '^[+-]?[0-9]+\.[0-9]+$'
              OR declared_value_text ~ '^[+-]?[0-9]{1,3}(\.[0-9]{3})+,[0-9]+$'
              OR declared_value_text ~ '^[+-]?[0-9]{1,3}(,[0-9]{3})+\.[0-9]+$'
            THEN 'parsed'
            ELSE 'unrecognized'
        END AS declared_value_status,
        CASE
            WHEN asset_updated_date_text ~ '^[0-9]{2}/[0-9]{2}/[0-9]{4}$'
             AND asset_updated_time_text ~ '^[0-9]{2}:[0-9]{2}:[0-9]{2}$'
            THEN (
                to_date(asset_updated_date_text, 'DD/MM/YYYY')::timestamp
                + asset_updated_time_text::time
            ) AT TIME ZONE 'America/Sao_Paulo'
        END AS asset_updated_at
    FROM source_rows
)
SELECT
    raw_asset_id,
    ingestion_run_id,
    source_snapshot_at,
    person_id,
    election_year,
    election_code,
    candidacy_sequence,
    asset_order,
    asset_type_code,
    asset_type_name,
    asset_description,
    declared_value,
    declared_value_status,
    asset_updated_at
FROM typed
"""

VALIDATE_CORE = r"""
DO $$
DECLARE
    active_source_rows bigint;
    core_rows bigint;
BEGIN
    SELECT count(*)
    INTO active_source_rows
    FROM raw.tse_candidate_asset AS a
    JOIN audit.ingestion_run AS r
      ON r.id = a.ingestion_run_id
     AND r.status = 'success'
     AND r.source = 'TSE'
     AND r.dataset = 'bens_candidatos'
     AND r.scope_key = 'election-year:' || btrim(a.ano_eleicao)
    WHERE a.valid_to_run_id IS NULL;

    SELECT count(*) INTO core_rows FROM core.candidate_asset;

    IF active_source_rows <> core_rows THEN
        RAISE EXCEPTION
            'core.candidate_asset lost rows while linking declared assets to stable people';
    END IF;

    IF EXISTS (
        SELECT 1
        FROM core.candidate_asset
        WHERE election_year IS NULL
           OR asset_order IS NULL
           OR declared_value_status = 'unrecognized'
    ) THEN
        RAISE EXCEPTION
            'core.candidate_asset contains an unsupported canonical value';
    END IF;
END;
$$
"""


def upgrade() -> None:
    op.execute(CREATE_CORE)
    op.execute(VALIDATE_CORE)
    op.execute(
        "REVOKE ALL ON core.candidate_asset "
        "FROM PUBLIC, wv_eleicoes_ingestion, wv_eleicoes_api"
    )
    op.execute("GRANT SELECT ON core.candidate_asset TO wv_eleicoes_api")


def downgrade() -> None:
    op.execute("DROP VIEW core.candidate_asset")
