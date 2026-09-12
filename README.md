# WV Eleições Data

## Validação de migrations

Em um PostgreSQL local descartável de validação, provisionado com os papéis
`wv_eleicoes_owner`, `wv_eleicoes_ingestion` e `wv_eleicoes_api`, execute usando
o papel owner e a configuração de conexão fornecida pelo ambiente:

```sh
alembic upgrade head
alembic heads
alembic check
```

`alembic check` compara o banco já migrado com os modelos, incluindo os schemas
`raw` e `audit`. Ele não aplica migrations. `Target database is not up to date`
indica que há migrations pendentes no banco de validação; o orquestrador deve
aplicá-las nesse banco antes da comparação. Não use `stamp` para substituir
a execução das migrations e não execute este procedimento em produção.

## Candidaturas TSE 2026 — RAW

`raw.tse_candidate` preserva os 50 campos do contrato
`TSE_CANDIDATES_2026_HEADERS` em colunas `TEXT`, sem normalização. O mapeamento
`TSE_CANDIDATE_SOURCE_HEADERS` associa cada atributo snake_case ao cabeçalho
oficial. A migration mantém uma cópia congelada do layout, verificada pelos testes.

A identidade de origem é a combinação de execução de ingestão, arquivo e número
da linha de dados (iniciando em 1, sem contar o cabeçalho). O índice dessa restrição
única também atende consultas por execução; não há índices adicionais.
`SQ_CANDIDATO` identifica uma candidatura em uma eleição. CPF, título eleitoral
e email permanecem internos; esta camada não é publicada pela API.
