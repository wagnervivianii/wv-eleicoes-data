# TSE declared-assets temporal RAW ingestion

## Scope

This unit persists the frozen TSE **Bens de candidatos** contracts for any registered election year into one temporal RAW table. It deliberately stops before CORE and ANALYTICS. Public product language remains **bens declarados ao TSE** / **patrimônio declarado**; the source is a candidate declaration, not an independent audit of wealth.

## Generic annual onboarding

The pipeline is year-driven rather than table-per-year. A future election such as 2018 should first be probed and frozen in `contracts.py`; once registered in `SUPPORTED_ASSET_YEARS`, the same command and persistence engine apply:

```bash
python -m wv_eleicoes_data.ingestion.tse.asset_pipeline --year 2018
```

No `raw.tse_candidate_asset_2018` table is created. All supported years share `raw.tse_candidate_asset`, partitioned logically by `ANO_ELEICAO` and audit `scope_key=election-year:<year>`.

## Proven source contract

The natural item key proven by the 2022/2026 quality probe is:

- `ANO_ELEICAO`
- `CD_ELEICAO`
- `SQ_CANDIDATO`
- `NR_ORDEM_BEM_CANDIDATO`

The pipeline fails closed on blank/sentinel/duplicate keys, non-positive/non-integer asset order, wrong election year, or an asset referencing a candidacy that is not active in `raw.tse_candidate` for the same year.

The candidate source for a year must therefore be ingested before its assets.

## Source fidelity

All nineteen official columns are stored as text exactly as published. This is intentional:

- monetary values remain text in RAW, including negative values;
- empty asset descriptions remain empty strings;
- no decimal conversion is performed in RAW;
- `DT_GERACAO` and `HH_GERACAO` are retained but excluded from logical `content_hash`, so artifact regeneration alone does not create false semantic versions;
- item-level update date/time remain part of the hash and change audit.

Numeric typing belongs in a later CORE unit.

## Temporal behavior

One active version is allowed for each natural item key. A changed annual snapshot produces:

- `A` — new item;
- `M` — same natural item key with changed source fields;
- `D` — previously active item absent from the new complete snapshot.

Historical RAW rows are never deleted. `valid_from_run_id` and `valid_to_run_id` bound each version. `audit.asset_change` records the logical delta and exact changed official headers for modifications.

`audit.ingestion_run` remains the run-level lineage source. Checksum replay is compared only with the latest successfully applied snapshot for the same source/dataset/year scope. Thus A → B → A restores A instead of incorrectly skipping because A existed historically.

## Security

The API role receives no access to RAW or asset-change audit tables. `wv_eleicoes_ingestion` receives only:

- SELECT + INSERT on `raw.tse_candidate_asset`;
- column UPDATE for `valid_to_run_id` and `content_hash`;
- SELECT + INSERT on `audit.asset_change`;
- sequence usage needed for inserts.

No exception text or source row value is written into `audit.ingestion_run.error_message`.

## Commands

After migration:

```bash
python -m wv_eleicoes_data.ingestion.tse.asset_pipeline --year 2022
python -m wv_eleicoes_data.ingestion.tse.asset_pipeline --year 2026
```

A repeat of an identical latest checksum is `skipped`. A regenerated artifact with a different checksum but identical semantic row content is a successful run whose rows are all `rows_unchanged`.
