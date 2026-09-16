"""Publish declared-assets serving aggregates and longitudinal evolution.

Revision ID: j2582026as03
Revises: i1472026as02
"""

from alembic import op

revision = "j2582026as03"
down_revision = "i1472026as02"
branch_labels = None
depends_on = None

CREATE_SUMMARY = r"""
CREATE MATERIALIZED VIEW analytics.candidate_asset_summary AS
WITH ranked AS (
    SELECT
        a.*,
        row_number() OVER (
            PARTITION BY
                a.person_id,
                a.election_year,
                a.election_code,
                a.candidacy_sequence
            ORDER BY a.declared_value DESC NULLS LAST, a.asset_order, a.raw_asset_id
        ) AS value_rank
    FROM core.candidate_asset AS a
), grouped AS (
    SELECT
        person_id,
        election_year,
        election_code,
        candidacy_sequence,
        count(*)::integer AS asset_count,
        count(declared_value)::integer AS declared_value_count,
        count(*) FILTER (WHERE declared_value_status = 'missing')::integer
            AS missing_value_count,
        count(*) FILTER (WHERE declared_value > 0)::integer AS positive_value_count,
        count(*) FILTER (WHERE declared_value = 0)::integer AS zero_value_count,
        count(*) FILTER (WHERE declared_value < 0)::integer AS negative_value_count,
        sum(declared_value) AS declared_value_signed_total,
        coalesce(sum(declared_value) FILTER (WHERE declared_value > 0), 0::numeric)
            AS declared_value_positive_total,
        coalesce(sum(declared_value) FILTER (WHERE declared_value < 0), 0::numeric)
            AS declared_value_negative_total,
        bool_or(declared_value < 0) AS has_negative_values,
        max(declared_value) AS largest_declared_value,
        max(asset_order) FILTER (WHERE value_rank = 1) AS largest_asset_order,
        max(asset_type_code) FILTER (WHERE value_rank = 1) AS largest_asset_type_code,
        max(asset_type_name) FILTER (WHERE value_rank = 1) AS largest_asset_type_name,
        max(asset_description) FILTER (WHERE value_rank = 1) AS largest_asset_description,
        max(asset_updated_at) AS latest_asset_updated_at,
        max(source_snapshot_at) AS source_snapshot_at
    FROM ranked
    GROUP BY person_id, election_year, election_code, candidacy_sequence
)
SELECT * FROM grouped
WITH DATA
"""

CREATE_TYPE_COMPOSITION = r"""
CREATE MATERIALIZED VIEW analytics.candidate_asset_type AS
WITH grouped AS (
    SELECT
        a.person_id,
        a.election_year,
        a.election_code,
        a.candidacy_sequence,
        coalesce(a.asset_type_code, '') AS asset_type_key,
        a.asset_type_code,
        a.asset_type_name,
        count(*)::integer AS asset_count,
        count(a.declared_value)::integer AS declared_value_count,
        count(*) FILTER (WHERE a.declared_value < 0)::integer AS negative_value_count,
        sum(a.declared_value) AS declared_value_signed_total,
        coalesce(sum(a.declared_value) FILTER (WHERE a.declared_value > 0), 0::numeric)
            AS declared_value_positive_total,
        coalesce(sum(a.declared_value) FILTER (WHERE a.declared_value < 0), 0::numeric)
            AS declared_value_negative_total,
        max(a.declared_value) AS largest_declared_value
    FROM core.candidate_asset AS a
    GROUP BY
        a.person_id,
        a.election_year,
        a.election_code,
        a.candidacy_sequence,
        coalesce(a.asset_type_code, ''),
        a.asset_type_code,
        a.asset_type_name
)
SELECT
    grouped.*,
    round(
        grouped.asset_count::numeric * 100
        / nullif(summary.asset_count, 0),
        4
    ) AS item_share_pct,
    CASE
        WHEN summary.declared_value_positive_total > 0
        THEN round(
            grouped.declared_value_positive_total * 100
            / summary.declared_value_positive_total,
            4
        )
    END AS positive_value_share_pct
FROM grouped
JOIN analytics.candidate_asset_summary AS summary
  ON summary.person_id = grouped.person_id
 AND summary.election_year = grouped.election_year
 AND summary.election_code = grouped.election_code
 AND summary.candidacy_sequence = grouped.candidacy_sequence
WITH DATA
"""

CREATE_EVOLUTION = r"""
CREATE MATERIALIZED VIEW analytics.person_asset_evolution AS
WITH annual AS (
    SELECT
        s.person_id,
        s.election_year,
        count(*)::integer AS candidacy_snapshot_count,
        count(DISTINCT s.election_code)::integer AS election_count,
        CASE
            WHEN count(*) = 1 THEN max(s.election_code)
        END AS election_code,
        CASE
            WHEN count(*) = 1 THEN max(s.candidacy_sequence)
        END AS candidacy_sequence,
        CASE
            WHEN count(*) = 1 THEN max(s.asset_count)
        END AS asset_count,
        CASE
            WHEN count(*) = 1 THEN max(s.declared_value_signed_total)
        END AS declared_value_signed_total,
        CASE
            WHEN count(*) = 1 THEN bool_or(s.has_negative_values)
        END AS has_negative_values,
        CASE
            WHEN count(*) = 1 THEN 'single_snapshot'
            ELSE 'multiple_candidacy_snapshots'
        END AS snapshot_status
    FROM analytics.candidate_asset_summary AS s
    GROUP BY s.person_id, s.election_year
), ordered AS (
    SELECT
        a.*,
        lag(a.election_year) OVER person_history AS previous_election_year,
        lag(a.candidacy_snapshot_count) OVER person_history
            AS previous_candidacy_snapshot_count,
        lag(a.election_count) OVER person_history AS previous_election_count,
        lag(a.election_code) OVER person_history AS previous_election_code,
        lag(a.candidacy_sequence) OVER person_history
            AS previous_candidacy_sequence,
        lag(a.asset_count) OVER person_history AS previous_asset_count,
        lag(a.declared_value_signed_total) OVER person_history
            AS previous_declared_value_signed_total,
        lag(a.has_negative_values) OVER person_history
            AS previous_has_negative_values,
        lag(a.snapshot_status) OVER person_history AS previous_snapshot_status
    FROM annual AS a
    WINDOW person_history AS (
        PARTITION BY a.person_id
        ORDER BY a.election_year
    )
)
SELECT
    person_id,
    election_year,
    candidacy_snapshot_count,
    election_count,
    election_code,
    candidacy_sequence,
    asset_count,
    declared_value_signed_total,
    has_negative_values,
    snapshot_status,
    previous_election_year,
    previous_candidacy_snapshot_count,
    previous_election_count,
    previous_election_code,
    previous_candidacy_sequence,
    previous_asset_count,
    previous_declared_value_signed_total,
    previous_has_negative_values,
    previous_snapshot_status,
    CASE
        WHEN previous_election_year IS NOT NULL
         AND snapshot_status = 'single_snapshot'
         AND previous_snapshot_status = 'single_snapshot'
         AND declared_value_signed_total IS NOT NULL
         AND previous_declared_value_signed_total IS NOT NULL
        THEN declared_value_signed_total - previous_declared_value_signed_total
    END AS declared_value_nominal_change,
    CASE
        WHEN previous_election_year IS NULL THEN 'first_snapshot'
        WHEN snapshot_status <> 'single_snapshot' THEN 'current_ambiguous'
        WHEN previous_snapshot_status <> 'single_snapshot' THEN 'previous_ambiguous'
        WHEN has_negative_values OR previous_has_negative_values
            THEN 'contains_negative_values'
        WHEN previous_declared_value_signed_total = 0 THEN 'zero_baseline'
        WHEN previous_declared_value_signed_total IS NULL
          OR declared_value_signed_total IS NULL THEN 'missing_value'
        ELSE 'comparable'
    END AS comparison_status,
    CASE
        WHEN previous_election_year IS NOT NULL
         AND snapshot_status = 'single_snapshot'
         AND previous_snapshot_status = 'single_snapshot'
         AND NOT has_negative_values
         AND NOT previous_has_negative_values
         AND previous_declared_value_signed_total <> 0
         AND previous_declared_value_signed_total IS NOT NULL
         AND declared_value_signed_total IS NOT NULL
        THEN round(
            (declared_value_signed_total - previous_declared_value_signed_total)
            * 100 / previous_declared_value_signed_total,
            4
        )
    END AS declared_value_change_pct
FROM ordered
WITH DATA
"""

INDEXES = (
    "CREATE UNIQUE INDEX uq_candidate_asset_summary_scope "
    "ON analytics.candidate_asset_summary "
    "(person_id, election_year, election_code, candidacy_sequence)",
    "CREATE INDEX ix_candidate_asset_summary_person_year "
    "ON analytics.candidate_asset_summary (person_id, election_year)",
    "CREATE INDEX ix_candidate_asset_summary_year "
    "ON analytics.candidate_asset_summary (election_year, person_id)",
    "CREATE UNIQUE INDEX uq_candidate_asset_type_scope "
    "ON analytics.candidate_asset_type "
    "(person_id, election_year, election_code, candidacy_sequence, "
    "asset_type_key, asset_type_name)",
    "CREATE INDEX ix_candidate_asset_type_person_year "
    "ON analytics.candidate_asset_type (person_id, election_year)",
    "CREATE INDEX ix_candidate_asset_type_year_type "
    "ON analytics.candidate_asset_type (election_year, asset_type_key, person_id)",
    "CREATE UNIQUE INDEX uq_person_asset_evolution_person_year "
    "ON analytics.person_asset_evolution (person_id, election_year)",
    "CREATE INDEX ix_person_asset_evolution_year_person "
    "ON analytics.person_asset_evolution (election_year, person_id)",
)

VALIDATE_ANALYTICS = r"""
DO $$
DECLARE
    core_rows bigint;
    summary_assets bigint;
    type_assets bigint;
    expected_summaries bigint;
    expected_evolution_rows bigint;
    summary_rows bigint;
    evolution_rows bigint;
BEGIN
    SELECT count(*) INTO core_rows FROM core.candidate_asset;

    SELECT count(*) INTO expected_summaries
    FROM (
        SELECT 1
        FROM core.candidate_asset
        GROUP BY person_id, election_year, election_code, candidacy_sequence
    ) AS scopes;

    SELECT count(*), coalesce(sum(asset_count), 0)
    INTO summary_rows, summary_assets
    FROM analytics.candidate_asset_summary;

    SELECT coalesce(sum(asset_count), 0)
    INTO type_assets
    FROM analytics.candidate_asset_type;

    SELECT count(*) INTO expected_evolution_rows
    FROM (
        SELECT 1
        FROM analytics.candidate_asset_summary
        GROUP BY person_id, election_year
    ) AS annual_scopes;

    SELECT count(*) INTO evolution_rows
    FROM analytics.person_asset_evolution;

    IF summary_rows <> expected_summaries THEN
        RAISE EXCEPTION 'candidate_asset_summary scope count mismatch';
    END IF;

    IF summary_assets <> core_rows THEN
        RAISE EXCEPTION 'candidate_asset_summary item count mismatch';
    END IF;

    IF type_assets <> core_rows THEN
        RAISE EXCEPTION 'candidate_asset_type item count mismatch';
    END IF;

    IF evolution_rows <> expected_evolution_rows THEN
        RAISE EXCEPTION 'person_asset_evolution annual scope count mismatch';
    END IF;

    IF EXISTS (
        SELECT 1
        FROM analytics.candidate_asset_summary
        WHERE coalesce(declared_value_signed_total, 0::numeric)
              <> declared_value_positive_total + declared_value_negative_total
           OR negative_value_count < 0
           OR asset_count < declared_value_count
    ) THEN
        RAISE EXCEPTION 'candidate_asset_summary monetary decomposition mismatch';
    END IF;

    IF EXISTS (
        SELECT 1
        FROM analytics.person_asset_evolution
        WHERE previous_election_year >= election_year
    ) THEN
        RAISE EXCEPTION 'person_asset_evolution contains non-forward year comparison';
    END IF;

    IF EXISTS (
        SELECT 1
        FROM analytics.person_asset_evolution
        WHERE candidacy_snapshot_count = 1
          AND snapshot_status <> 'single_snapshot'
           OR candidacy_snapshot_count > 1
          AND snapshot_status <> 'multiple_candidacy_snapshots'
    ) THEN
        RAISE EXCEPTION 'person_asset_evolution snapshot status mismatch';
    END IF;

    IF EXISTS (
        SELECT 1
        FROM analytics.person_asset_evolution
        WHERE comparison_status <> 'comparable'
          AND declared_value_change_pct IS NOT NULL
    ) THEN
        RAISE EXCEPTION 'person_asset_evolution published an unsafe percentage';
    END IF;
END;
$$
"""

RELATIONS = (
    "analytics.candidate_asset_summary",
    "analytics.candidate_asset_type",
    "analytics.person_asset_evolution",
)


def _grant_api_reads() -> None:
    for relation in RELATIONS:
        op.execute(
            f"REVOKE ALL ON {relation} "
            "FROM PUBLIC, wv_eleicoes_ingestion, wv_eleicoes_api"
        )
        op.execute(f"GRANT SELECT ON {relation} TO wv_eleicoes_api")


def upgrade() -> None:
    op.execute(CREATE_SUMMARY)
    op.execute(CREATE_TYPE_COMPOSITION)
    op.execute(CREATE_EVOLUTION)
    for statement in INDEXES:
        op.execute(statement)
    op.execute(VALIDATE_ANALYTICS)
    _grant_api_reads()


def downgrade() -> None:
    op.execute("DROP MATERIALIZED VIEW analytics.person_asset_evolution")
    op.execute("DROP MATERIALIZED VIEW analytics.candidate_asset_type")
    op.execute("DROP MATERIALIZED VIEW analytics.candidate_asset_summary")
