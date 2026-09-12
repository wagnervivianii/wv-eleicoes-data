"""Read-only evidence collection for the orchestrator's database_validation step."""

from typing import Any

from sqlalchemy import Connection, text

from wv_eleicoes_data.analytics.candidates import QUERIES


def collect_candidate_evidence(connection: Connection) -> dict[str, Any]:
    """Run in a repeatable-read transaction after publication, as the local owner.

    Never returns candidate data or query parameters. Timings are informational.
    No planner settings are changed: small result sets may favor sequential scans.
    """
    counts = connection.execute(text("""
        WITH latest AS (
            SELECT id FROM audit.ingestion_run
            WHERE source = 'TSE' AND dataset = 'candidatos'
                AND status = 'success' AND finished_at IS NOT NULL
            ORDER BY finished_at DESC, id DESC LIMIT 1
        )
        SELECT
            (SELECT count(*) FROM raw.tse_candidate
             WHERE ingestion_run_id = (SELECT id FROM latest)
               AND source_file = 'consulta_cand_2026_BRASIL.csv'
               AND ano_eleicao = '2026') AS eligible_raw,
            (SELECT count(*) FROM analytics.candidate_2026) AS bootstrap,
            (SELECT count(*) FROM analytics.candidate) AS public
    """)).mappings().one()
    if len(set(counts.values())) != 1:
        raise ValueError("Candidate publication count mismatch; refresh and retry")
    sample = connection.execute(text("""
        SELECT election_year AS year, uf, office_code AS office,
               party_number AS party, ballot_number AS number, ballot_name AS name
        FROM analytics.candidate
        WHERE election_year IS NOT NULL AND uf IS NOT NULL AND office_code IS NOT NULL
          AND party_number IS NOT NULL AND ballot_number IS NOT NULL AND ballot_name IS NOT NULL
        ORDER BY raw_candidate_id LIMIT 1
    """)).mappings().first()
    if sample is None:
        raise ValueError("No complete representative candidate available for benchmark")
    parameters = dict(sample) | {"after": 0, "limit": 50}
    plans: dict[str, Any] = {}
    for name, query in QUERIES.items():
        plan = connection.scalar(text("EXPLAIN (ANALYZE, BUFFERS, FORMAT JSON) " + query),
                                 parameters)
        # Return structure/access paths and metrics only; plan expressions can
        # contain names or other source values and must not enter evidence files.
        def summarize(node: dict[str, Any]) -> dict[str, Any]:
            keys = ("Node Type", "Index Name", "Actual Rows", "Actual Loops",
                    "Actual Total Time", "Shared Hit Blocks", "Shared Read Blocks")
            return {k: node[k] for k in keys if k in node} | {
                "Plans": [summarize(child) for child in node.get("Plans", [])]
            }
        plans[name] = {
            "plan": summarize(plan[0]["Plan"]),
            "execution_ms": plan[0]["Execution Time"],
            "planning_ms": plan[0]["Planning Time"],
        }
    return {"counts": dict(counts), "queries": plans}
