# TSE historical candidates

This module builds electoral history from official TSE candidate snapshots without assuming that historical
layouts match the current election.

## Candidates 2022: observed contract evidence

The non-mutating probe executed against the official resource on 2026-09-15 returned:

- dataset: `candidatos`
- election year: `2022`
- package id: `8747bd50-e1f7-407a-8e24-2707126ccde6`
- resource id: `435145fd-bc9d-446a-ac9d-273f585a0bb9`
- artifact: `consulta_cand_2022.zip`
- canonical CSV: `consulta_cand_2022_BRASIL.csv`
- row count observed: `29322`
- column count: `50`
- same ordered layout as 2026: `true`
- missing columns versus 2026: none
- artifact SHA-256 observed: `787c59266f13d8b7d022210513aa22543fcce69b09922c1ffa578b8f8e05931a`
- source snapshot timestamp observed: `2026-09-15T03:16:24-03:00`

The checksum and source timestamp are observations of that publication, not permanent constants. The header
contract is what is frozen for ingestion.

Identity-relevant fields were present in the official 2022 header: `SQ_CANDIDATO`, `NR_CPF_CANDIDATO`,
`NR_TITULO_ELEITORAL_CANDIDATO`, `NM_CANDIDATO` and `DT_NASCIMENTO`.

## Frozen 2022 ingestion contract

`CANDIDATES_2022` requires the same exact ordered 50-column header validated by the probe. The discovery
contract remains available only for future evidence gathering; production persistence uses the frozen contract.

The candidates CLI supports both years while preserving the existing default:

```bash
python -m wv_eleicoes_data.ingestion.tse.pipeline --year 2022
python -m wv_eleicoes_data.ingestion.tse.pipeline --year 2026
```

Omitting `--year` still means 2026 so existing scheduled operations do not silently change behavior.

## Election-scoped ingestion audit

Candidate runs use an election-year scope so one election can never affect another election's checksum or lock:

```text
TSE / candidatos / election-year:2022
TSE / candidatos / election-year:2026
```

Migration `f8142026hi01` introduced `audit.ingestion_run.scope_key`, backfilled the pre-existing candidate runs
as 2026, and aligned advisory locking plus last-success idempotency with that same scope.

The first real 2022 load on 2026-09-15 persisted 29,322 active candidacies, created 29,322 scoped public
candidacy identifiers, and proved 6,382 stable `core.person` identities with candidacies in both 2022 and 2026.
Those counts are checkpoint observations rather than permanent source constants.

## Longitudinal public candidate read model

Migration `g9252026hi02` removes the 2026-only publication bootstrap. `core.candidate` now projects every active,
successful, election-scoped TSE candidacy directly from `raw.tse_candidate`, while preserving the same public-safe
typed columns. Sensitive source fields such as CPF, email and voter-registration number never enter the public
projection.

The publication path is now:

```text
raw.tse_candidate (active versions, multiple years)
        -> core.candidate (typed longitudinal view)
        -> analytics.candidate (materialized public query model)
        -> FastAPI Profile 360
```

`analytics.candidate_2026` is retired. The existing API already joins `core.person_external_identifier` to
`analytics.candidate` through `election_year + election_code + candidacy_sequence`, so it does not require a
separate API code change to begin returning both 2022 and 2026 candidacies for the same person after this data
migration is deployed.

A dedicated index on `(election_year, election_code, candidacy_sequence, raw_candidate_id)` supports that
Profile 360 identity join. Candidate-list filters and full-text name lookup retain their existing indexes.

`refresh_candidates()` now refreshes only `analytics.candidate`: the underlying `core.candidate` is a normal view
over the active RAW state, so the obsolete 2026 materialized adapter no longer needs a first refresh.
