# WV Eleições Data

Camada de dados e ingestão do **WV Eleições**, uma plataforma modular de dados
eleitorais e história política longitudinal. Este repositório transforma arquivos
oficiais do TSE em versões rastreáveis de candidaturas e modelos de leitura seguros
para consumo público. A API e o frontend pertencem a repositórios independentes.

O foco de engenharia é tornar cada resultado explicável: origem identificada,
conteúdo de fonte preservado, reconciliação idempotente, histórico temporal e
privilégios mínimos. O escopo implementado é **Candidatos TSE 2026**; integração
histórica e acompanhamento de mandatos fazem parte da evolução planejada.

**Navegação:** [arquitetura](#arquitetura-de-dados) · [contrato TSE](#contrato-da-fonte)
· [incremental](#reconciliação-incremental) · [auditoria](#histórico-temporal)
· [consultas](#modelos-públicos-e-consultas) · [migrations](#migrations)
· [desenvolvimento](#desenvolvimento-e-qualidade) · [roadmap](#checkpoint-e-roadmap)

## Stack

- **Python 3.12** como alvo de runtime e ferramentas (`requires-python >=3.12`).
- **PostgreSQL 16** como banco alvo; SQLAlchemy 2.x e Psycopg 3 para persistência,
  Alembic para evolução versionada de schemas e privilégios.
- **HTTPX** para descoberta/download e **Tenacity** para tentativas com espera
  exponencial em falhas transitórias.
- Biblioteca padrão: `csv` para leitura fiel, `zipfile` para validação do arquivo,
  `hashlib` para SHA-256, `json` para delimitação inequívoca do hash semântico e
  `zoneinfo` para o horário informado pela fonte.
- Pydantic/Pydantic Settings para configuração; pandas integra as dependências,
  mas o parser deste conector usa `csv`.
- **pytest**, **Ruff** e **mypy** para testes, lint e tipagem estrita.

As dependências e os parâmetros de qualidade estão em [pyproject.toml](pyproject.toml).
A versão efetiva do banco deve ser validada no ambiente de desenvolvimento;
a declaração de alvo não representa evidência de execução contra PostgreSQL.

## Arquitetura de dados

| Schema | Responsabilidade | Situação neste repositório |
| --- | --- | --- |
| `raw` | Valores de fonte e proveniência, sem interpretação semântica | `tse_candidate`, com versões e vigência |
| `staging` | Normalização e interpretação intermediária | Reservado; não há população implementada |
| `core` | Contrato canônico do domínio | View tipada `candidate` |
| `analytics` | Projeções de consulta e publicação | Materialized views `candidate_2026` e `candidate` |
| `audit` | Linhagem e histórico de ingestão | `ingestion_run` e ledger `candidate_change` |

Fluxo atual:

```text
Contrato TSE → download e validação → reconciliação RAW + audit (transação)
                                  → refresh após commit
                                  → analytics.candidate_2026
                                  → core.candidate → analytics.candidate
```

A normalização atual ocorre na view `core.candidate`, sobre a projeção permitida.
O schema `staging` delimita uma responsabilidade futura, sem sugerir um pipeline
já implementado nessa camada. Os modelos usam a Base SQLAlchemy compartilhada.

## Contrato da fonte

[contracts.py](src/wv_eleicoes_data/ingestion/tse/contracts.py) fixa o recurso oficial
TSE/CKAN: pacote `ba2d7d69-5bf5-4379-8c91-664c11f75a2e`, recurso
`7748de82-a23b-47c4-9ec1-35535d945e5b`, dataset `candidatos`, eleição 2026.
O conector descobre o download por `resource_show`; somente um HTTP 403 nessa
etapa permite o fallback oficial fixado no contrato. As validações permanecem
obrigatórias e outras falhas de descoberta são propagadas.

| Propriedade | Contrato |
| --- | --- |
| Artefato | `consulta_cand_2026.zip` |
| CSV canônico | `consulta_cand_2026_BRASIL.csv`, exatamente uma ocorrência |
| Cabeçalho | 50 colunas, nomes e ordem oficiais |
| Codificação | Latin-1 |
| Delimitador / aspas | Ponto e vírgula / aspas duplas |
| Horário da fonte | `America/Sao_Paulo` |

O conector valida ZIP, caminhos internos, cabeçalho, linhas e timestamp de geração.
O SHA-256 identifica os bytes do artefato. A ingestão registra execução, arquivo,
linha e demais metadados de proveniência para localizar a origem de cada versão.

**RAW preserva exatamente as strings decodificadas da fonte**, inclusive espaços,
zeros à esquerda e sentinelas `#NULO`, `#NE`, `NÃO DIVULGÁVEL`, `-1`, `-3`, `-4`.
Não há conversão desses marcadores em zero nem normalização do payload RAW.
Imutabilidade refere-se aos valores de fonte: metadados de encerramento de vigência
e bootstrap de hash podem ser atualizados sob permissões específicas.

CPF, título eleitoral e email são dados internos restritos. Nenhum exemplo de
registro pessoal é necessário para explicar ou testar o contrato público.

## Reconciliação incremental

Cada execução baixa e valida o arquivo completo. O ganho incremental está na
persistência: compara-se o snapshot com as versões ativas, sem reinserir todas as
candidaturas a cada publicação.

Há dois hashes com responsabilidades diferentes:

1. **SHA-256 do ZIP:** comparado apenas ao último snapshot aplicado com sucesso,
   ordenado por término e ID da execução. Igualdade produz `skipped`; execuções
   falhas ou ignoradas não avançam essa referência.
2. **`content_hash` da candidatura:** SHA-256 de um array JSON compacto em UTF-8,
   com `ensure_ascii=False`, contendo as strings exatas na ordem oficial e
   excluindo **somente `DT_GERACAO` e `HH_GERACAO`**. Essa delimitação preserva
   fronteiras de campos, espaços, quebras de linha e sentinelas.

A chave natural é a tupla exata **`(ANO_ELEICAO, CD_ELEICAO, SQ_CANDIDATO)`**.
Chaves duplicadas na entrada, componentes vazios ou sentinelas invalidam a carga
inteira. O ano aceito pelo contrato atual é exatamente `2026`. O trim serve apenas
para detectar componentes inválidos; não altera a chave armazenada.
`SQ_CANDIDATO` identifica uma candidatura em uma eleição, nunca uma pessoa permanente.

| Resultado | Persistência |
| --- | --- |
| A — adição | Insere versão ativa e evento A |
| M — modificação | Encerra versão anterior, insere nova versão e evento M |
| D — remoção | Encerra versão ativa e registra D, sem apagar a linha RAW |
| Unchanged | Mantém versão, proveniência e campos de publicação originais |

`valid_from_run_id` marca a entrada da versão; `valid_to_run_id` é exclusivo e
`NULL` indica versão ativa. `rows_inserted = rows_added + rows_updated`, sendo
`rows_updated` a contagem lógica de M. Execuções ignoradas têm deltas zerados.
Um ZIP diferente apenas em metadados de geração pode concluir com sucesso e todas
as candidaturas unchanged.

**Replay A → B → A:** o último A é reconciliado contra B; não é ignorado por já
ter existido no passado. Comparação e bootstrap de hashes são isolados pelo ano
exato do contrato, sem usar o nome de arquivo como filtro adicional. A publicação
2026 mantém seu próprio filtro de ano e arquivo canônico, evitando mistura de eleições.

Um advisory lock transacional por dataset serializa a aplicação dos snapshots.
Em `READ COMMITTED`, a consulta após o lock observa o commit anterior. Encerramentos,
inserções, ledger e contadores de sucesso são atômicos. Falhas desfazem esse conjunto;
outra transação registra o erro sem payload da fonte ou parâmetros da exceção.
Os lotes de payload/eventos têm até 1.000 linhas; a memória de comparação cresce
com as chaves/hashes ativos e as chaves recebidas.

## Histórico temporal

`audit.candidate_change` registra A/M/D com execução, chave eleitoral,
`old_raw_candidate_id` e/ou `new_raw_candidate_id`. Índices permitem inspeção por
execução, eleição e histórico da candidatura.

- `source_snapshot_at`: geração do snapshot TSE em que a mudança foi observada;
  não afirma o instante exato do evento político ou da alteração no TSE.
- `detected_at`: instante registrado pelo banco ao persistir a detecção na plataforma.
- `changed_fields`: em M, array JSON ordenado de nomes oficiais dos campos alterados,
  por comparação exata, excluindo os dois campos de geração. Em A/D, é `NULL`.

Valores antigos e novos **não são duplicados no ledger**. Uma investigação interna
autorizada pode seguir os IDs até as versões RAW imutáveis. Isso conserva a
rastreabilidade sem criar uma segunda cópia de campos pessoais restritos na auditoria.

## Modelos públicos e consultas

A publicação usa **allowlists explícitas** de eleição, circunscrição, cargo,
candidatura, número/nome de urna, partido e situação, mais IDs numéricos de linhagem.
CPF, título eleitoral, email, data de nascimento, dados demográficos, nomes
civil/social, caminhos e metadados operacionais não integram essas projeções.
Os IDs de linhagem não concedem acesso às tabelas internas.

`analytics.candidate_2026` seleciona versões ativas do CSV canônico de 2026.
`core.candidate` oferece nomes genéricos e tipos estáveis; `analytics.candidate`
materializa esse contrato para consultas. Ano e turno são `SMALLINT` validados:
ano com quatro dígitos exceto `0000`; turno de 1 a 99 sem zero inicial. Valores
inválidos tornam-se `NULL` sem casts arriscados. Identificadores continuam `TEXT`,
preservando zeros à esquerda. Na camada semântica, espaços externos são removidos
e vazios/sentinelas tornam-se `NULL`; o RAW permanece intacto.

A unidade é a observação de candidatura, não a pessoa. `raw_candidate_id` é a
chave única de publicação. Número de urna não é identificador global; consultas
podem retornar múltiplos resultados em contextos eleitorais distintos. As contagens
contam observações, inclusive duplicidades legadas quando aplicáveis.

O SQL parametrizado está em [candidates.py](src/wv_eleicoes_data/analytics/candidates.py):

| Consulta | Filtros / ordenação | Índice previsto |
| --- | --- | --- |
| Lista | Ano + UF + cargo; cursor por RAW ID | B-tree composto de filtro |
| Partido | Filtros da lista + número do partido | B-tree composto de partido |
| Número exato | Filtros da lista + número textual de urna | B-tree composto de número |
| Nome de urna | Filtros da lista + tokens do nome | GIN sobre `tsvector` com configuração `simple` |
| Contagem por partido | Ano + UF + cargo; agrupamento por partido | B-tree de partido ou agregação sequencial |

Paginação usa `raw_candidate_id > :after`, ordem crescente e `LIMIT :limit`.
O consumidor deve vincular parâmetros, validar ano positivo/cursor não negativo,
limitar páginas (sugestão: 100) e rejeitar buscas vazias. Essas validações são
responsabilidade do consumidor futuro; este módulo fornece as consultas SQL.
A busca é por tokens inteiros, sem distinção de caixa, sensível a acentos e com
semântica AND; não oferece substring, fuzzy matching ou remoção de acentos.
Consultas só com pontuação não encontram linhas. Partido `NULL` significa dado
indisponível, nunca partido zero. Para percorrer um conjunto completo, reinicie
após refresh: cursores só são estáveis dentro do snapshot publicado.

O modelo genérico tem cinco índices: um unique completo para refresh, três B-trees
para filtros/ordenação distintos e um GIN. Não há promessa de uso obrigatório de
índice: seletividade e custos podem favorecer varredura sequencial.

### Publicação e privilégios

Após o commit da ingestão, `refresh_candidates(engine)` usa uma conexão do owner
e outra transação: adquire advisory lock, executa `REFRESH MATERIALIZED VIEW
CONCURRENTLY` primeiro em `candidate_2026`, depois em `candidate`, e publica ambas
atomicamente. As views já são populadas e recebem índices únicos nas migrations.
Uma falha mantém a publicação anterior e permite retry independente, sem invalidar
a ingestão já concluída. Todos os chamadores devem usar o helper/lock para serializar
refreshes; não existe agendamento automático no pipeline.

| Papel conceitual | Responsabilidade |
| --- | --- |
| `wv_eleicoes_owner` | Estrutura, migrations e refresh das projeções |
| `wv_eleicoes_ingestion` | Escrita operacional e auditoria; em RAW, sem DELETE e com UPDATE apenas de vigência/hash |
| `wv_eleicoes_api` | Leitura permitida em core/analytics; sem acesso a raw/audit |

As migrations aplicam grants explícitos às projeções e retiram os privilégios de
escrita herdados da ingestão nesses objetos. Não introduzem funções
`SECURITY DEFINER` nem memberships adicionais. Os papéis devem existir no banco
local usado para validar migrations; sua administração não é implementada aqui.

## Migrations

A cadeia é linear e deve ser lida na ordem abaixo:

| Revisão | Evolução |
| --- | --- |
| `11df84fdab45` | Cria os cinco schemas |
| `fe71aac9b2ed` | Configura privilégios por papel e privilégios padrão |
| `2ae610ff28cd` | Adiciona `audit.ingestion_run` |
| `8c31b79e5a02` | Cria RAW de candidatos com contrato de colunas congelado e proveniência |
| `b4702026ca01` | Primeira materialized view pública 2026, baseada no último run bem-sucedido |
| `c5812026ca02` | Contrato tipado em core, materialização genérica, consultas e índices |
| `d6922026ca03` | Vigência/hash, reconciliação incremental, contadores A/M/D, ledger temporal e projeções por versões ativas |

A última migration preserva as linhas legadas. Dentro de cada chave, versões
bem-sucedidas são ordenadas por término, run ID e RAW ID; a última fica ativa e
as anteriores encerram na próxima versão. Linhas de execuções malsucedidas encerram
no próprio run. Chaves ausentes do último snapshot legado podem continuar ativas
até a próxima reconciliação com artefato diferente. Hashes legados começam `NULL`
e recebem bootstrap transacional nessa reconciliação; eventos históricos A/M/D
não são inventados.

A reconstrução das projeções preserva allowlists, grants e índices, mas exige locks
e materialização completa. O downgrade automático de `d6922026ca03` é recusado:
o leitor anterior de snapshots completos não representa com segurança o histórico
de deltas. Recuperação exige backup ou migration corretiva revisada.

## Estrutura do repositório

```text
README.md                 Portfólio, arquitetura e desenvolvimento
src/wv_eleicoes_data/
  config.py               Configuração tipada
  db/                     Base e modelos SQLAlchemy
  ingestion/tse/          Contrato, conector, reconciliação e pipeline
  analytics/              Consultas, refresh e coleta de evidências
migrations/               Ambiente Alembic e cadeia de revisões
tests/                    Testes de ingestão, contratos, banco e SQL
pyproject.toml            Pacote, dependências e qualidade
alembic.ini               Configuração do Alembic
.env.example              Modelo de configuração local preservado
.gitignore                Exclusões de arquivos locais e gerados
```

O conteúdo arquitetural útil de `docs/` foi consolidado neste README; o diretório
redundante foi removido. `migrations/README` permanece junto ao ambiente Alembic.

## Desenvolvimento e qualidade

Em um ambiente Python 3.12 de desenvolvimento já ativado, instale o pacote:

```sh
python -m pip install -e '.[dev]'
python -m ruff check src tests migrations
python -m mypy src
python -m pytest -q
git diff --check
git status --short
```

A ativação do ambiente e a configuração local ficam a cargo do ambiente de
execução/orquestrador. Nenhuma credencial ou configuração de host deve ser versionada.
A CLI de ingestão é `python -m wv_eleicoes_data.ingestion.tse.pipeline`; ela exige
uma conexão explícita de ingestão e não usa fallback para a conexão do owner.

Para gerar SQL Alembic sem conectar a um banco, com o ambiente local configurado:

```sh
python -m alembic upgrade head --sql > /tmp/wv_eleicoes_upgrade.sql
```

A geração offline verifica a emissão da cadeia, mas não comprova sua aplicação
em PostgreSQL. Em banco **local descartável**, os testes opcionais recebem uma
URL explícita, fornecida pelo ambiente de testes:

```sh
python -m pytest tests/db -q --analytics-test-url="$LOCAL_TEST_DATABASE_URL"
```

Esse banco deve estar em `8c31b79e5a02`, com os três papéis existentes e sem as
projeções posteriores: os testes constroem seus cenários em transações revertidas.
Sem a opção, os testes de integração correspondentes são pulados. Não use um banco
com dados que precisem ser preservados. Validações autoritativas de migrations
(`upgrade`, `current`, `heads`, `check`) pertencem ao orquestrador no banco local.

A suíte cobre contrato CSV/ZIP, fallback 403, preservação RAW, idempotência,
replay, isolamento eleitoral, deltas e ledger, falhas transacionais, allowlists,
SQL de migrations e consultas tipadas. Testes locais não substituem evidência de
concorrência e planos de execução no PostgreSQL.
`collect_candidate_evidence(connection)`, no módulo `analytics/validation.py`,
coleta contagens e planos das cinco famílias de consulta em uma transação
repeatable-read. Seu comparador de contagens ainda usa as linhas do último run
bem-sucedido, enquanto a publicação incremental usa todas as versões ativas:
pode apontar divergência após deltas e precisa ser adaptado antes de servir como
gate de consistência incremental. A saída omite valores de fonte e expressões
dos planos; não há benchmark ou latência de dados reais prometidos neste README.

Fluxo de contribuição: **alteração local → testes → commit → push → PR/merge**.
A publicação Git é conduzida pelo orquestrador do projeto. Deploy de runtime/produção
está intencionalmente fora deste repositório; configurações de host não são
versionadas aqui.

## Checkpoint e roadmap

O checkpoint funcional canônico **`71d7df6`** reúne reconciliação incremental e
ledger temporal. Este README documenta esse estado do código. O commit de
documentação avançará naturalmente `main` após o merge, sem substituir a referência
histórica da funcionalidade.

Próximos passos da plataforma:

- API pública FastAPI em `wv-eleicoes-api`, consumindo somente modelos permitidos.
- Frontend em `wv-eleicoes-web`, independente da ingestão.
- Outros datasets TSE e eleições históricas, com discriminadores explícitos de
  recurso/ano antes de ampliar o adaptador público.
- História política longitudinal e acompanhamento de mandatos, com identidade
  de pessoa modelada separadamente da chave de candidatura.

A base entregue combina reprodutibilidade de contratos e migrations, linhagem
até a fonte, payload imutável, idempotência por estado aplicado, histórico temporal
e modelos públicos orientados a privilégio mínimo.
