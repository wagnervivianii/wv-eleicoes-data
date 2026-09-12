# Candidate materialized read model

`analytics.candidate_2026` is the public read boundary. API/frontend readers must
never query `raw.tse_candidate`. The migration grants API SELECT explicitly and
removes inherited ingestion privileges on this object. Existing schema privileges
keep RAW/audit internal. Run migrations as `wv_eleicoes_owner`, as for the existing
privilege migrations. No elevated function or new role membership is introduced.

The allowlist contains election, constituency, office, candidacy sequence, ballot
number/name, party and candidacy status, plus numeric RAW row/run references for
lineage. It excludes CPF, voter title, email, birth date, demographics, legal/social
names, source paths and operational error/checksum metadata. Numeric lineage IDs
do not grant access to their internal source tables.

One row represents one source row, not one person. `SQ_CANDIDATO` identifies an
election candidacy and is neither a person key nor guaranteed unique in RAW.
`raw_candidate_id` is the unique refresh key; repeated source candidacies are kept.
All TSE values remain text, including identifiers with leading zeros. Exact
`#NULO`, `#NE`, `NÃO DIVULGÁVEL`, `-1`, `-3`, `-4`, blanks and whitespace remain
source markers, not real identifiers, numbers or categories. Consumers must treat
these as unavailable source values, not display them as genuine candidate facts.
No sentinel is converted to zero, inferred, trimmed or collapsed into another
sentinel. Semantic normalization belongs to topic 2. The exact year filter is
`ano_eleicao = '2026'`; malformed years are not coerced into 2026.

The selected run is the completed `success` for source `TSE`, dataset `candidatos`,
with greatest `(finished_at, id)`. Running, failed, skipped and unfinished runs are
ignored. This uses completion time, not source publication time. The current
contract scopes that dataset to 2026; adding other years requires an explicit
audit contract discriminator before reusing this selection. Only canonical CSV
rows for 2026 in that run are published. An empty latest success publishes an
empty snapshot; it never silently falls back to older data. Count consistency is
against these eligible RAW rows (audit `rows_inserted` counts the entire artifact).

## Refresh lifecycle

The migration populates the snapshot, even if empty, and creates the full unique
index required for concurrent refresh. After the RAW/success transaction commits,
the owner/orchestrator executes in a separate transaction:

```sql
REFRESH MATERIALIZED VIEW CONCURRENTLY analytics.candidate_2026;
```

This is an explicit operational step, not an ingestion-role responsibility. The
ingestion pipeline is unchanged. Refresh always resolves the latest committed
success from its statement snapshot; it does not accept arbitrary run IDs. The
orchestrator should serialize refresh requests and retry failures independently
of ingestion. Failure preserves the previous published snapshot and must not mark
a committed ingestion failed. Skips/failures need no refresh; retries are safe.
A success committed during refresh is picked up by the next refresh. Readers see
the old or new snapshot atomically, with no freshness promise until refresh
commits. There is no automatic scheduler in this foundation.

Physical row order is not a contract. For deterministic results, readers use
`ORDER BY raw_candidate_id`. Repeated refresh without source changes preserves
the same values and identifiers; no volatile timestamps are projected.

Downgrade drops only this materialized view with RESTRICT, including its index
and grants. Dependencies must be removed explicitly; RAW/audit are untouched.

PostgreSQL integration validation uses an explicitly supplied disposable database:
`pytest tests/db/test_candidate_read_model.py --analytics-test-url=<local URL>`.
It runs inside a rolled-back transaction and requires the existing migrations
through `8c31b79e5a02`, the three project roles, and no analytics view yet.
Environment activation and authoritative database checks belong to the orchestrator.
