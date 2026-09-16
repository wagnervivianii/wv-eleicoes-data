# TSE declared-assets contract and quality probe

## Purpose

The declared-assets module is built from the official TSE **Bens de candidatos** resources. The public
product must describe these values as **bens declarados ao TSE** or **patrimônio declarado**; the dataset is
a declaration source and is not an independent audit of a person's net worth.

This work is intentionally split before persistence:

1. discover the real 2022/2026 layouts without a database;
2. freeze the observed official contracts;
3. measure item-key, money-format, timestamp and candidate-link quality;
4. only then design the RAW table and ingestion semantics.

No command in this document writes to PostgreSQL.

## Official resources

### 2022

- annual package: `8747bd50-e1f7-407a-8e24-2707126ccde6`
- assets resource: `fac824ef-8519-4c75-b634-378e6fcc717f`
- artifact: `bem_candidato_2022.zip`
- canonical CSV: `bem_candidato_2022_BRASIL.csv`
- CDN fallback: `https://cdn.tse.jus.br/estatistica/sead/odsele/bem_candidato/bem_candidato_2022.zip`

### 2026

- annual package: `ba2d7d69-5bf5-4379-8c91-664c11f75a2e`
- assets resource: `33fbda56-eb41-46f5-a8a0-8b499c285a1d`
- artifact: `bem_candidato_2026.zip`
- canonical CSV: `bem_candidato_2026_BRASIL.csv`
- CDN fallback: `https://cdn.tse.jus.br/estatistica/sead/odsele/bem_candidato/bem_candidato_2026.zip`

Official catalog references:

- `https://dadosabertos.tse.jus.br/dataset/candidatos-2022`
- `https://dadosabertos.tse.jus.br/dataset/candidatos-2026`

## Unit 05 evidence: observed schema

The official probe executed on 2026-09-15 proved exact positional equality between 2022 and 2026: both
national CSVs contain the same ordered 19-column layout.

```text
DT_GERACAO
HH_GERACAO
ANO_ELEICAO
CD_TIPO_ELEICAO
NM_TIPO_ELEICAO
CD_ELEICAO
DS_ELEICAO
DT_ELEICAO
SG_UF
SG_UE
NM_UE
SQ_CANDIDATO
NR_ORDEM_BEM_CANDIDATO
CD_TIPO_BEM_CANDIDATO
DS_TIPO_BEM_CANDIDATO
DS_BEM_CANDIDATO
VR_BEM_CANDIDATO
DT_ULT_ATUAL_BEM_CANDIDATO
HH_ULT_ATUAL_BEM_CANDIDATO
```

Observed publication evidence:

| Year | Rows | Distinct candidate sequences | Candidates with >1 asset | Maximum assets/candidate | Blank SQ_CANDIDATO |
| --- | ---: | ---: | ---: | ---: | ---: |
| 2022 | 92,559 | 18,249 | 13,572 | 180 | 0 |
| 2026 | 77,139 | 13,899 | 10,538 | 152 | 0 |

Observed artifact SHA-256 values are evidence of those publications, not permanent constants:

- 2022: `f4c606bb18e72cb15d5c34b0107879785693cec0be081009f4efa72ae57866d8`
- 2026: `247ff8a58cb319c75a464aac8351d38c7f58efc5fbe5245be3e6f43395731f55`

The observed source-generation timestamp for 2022 was in 2026. This confirms that `DT_GERACAO` /
`HH_GERACAO` describe the current official publication snapshot, not the election date.

## Frozen contracts

`ASSETS_2022` and `ASSETS_2026` now require the exact ordered 19-column layout above. The schema-open
`ASSETS_2022_DISCOVERY` and `ASSETS_2026_DISCOVERY` contracts remain available to reproduce discovery in
future investigations.

The natural candidate linkage exposed by the official files is:

```text
CD_ELEICAO + SQ_CANDIDATO
```

Inside WV Eleições that corresponds to the already established public identity scope:

```text
election:<ANO_ELEICAO>:<CD_ELEICAO> + candidacy_sequence=SQ_CANDIDATO
```

No name matching is required.

## Unit 06: non-mutating data-quality contract

Before a RAW table is created, run:

```bash
python -m wv_eleicoes_data.ingestion.tse.asset_quality_probe \
  --output /tmp/tse-assets-quality-2022-2026.json
```

The probe downloads the frozen assets artifact and frozen candidates artifact for each supported year, then
emits only safe aggregates. It never prints candidate identifiers, asset descriptions or individual values.

It measures:

- uniqueness of the proposed item key
  `(ANO_ELEICAO, CD_ELEICAO, SQ_CANDIDATO, NR_ORDEM_BEM_CANDIDATO)`;
- blank/non-integer/zero/negative asset-order rows;
- distinct asset candidacy keys and how many do not resolve in the official candidates file for the same year;
- blank type code, type name and description rows;
- monetary lexical shapes in `VR_BEM_CANDIDATO` without exposing values;
- known TSE sentinel values separately from numeric values;
- negative numeric rows and maximum observed decimal scale;
- blank or invalid `DT_ULT_ATUAL_BEM_CANDIDATO` / `HH_ULT_ATUAL_BEM_CANDIDATO` timestamps.

Recognized money shapes are deliberately broader than the future persistence contract: integer, decimal
comma, decimal point, Brazilian grouped decimal and US grouped decimal. Any other representation is counted
as `unrecognized_value_rows` so storage/normalization rules can be based on evidence instead of guesses.

## Gate for persistence

Do not create `raw.tse_candidate_asset` until the quality probe has answered, for both years:

- whether the proposed item key is unique;
- whether every asset candidacy resolves against the official candidate resource;
- which lexical monetary format(s) actually occur;
- whether any values are blank, sentinel, negative or unrecognized;
- whether asset update timestamps are structurally valid.

RAW should remain source-faithful. Typed monetary normalization belongs in a later CORE/ANALYTICS layer once
these observations are known.
