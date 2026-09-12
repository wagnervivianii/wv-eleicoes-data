# Typed candidate serving contract

Migration `c5812026ca02` follows the unchanged `b4702026ca01` foundation.
`core.candidate` is the durable typed view contract; `analytics.candidate` is its
materialized public serving snapshot. The current source adapter is the existing
`analytics.candidate_2026`. RAW receives no indexes or changes.

This intentionally does not infer historical run partitions from RAW rows: the
current audit dataset only describes the 2026 artifact and cannot distinguish an
empty successful snapshot for another election. Before enabling another source,
introduce an explicit audit resource/year discriminator, then extend the adapter
behind the same generic columns. Public queries and keys have no fixed year.
This change prepares a generic contract, not multi-year ingestion support.

Year and round are SMALLINT: year accepts four ASCII digits except 0000; round
accepts 1–99 without leading zeros. Malformed or oversized values become NULL
without risky casts. Identifiers (election, office, party, candidacy sequence,
ballot number and electoral unit) remain TEXT. No date or boolean is needed.
Every semantic text column trims outer spaces and maps empty, #NULO, #NE,
NÃO DIVULGÁVEL, -1, -3 and -4 to NULL. RAW and bootstrap retain exact source text
for audit through the BIGINT raw_candidate_id and ingestion_run_id references.
No sensitive field is projected into either new object.

One row remains one source candidacy observation. The unique publication key is
raw_candidate_id, globally assigned by RAW, including across runs and elections.
The semantic candidacy context is (election_year, election_code, election_round,
UF, electoral_unit, candidacy_sequence). It is not a person key. No uniqueness
constraint is invented for duplicate source sequences or unavailable context.
Counts count observations, including source duplicates. Number lookup may return
multiple rows across electoral units, elections or rounds; consumers may add those
context filters for narrower lookup. Never treat ballot number as a unique ID.

## Query contracts and indexes

Executable bound-parameter SQL lives in `analytics/candidates.py`.

| Query | Predicates / order | Access path |
| --- | --- | --- |
| List | year + UF + office; raw ID cursor/order | composite BTREE filter |
| Party list | above + party number | composite BTREE party |
| Exact ballot number | above + textual ballot number | composite BTREE number |
| Ballot name | above + all supplied name tokens | GIN simple tsvector |
| Party chart | year + UF + office, group by party | party BTREE or sequential aggregate |
| Pagination | raw ID > cursor, ascending, bounded limit | respective BTREE |

Name search is case-insensitive whole-token matching using PostgreSQL's built-in
`simple` configuration, accent-sensitive, with AND semantics. It is not substring,
fuzzy or accent-folded search. Empty/punctuation-only queries match no rows.
No extension or elevated extension installation is needed. The GIN expression
matches the query expression exactly; PostgreSQL may combine it with a BTREE.
The API must bind all values, cap limit (suggested 100), require positive year and
nonnegative cursor, and reject empty searches. Chart NULL party groups represent
unavailable data, never party zero. Ordering uses raw IDs, not locale-dependent
names. Cursors are stable within a published snapshot; start over after refresh
when traversing a complete dataset because RAW IDs can change between ingestions.

The five indexes include the mandatory full unique refresh index. The filter,
party and number indexes each serve a distinct ordered query: party/number keys
cannot satisfy the unfiltered raw ID order. GIN adds token search storage and
refresh work. No independent indexes on year, UF or office are added. Measure
index size and refresh duration as traffic/data grows before adding covering
columns or preaggregated chart objects. NULL-heavy/common-name queries can
legitimately use sequential scans; do not force indexes in production.

## Publication

The owner invokes `refresh_candidates(engine)` with its own engine after the
successful ingestion transaction has committed. It opens a separate transaction,
takes a transaction advisory lock, refreshes the bootstrap concurrently, then the
generic snapshot concurrently, and commits both atomically. All callers must use
this helper/lock; direct refresh can bypass serialization. A failure rolls back
both refreshes, propagates to the owner for retry, and leaves committed ingestion
untouched. No helper is called inside the ingestion pipeline. API receives SELECT
only; ingestion receives no rights on the new views. No SECURITY DEFINER function,
DDL grants, scheduler or role memberships are introduced. Both materialized views
have full unique indexes and are populated at migration time.

## Validation evidence and outstanding gate

Available local checks: pytest, Ruff and mypy. PostgreSQL integration tests accept
the existing explicit disposable `--analytics-test-url` option and rollback their
fixtures. The new test includes future-year observations, duplicate candidacy
sequences, leading-zero identifiers, all sentinels and malformed years.

For authoritative real-data validation the orchestrator must run its
`database_validation` workflow including Alembic upgrade/current/heads/check,
refresh as owner, ANALYZE on both materialized views, and
`collect_candidate_evidence(connection)` in a repeatable-read transaction. The
collector checks eligible latest-success RAW / bootstrap / public row counts and
runs EXPLAIN (ANALYZE, BUFFERS) for all five query families (four paginated).
It emits only plan node types, index names, rows, buffers and informational times;
source values and plan expressions are excluded. Capture normal planner choices
and confirm selective predicates use the intended indexes where cost-effective.
Compare pre/post index plans in the same disposable local data clone when feasible;
never drop indexes on the operational database for measurement.

No authoritative database_validation tool, explicit local database URL, or loaded
~20k-row dataset was supplied to this session. No database credentials or .env
were inspected. No real-data timings, access-path confirmation, migration success
or row-count evidence is claimed. This is a blocking review gate: NOT REVIEW_READY
until the orchestrator executes the database checks and records their results.
