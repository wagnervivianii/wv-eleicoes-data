"""Owner-only publication helpers for declared-assets analytics."""

from sqlalchemy import Engine, text

SUMMARY_RELATION = "analytics.candidate_asset_summary"
TYPE_RELATION = "analytics.candidate_asset_type"
EVOLUTION_RELATION = "analytics.person_asset_evolution"


def refresh_declared_assets(engine: Engine) -> None:
    """Refresh all declared-assets serving relations in dependency order.

    The transaction-scoped advisory lock serializes publishers. This helper must run
    with the migration/owner credential: the ingestion role intentionally has no
    privilege on CORE or ANALYTICS serving relations.
    """

    with engine.begin() as connection:
        connection.execute(text("SELECT pg_advisory_xact_lock(58102, 4)"))
        connection.execute(text(
            "REFRESH MATERIALIZED VIEW analytics.candidate_asset_summary"
        ))
        connection.execute(text(
            "REFRESH MATERIALIZED VIEW analytics.candidate_asset_type"
        ))
        connection.execute(text(
            "REFRESH MATERIALIZED VIEW analytics.person_asset_evolution"
        ))
