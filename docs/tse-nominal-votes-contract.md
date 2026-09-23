# TSE nominal votes — annual resource contract

## Scope

This unit freezes the official TSE `votacao_candidato_munzona` resource contract
for 2014, 2018 and 2022. It does not add persistence, migrations, ingestion
commands, analytics or API endpoints.

The existing `TseResourceContract` and connector are reused. CKAN remains the
preferred discovery path; the pinned official CDN URL remains the fallback only
for CKAN discovery HTTP 403, as already enforced by the connector.

## Official resources

| Year | Package ID | Resource ID | Canonical CSV |
| --- | --- | --- | --- |
| 2014 | `05b7d86e-d784-4b9c-8ba5-4428d64e4ec2` | `9df2487a-7d41-4e1f-8ca1-a9dbe43fdd02` | `votacao_candidato_munzona_2014_BRASIL.csv` |
| 2018 | `76d7bbbb-14c6-4b9a-beec-9ed87c2ad8b6` | `e1dae37e-c2d6-493c-bf66-437f3788af89` | `votacao_candidato_munzona_2018_BRASIL.csv` |
| 2022 | `5db2c9ef-a63b-4c0c-a2ec-d08002f49897` | `40fdcf49-256a-4c81-87cf-711545bd1528` | `votacao_candidato_munzona_2022_BRASIL.csv` |

All three observed resources are ZIP artifacts encoded as Latin-1 CSV with `;`
delimiter.

## Observed layouts

- 2014: 38 columns.
- 2018: 50 columns.
- 2022: 50 columns.
- 2018 and 2022 differ at the diploma-status fields:
  `CD_SITUACAO_DIPLOMA` / `DS_SITUACAO_DIPLOMA` in 2018 versus
  `CD_SITUACAO_DCONST_DIPLOMA` / `DS_SITUACAO_DCONST_DIPLOMA` in 2022.

The layouts are intentionally frozen per year. The application must normalize
historical differences after RAW instead of forcing one source schema across
years.

## Observed natural grain

The following grain was validated against the complete BRASIL CSVs:

```text
ANO_ELEICAO
+ CD_ELEICAO
+ NR_TURNO
+ SG_UF
+ CD_MUNICIPIO
+ NR_ZONA
+ SQ_CANDIDATO
+ ST_VOTO_EM_TRANSITO
```

Validation results:

| Year | Rows | Unique grain keys | Duplicates |
| ---: | ---: | ---: | ---: |
| 2014 | 7,905,274 | 7,905,274 | 0 |
| 2018 | 8,680,108 | 8,680,108 | 0 |
| 2022 | 9,377,845 | 9,377,845 | 0 |

`ST_VOTO_EM_TRANSITO` is required for historical stability: omitting it in
2014 produced 1,090 duplicate occurrences; including it reduced duplicates to
zero.

## Source generation metadata

Each inspected BRASIL CSV had exactly one generation timestamp and only its own
`ANO_ELEICAO`:

- 2014: `28/07/2021 11:54:31`
- 2018: `13/11/2024 10:56:11`
- 2022: `22/09/2026 03:16:37`

`source_updated_at` therefore remains source-generation metadata, not election
date.

## Extension rule

Adding another election year must be an explicit annual contract:

1. probe the official TSE resource;
2. freeze exact headers for that year;
3. validate the natural grain against the whole canonical BRASIL CSV;
4. add the contract to the supported-year registry;
5. keep downstream CORE/ANALYTICS/API year-agnostic.
