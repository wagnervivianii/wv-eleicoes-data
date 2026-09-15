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

`CANDIDATES_2022` now requires the same exact ordered 50-column header validated by the probe. The discovery
contract remains available only for future evidence gathering; production persistence uses the frozen contract.

The candidates CLI supports both years while preserving the existing default:

```bash
python -m wv_eleicoes_data.ingestion.tse.pipeline --year 2022
python -m wv_eleicoes_data.ingestion.tse.pipeline --year 2026
```

Omitting `--year` still means 2026 so existing scheduled operations do not silently change behavior.

## Why `audit.ingestion_run.scope_key` exists

`source=TSE` plus `dataset=candidatos` is no longer enough to identify the currently applied snapshot once
multiple elections coexist. A 2022 checksum must never cause a 2026 run to skip, and vice versa.

Candidate runs therefore use:

```text
TSE / candidatos / election-year:2022
TSE / candidatos / election-year:2026
```

The migration `f8142026hi01` backfills every pre-existing `TSE/candidatos` run as `election-year:2026`, because
2026 was the only persisted candidate contract before historical ingestion was introduced. Other ingestion runs
retain the generic `global` default until their own contracts define a narrower scope.

The advisory lock and last-success checksum lookup use the same scope. This allows independent election-year
snapshots while keeping idempotency deterministic inside each year.

## Boundary of this unit

This unit makes 2022 safe to ingest into the existing multi-year RAW table and keeps person-identity
reconciliation compatible with historical rows. It intentionally does **not** yet make 2022 visible through
`analytics.candidate` / Profile 360, because the current public read model is still 2026-specific. Generalizing
that public longitudinal read model is the next functional unit.
