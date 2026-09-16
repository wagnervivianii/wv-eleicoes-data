# TSE declared-assets contract probe

## Purpose

This unit discovers the real official schema of the TSE **Bens de candidatos** resources for the 2022 and
2026 elections before any RAW table or persistence pipeline is designed. It is intentionally non-mutating:
it downloads official ZIP artifacts into temporary directories, validates their structure, emits schema
evidence and safe aggregates, then deletes the temporary files. It never opens a database connection.

## Official resources pinned for discovery

The TSE Portal de Dados Abertos publishes **Bens de candidatos** as a CSV/ZIP resource inside the annual
Candidates datasets. The schema remains open in this unit; only source identity and transport expectations
are pinned.

### 2022

- annual package: `8747bd50-e1f7-407a-8e24-2707126ccde6`
- assets resource: `fac824ef-8519-4c75-b634-378e6fcc717f`
- artifact: `bem_candidato_2022.zip`
- canonical national CSV expected by the official naming convention: `bem_candidato_2022_BRASIL.csv`
- pinned CDN fallback: `https://cdn.tse.jus.br/estatistica/sead/odsele/bem_candidato/bem_candidato_2022.zip`

### 2026

- annual package: `ba2d7d69-5bf5-4379-8c91-664c11f75a2e`
- assets resource: `33fbda56-eb41-46f5-a8a0-8b499c285a1d`
- artifact: `bem_candidato_2026.zip`
- canonical national CSV expected by the official naming convention: `bem_candidato_2026_BRASIL.csv`
- pinned CDN fallback: `https://cdn.tse.jus.br/estatistica/sead/odsele/bem_candidato/bem_candidato_2026.zip`

References:

- `https://dadosabertos.tse.jus.br/dataset/candidatos-2022`
- `https://dadosabertos.tse.jus.br/dataset/candidatos-2026`

## Why the schema is deliberately not frozen yet

The resource IDs and ZIP transport are known from the official catalog, but persistence must not be designed
from assumptions about columns. `ASSETS_2022_DISCOVERY` and `ASSETS_2026_DISCOVERY` therefore set
`expected_headers=None`. The connector requires only the generic TSE generation/year headers during this
probe. Candidate linkage (`SQ_CANDIDATO`, `CD_ELEICAO`) and asset semantics are observations reported by
the probe, not prerequisites imposed before seeing the files.

## Probe output

Run:

```bash
python -m wv_eleicoes_data.ingestion.tse.asset_probe \
  --output /tmp/tse-assets-probe-2022-2026.json
```

The JSON contains, for each year:

- exact ordered headers;
- row and column counts;
- artifact SHA-256 and size;
- source generation timestamp;
- package/resource IDs and actual discovered download URL;
- presence of candidate-link and asset-semantic headers;
- safe one-to-many aggregates when `SQ_CANDIDATO` exists.

It also compares 2022 and 2026 layouts (`same_ordered_layout`, common headers and year-only headers). No
candidate identifier, asset description, asset value or other row value is emitted.

## Gate for the next unit

Do not create a RAW assets table yet. The next unit may freeze the contracts and design persistence only after
the probe proves the actual layouts and linkage fields for both years. Public product language must remain
**bens declarados ao TSE**; this dataset is a declaration source, not an independent audit of net worth.
