"""Publish item-level declared-assets serving relation.

Revision ID: k3692026as04
Revises: j2582026as03
"""

from alembic import op

revision = "k3692026as04"
down_revision = "j2582026as03"
branch_labels = None
depends_on = None

CREATE_ITEM = r"""
CREATE MATERIALIZED VIEW analytics.candidate_asset_item AS
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
FROM core.candidate_asset
WITH DATA
"""

INDEXES = (
    "CREATE UNIQUE INDEX uq_candidate_asset_item_raw_asset "
    "ON analytics.candidate_asset_item (raw_asset_id)",
    "CREATE INDEX ix_candidate_asset_item_declaration "
    "ON analytics.candidate_asset_item "
    "(person_id, election_year, election_code, candidacy_sequence, asset_order, raw_asset_id)",
)

VALIDATE_ITEM = r"""
DO $$
DECLARE
    core_rows bigint;
    item_rows bigint;
BEGIN
    SELECT count(*) INTO core_rows FROM core.candidate_asset;
    SELECT count(*) INTO item_rows FROM analytics.candidate_asset_item;

    IF item_rows <> core_rows THEN
        RAISE EXCEPTION 'candidate_asset_item row count mismatch against CORE';
    END IF;

    IF EXISTS (
        SELECT 1
        FROM analytics.candidate_asset_item
        GROUP BY raw_asset_id
        HAVING count(*) <> 1
    ) THEN
        RAISE EXCEPTION 'candidate_asset_item duplicated a RAW asset identity';
    END IF;

    IF EXISTS (
        SELECT 1
        FROM analytics.candidate_asset_item
        WHERE person_id IS NULL
           OR election_year IS NULL
           OR election_code IS NULL
           OR candidacy_sequence IS NULL
           OR asset_order IS NULL
    ) THEN
        RAISE EXCEPTION 'candidate_asset_item contains an incomplete serving key';
    END IF;

    IF EXISTS (
        SELECT 1
        FROM (
            SELECT
                person_id,
                election_year,
                election_code,
                candidacy_sequence,
                count(*)::integer AS asset_count,
                count(*) FILTER (WHERE declared_value < 0)::integer
                    AS negative_value_count,
                sum(declared_value) AS declared_value_signed_total
            FROM analytics.candidate_asset_item
            GROUP BY person_id, election_year, election_code, candidacy_sequence
        ) AS items
        FULL JOIN analytics.candidate_asset_summary AS summary
          ON summary.person_id = items.person_id
         AND summary.election_year = items.election_year
         AND summary.election_code = items.election_code
         AND summary.candidacy_sequence = items.candidacy_sequence
        WHERE items.person_id IS NULL
           OR summary.person_id IS NULL
           OR items.asset_count <> summary.asset_count
           OR items.negative_value_count <> summary.negative_value_count
           OR items.declared_value_signed_total
              IS DISTINCT FROM summary.declared_value_signed_total
    ) THEN
        RAISE EXCEPTION 'candidate_asset_item does not reconcile with candidate_asset_summary';
    END IF;
END;
$$
"""

RELATION = "analytics.candidate_asset_item"


def upgrade() -> None:
    op.execute(CREATE_ITEM)
    for statement in INDEXES:
        op.execute(statement)
    op.execute(VALIDATE_ITEM)
    op.execute(
        f"REVOKE ALL ON {RELATION} "
        "FROM PUBLIC, wv_eleicoes_ingestion, wv_eleicoes_api"
    )
    op.execute(f"GRANT SELECT ON {RELATION} TO wv_eleicoes_api")


def downgrade() -> None:
    op.execute("DROP MATERIALIZED VIEW analytics.candidate_asset_item")
