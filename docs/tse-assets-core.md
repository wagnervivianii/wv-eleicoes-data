# TSE declared assets — longitudinal CORE contract

Unit 08 adds the canonical, typed projection for active TSE candidate-declared assets.
It does not modify or rewrite the source-faithful RAW history created in Unit 07.

## Relation

`core.candidate_asset` is a PostgreSQL view over active successful rows from
`raw.tse_candidate_asset`.

Each row is linked to the stable political person through the already-established
public TSE candidacy identifier:

- source system: `TSE`
- identifier type: `candidacy_sequence`
- identifier value: `SQ_CANDIDATO`
- scope: `election:<year>:<election_code>`

The CORE row therefore carries both the scoped candidacy identity and `person_id`,
without persisting or exposing CPF, voter registration or email.

## Canonical fields

The view publishes:

- RAW/audit lineage: `raw_asset_id`, `ingestion_run_id`, `source_snapshot_at`
- stable identity: `person_id`
- election/candidacy scope: `election_year`, `election_code`, `candidacy_sequence`
- asset item: `asset_order`, `asset_type_code`, `asset_type_name`, `asset_description`
- typed amount: `declared_value`, `declared_value_status`
- source update time: `asset_updated_at`

`asset_description` converts blank/TSE sentinel values to SQL `NULL` in CORE. The exact
source text remains unchanged in RAW.

## Monetary semantics

`declared_value` is PostgreSQL `numeric` and remains signed. Negative source values are
preserved; the CORE contract never applies `ABS`, clamps to zero or silently drops them.

Recognized textual shapes include integer, decimal comma, decimal point, Brazilian
thousands grouping and US thousands grouping. Known TSE missing-value sentinels become
`NULL` with `declared_value_status = 'missing'`. Unexpected formats are marked
`unrecognized`, and the migration data gate refuses the current dataset if one is
present.

These values are **bens declarados ao TSE**. They are declarations from the electoral
source, not an independent audit of a person's real wealth.

## Time semantics

`DT_ULT_ATUAL_BEM_CANDIDATO` + `HH_ULT_ATUAL_BEM_CANDIDATO` are combined into
`asset_updated_at` using `America/Sao_Paulo`, while the original date/time strings remain
available in RAW.

## Integrity gate

Migration `i1472026as02` refuses to complete when:

1. the count of eligible active RAW rows differs from `core.candidate_asset`, indicating
   a failed stable-person link; or
2. a current row cannot produce a canonical election year / asset order / recognized
   monetary shape.

The view is derived and can be dropped safely on downgrade; RAW temporal history is not
deleted.

## Access

`wv_eleicoes_api` receives `SELECT` on `core.candidate_asset` only. PUBLIC and the
operational ingestion role receive no privileges on the CORE view. RAW and AUDIT remain
outside the API contract.
