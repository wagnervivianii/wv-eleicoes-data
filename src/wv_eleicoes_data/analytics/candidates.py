"""Parameterized public queries; identifiers remain text, including leading zeros."""

from sqlalchemy import Engine, text

BASE = """
SELECT * FROM analytics.candidate
WHERE election_year = :year AND uf = :uf AND office_code = :office
"""
PAGE = " AND raw_candidate_id > :after ORDER BY raw_candidate_id LIMIT :limit"
QUERIES = {
    "list": BASE + PAGE,
    "party": BASE + " AND party_number = :party" + PAGE,
    "number": BASE + " AND ballot_number = :number" + PAGE,
    "name": BASE + """ AND to_tsvector('simple'::regconfig, coalesce(ballot_name, ''))
        @@ plainto_tsquery('simple'::regconfig, :name)""" + PAGE,
    "counts": """
        SELECT party_number, count(*) AS candidate_count FROM analytics.candidate
        WHERE election_year = :year AND uf = :uf AND office_code = :office
        GROUP BY party_number ORDER BY party_number NULLS LAST
    """,
}


def refresh_candidates(engine: Engine) -> None:
    """Owner only, after ingestion commits. Errors propagate for independent retry.

    A separate transaction atomically publishes both snapshots. The transaction
    advisory lock serializes callers of this helper, including empty snapshots.
    """
    with engine.begin() as connection:
        connection.execute(text("SELECT pg_advisory_xact_lock(2026, 58102)"))
        connection.execute(text(
            "REFRESH MATERIALIZED VIEW CONCURRENTLY analytics.candidate_2026"
        ))
        connection.execute(text(
            "REFRESH MATERIALIZED VIEW CONCURRENTLY analytics.candidate"
        ))
