# TSE declared assets — ANALYTICS serving contract

Unit 09 publishes serving aggregates derived from `core.candidate_asset`. The source remains
TSE candidate-declared assets; the platform describes these values as **bens declarados ao
TSE** and **valores declarados**, not as an independent measure of real wealth.

## Relations

### `analytics.candidate_asset_summary`

One row per stable person + election + candidacy. It exposes:

- item counts and typed-value counts;
- signed declared-value total;
- positive and negative declared-value subtotals;
- explicit negative-value count / flag;
- the largest declared item fields;
- latest asset update and source snapshot timestamps.

The signed total preserves the source sign. No `ABS`, zero clamp, or silent exclusion is
used. Positive and negative subtotals are exposed separately so callers can avoid hiding
source anomalies.

### `analytics.candidate_asset_type`

One row per candidacy and declared-asset type. It exposes item counts and the same signed,
positive and negative monetary decomposition. Composition percentages have intentionally
narrow semantics:

- `item_share_pct`: share of declared items in that type;
- `positive_value_share_pct`: share of positive declared value only.

There is deliberately no percentage based on a signed denominator because negative source
values can make such a percentage misleading.

### `analytics.person_asset_evolution`

This relation is deliberately **annual-person scoped**, not candidacy scoped. It contains
one row per `person_id + election_year`.

A person can have more than one TSE candidacy-scoped declared-assets snapshot in the same
year. Those snapshots can legitimately differ in the source. ANALYTICS therefore never
chooses one silently and never compares two candidacies from the same year as if they were
temporal evolution.

The relation exposes:

- `candidacy_snapshot_count`;
- `election_count`;
- `snapshot_status` (`single_snapshot` or `multiple_candidacy_snapshots`);
- election/candidacy and monetary fields only when the annual snapshot is unique;
- the corresponding previous-year fields;
- nominal and percentage change only when the required snapshots are unambiguous.

Comparison statuses are:

- `first_snapshot`: no prior year is available;
- `current_ambiguous`: the current year has multiple candidacy snapshots;
- `previous_ambiguous`: the prior year has multiple candidacy snapshots;
- `contains_negative_values`: a unique current/prior snapshot contains signed negatives;
- `zero_baseline`: the previous unique total is zero;
- `missing_value`: one of the unique totals is unavailable;
- `comparable`: the percentage calculation is semantically permitted.

`declared_value_change_pct` is populated only for `comparable`. Same-year comparisons are
structurally impossible because the window has exactly one row per person/year before
`lag()` is applied.

This keeps temporal comparison conservative: candidate-level data remain fully available
in `candidate_asset_summary`, while annual evolution refuses to invent a canonical asset
snapshot when the official source provides more than one.

## Refresh contract

The materialized views are populated by the migration and later refreshed by
`wv_eleicoes_data.analytics.assets.refresh_declared_assets()` in dependency order:

1. candidate summary;
2. type composition;
3. person annual evolution.

The helper uses a transaction advisory lock. It is owner/migration-only. The ingestion role
intentionally has no access to CORE/ANALYTICS serving relations.

## Integrity gate

Migration `j2582026as03` refuses to complete if:

- the number of summary scopes differs from distinct CORE candidacy scopes;
- summary item counts do not reconcile to CORE rows;
- type-composition item counts do not reconcile to CORE rows;
- evolution rows differ from distinct `person_id + election_year` scopes;
- any evolution row points to the same or a later previous year;
- annual snapshot status disagrees with its candidacy-snapshot count;
- a non-comparable row publishes a percentage; or
- signed totals do not equal positive + negative subtotals.

## Access

`wv_eleicoes_api` receives `SELECT` on the three ANALYTICS relations. PUBLIC and
`wv_eleicoes_ingestion` receive no privileges.
