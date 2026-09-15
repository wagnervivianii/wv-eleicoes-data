# TSE historical candidates contract discovery

This unit starts the longitudinal electoral-history module without guessing historical CSV layouts.
It does **not** write to PostgreSQL and does **not** create migrations.

## First official target: Candidates 2022

Official TSE CKAN metadata frozen for discovery:

- dataset: `candidatos`
- election year: `2022`
- package id: `8747bd50-e1f7-407a-8e24-2707126ccde6`
- resource id: `435145fd-bc9d-446a-ac9d-273f585a0bb9`
- MIME: `application/zip`
- artifact: `consulta_cand_2022.zip`
- canonical national CSV: `consulta_cand_2022_BRASIL.csv`
- pinned official CDN fallback: `https://cdn.tse.jus.br/estatistica/sead/odsele/consulta_cand/consulta_cand_2022.zip`

The header is intentionally **not** frozen yet. The official artifact is probed first because historical TSE
layouts must not be assumed to match the 2026 50-column contract.

## Run the probe

From `wv-eleicoes-data`, with its existing virtual environment active:

```bash
python -m wv_eleicoes_data.ingestion.tse.probe \
  --year 2022 \
  --output /tmp/wv-eleicoes-tse-candidates-2022.json
```

The report contains only resource/artifact metadata, checksum, counts, source timestamp and column names.
It does not emit candidate row values and does not connect to the database.

The next implementation unit should use this evidence to freeze the exact 2022 schema and define the
historical normalization needed before any 2022 row is persisted.
