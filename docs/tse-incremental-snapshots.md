# TSE 2026 incremental snapshots

The candidacy key is the exact decoded tuple `(ANO_ELEICAO, CD_ELEICAO,
SQ_CANDIDATO)`, not a permanent person identifier. Incoming keys must be unique;
blank/whitespace-only and sentinel components fail the entire load. The election
year must be exactly `2026`. Trimming is used only to detect invalid components;
source values and stored keys are never normalized.

Candidate `content_hash` is SHA-256 of the UTF-8 encoding of a compact JSON array
(`ensure_ascii=False`, separators `,` and `:`) containing the exact decoded source
strings in official column order, excluding only DT_GERACAO and HH_GERACAO.
JSON framing preserves field boundaries, whitespace, embedded newlines and sentinels.
The ZIP SHA-256 remains the snapshot fingerprint. Every scheduled run downloads
and validates the full archive before comparing with the latest successfully applied
snapshot for the source/dataset, ordered by completion time and run ID. Only that
checksum is skipped; A -> B -> A reconciles back to A. Failed and skipped runs do
not move the applied snapshot pointer.

Active comparison and legacy hash bootstrap are scoped to the exact contract
election year. Source filenames are not an additional filter, preserving existing
history under the election/candidacy key even if a filename changes.

A dataset-wide transaction advisory lock serializes all checksums. Under READ
COMMITTED, the state lookup after acquiring the lock observes the preceding commit.
RAW closures, version inserts, A/M/D audit entries and successful run counters
commit together. Failure rolls all of these back; a separate transaction records
the failed run without source data or exception parameters.

`valid_from_run_id` identifies the insertion run; `valid_to_run_id` is exclusive
and NULL means active. Unchanged versions retain their original publication fields
and provenance. Removed candidates have only a closure and a D audit entry.
`rows_inserted = rows_added + rows_updated`; rows_updated counts logical M changes.
Skipped runs have zero delta counters. A changed ZIP containing only publication
metadata changes succeeds with all incoming rows counted as unchanged.

Migration d6922026ca03 preserves every legacy row. Successful rows are ordered by
finished_at, run id and raw id within each natural key. The last is active; previous
versions close at the next successful version's run. Unsuccessful legacy rows are
closed at their own run. Thus backfill follows latest-successful-row-per-key
semantics, including keys absent from the last legacy full snapshot; the next
changed snapshot reconciles removals. Legacy content hashes remain NULL until the
first changed-artifact transaction bootstraps active hashes. New versions always
receive a hash. No historical A/M/D events are invented.

The migration rebuilds the materialized projections and dependent core view in one
transaction, retaining explicit public allowlists, grants and all query/unique
indexes. Schedule this owner migration with allowance for relation locks and full
materialization. Continue refreshing candidate_2026 before candidate, using the
existing concurrent refresh procedure. The ingestion role can update only
valid_to_run_id/content_hash and cannot delete RAW rows. Hashes and audit changes
remain internal. Automatic downgrade is refused because delta history cannot be
represented safely by the earlier full-snapshot reader; recovery requires a backup
or a separately reviewed forward migration.

Comparison memory is proportional to active key/hash pairs plus incoming keys;
source payload and change INSERT batches are bounded to at most 1000 rows.
