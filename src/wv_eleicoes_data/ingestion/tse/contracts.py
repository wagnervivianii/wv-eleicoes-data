from dataclasses import dataclass, replace

TSE_CANDIDATES_2026_HEADERS = (
    "DT_GERACAO",
    "HH_GERACAO",
    "ANO_ELEICAO",
    "CD_TIPO_ELEICAO",
    "NM_TIPO_ELEICAO",
    "NR_TURNO",
    "CD_ELEICAO",
    "DS_ELEICAO",
    "DT_ELEICAO",
    "TP_ABRANGENCIA",
    "SG_UF",
    "SG_UE",
    "NM_UE",
    "CD_CARGO",
    "DS_CARGO",
    "SQ_CANDIDATO",
    "NR_CANDIDATO",
    "NM_CANDIDATO",
    "NM_URNA_CANDIDATO",
    "NM_SOCIAL_CANDIDATO",
    "NR_CPF_CANDIDATO",
    "DS_EMAIL",
    "CD_SITUACAO_CANDIDATURA",
    "DS_SITUACAO_CANDIDATURA",
    "TP_AGREMIACAO",
    "NR_PARTIDO",
    "SG_PARTIDO",
    "NM_PARTIDO",
    "NR_FEDERACAO",
    "NM_FEDERACAO",
    "SG_FEDERACAO",
    "DS_COMPOSICAO_FEDERACAO",
    "SQ_COLIGACAO",
    "NM_COLIGACAO",
    "DS_COMPOSICAO_COLIGACAO",
    "SG_UF_NASCIMENTO",
    "DT_NASCIMENTO",
    "NR_TITULO_ELEITORAL_CANDIDATO",
    "CD_GENERO",
    "DS_GENERO",
    "CD_GRAU_INSTRUCAO",
    "DS_GRAU_INSTRUCAO",
    "CD_ESTADO_CIVIL",
    "DS_ESTADO_CIVIL",
    "CD_COR_RACA",
    "DS_COR_RACA",
    "CD_OCUPACAO",
    "DS_OCUPACAO",
    "CD_SIT_TOT_TURNO",
    "DS_SIT_TOT_TURNO",
)

# The official 2022 probe on 2026-09-15 proved exact positional equality with 2026.
# Keep a semantic alias so future years may diverge without rewriting call sites.
TSE_CANDIDATES_2022_HEADERS = TSE_CANDIDATES_2026_HEADERS


TSE_ASSETS_2022_HEADERS = (
    "DT_GERACAO",
    "HH_GERACAO",
    "ANO_ELEICAO",
    "CD_TIPO_ELEICAO",
    "NM_TIPO_ELEICAO",
    "CD_ELEICAO",
    "DS_ELEICAO",
    "DT_ELEICAO",
    "SG_UF",
    "SG_UE",
    "NM_UE",
    "SQ_CANDIDATO",
    "NR_ORDEM_BEM_CANDIDATO",
    "CD_TIPO_BEM_CANDIDATO",
    "DS_TIPO_BEM_CANDIDATO",
    "DS_BEM_CANDIDATO",
    "VR_BEM_CANDIDATO",
    "DT_ULT_ATUAL_BEM_CANDIDATO",
    "HH_ULT_ATUAL_BEM_CANDIDATO",
)

# The official 2022/2026 probe on 2026-09-15 proved exact positional equality.
TSE_ASSETS_2026_HEADERS = TSE_ASSETS_2022_HEADERS


TSE_VOTES_2014_HEADERS = (
    "DT_GERACAO",
    "HH_GERACAO",
    "ANO_ELEICAO",
    "CD_TIPO_ELEICAO",
    "NM_TIPO_ELEICAO",
    "NR_TURNO",
    "CD_ELEICAO",
    "DS_ELEICAO",
    "DT_ELEICAO",
    "TP_ABRANGENCIA",
    "SG_UF",
    "SG_UE",
    "NM_UE",
    "CD_MUNICIPIO",
    "NM_MUNICIPIO",
    "NR_ZONA",
    "CD_CARGO",
    "DS_CARGO",
    "SQ_CANDIDATO",
    "NR_CANDIDATO",
    "NM_CANDIDATO",
    "NM_URNA_CANDIDATO",
    "NM_SOCIAL_CANDIDATO",
    "CD_SITUACAO_CANDIDATURA",
    "DS_SITUACAO_CANDIDATURA",
    "CD_DETALHE_SITUACAO_CAND",
    "DS_DETALHE_SITUACAO_CAND",
    "TP_AGREMIACAO",
    "NR_PARTIDO",
    "SG_PARTIDO",
    "NM_PARTIDO",
    "SQ_COLIGACAO",
    "NM_COLIGACAO",
    "DS_COMPOSICAO_COLIGACAO",
    "CD_SIT_TOT_TURNO",
    "DS_SIT_TOT_TURNO",
    "ST_VOTO_EM_TRANSITO",
    "QT_VOTOS_NOMINAIS",
)

TSE_VOTES_2018_HEADERS = (
    "DT_GERACAO",
    "HH_GERACAO",
    "ANO_ELEICAO",
    "CD_TIPO_ELEICAO",
    "NM_TIPO_ELEICAO",
    "NR_TURNO",
    "CD_ELEICAO",
    "DS_ELEICAO",
    "DT_ELEICAO",
    "TP_ABRANGENCIA",
    "SG_UF",
    "SG_UE",
    "NM_UE",
    "CD_MUNICIPIO",
    "NM_MUNICIPIO",
    "NR_ZONA",
    "CD_CARGO",
    "DS_CARGO",
    "SQ_CANDIDATO",
    "NR_CANDIDATO",
    "NM_CANDIDATO",
    "NM_URNA_CANDIDATO",
    "NM_SOCIAL_CANDIDATO",
    "CD_SITUACAO_CANDIDATURA",
    "DS_SITUACAO_CANDIDATURA",
    "CD_DETALHE_SITUACAO_CAND",
    "DS_DETALHE_SITUACAO_CAND",
    "CD_SITUACAO_JULGAMENTO",
    "DS_SITUACAO_JULGAMENTO",
    "CD_SITUACAO_CASSACAO",
    "DS_SITUACAO_CASSACAO",
    "CD_SITUACAO_DIPLOMA",
    "DS_SITUACAO_DIPLOMA",
    "TP_AGREMIACAO",
    "NR_PARTIDO",
    "SG_PARTIDO",
    "NM_PARTIDO",
    "NR_FEDERACAO",
    "NM_FEDERACAO",
    "SG_FEDERACAO",
    "DS_COMPOSICAO_FEDERACAO",
    "SQ_COLIGACAO",
    "NM_COLIGACAO",
    "DS_COMPOSICAO_COLIGACAO",
    "ST_VOTO_EM_TRANSITO",
    "QT_VOTOS_NOMINAIS",
    "NM_TIPO_DESTINACAO_VOTOS",
    "QT_VOTOS_NOMINAIS_VALIDOS",
    "CD_SIT_TOT_TURNO",
    "DS_SIT_TOT_TURNO",
)

TSE_VOTES_2022_HEADERS = (
    "DT_GERACAO",
    "HH_GERACAO",
    "ANO_ELEICAO",
    "CD_TIPO_ELEICAO",
    "NM_TIPO_ELEICAO",
    "NR_TURNO",
    "CD_ELEICAO",
    "DS_ELEICAO",
    "DT_ELEICAO",
    "TP_ABRANGENCIA",
    "SG_UF",
    "SG_UE",
    "NM_UE",
    "CD_MUNICIPIO",
    "NM_MUNICIPIO",
    "NR_ZONA",
    "CD_CARGO",
    "DS_CARGO",
    "SQ_CANDIDATO",
    "NR_CANDIDATO",
    "NM_CANDIDATO",
    "NM_URNA_CANDIDATO",
    "NM_SOCIAL_CANDIDATO",
    "CD_SITUACAO_CANDIDATURA",
    "DS_SITUACAO_CANDIDATURA",
    "CD_DETALHE_SITUACAO_CAND",
    "DS_DETALHE_SITUACAO_CAND",
    "CD_SITUACAO_JULGAMENTO",
    "DS_SITUACAO_JULGAMENTO",
    "CD_SITUACAO_CASSACAO",
    "DS_SITUACAO_CASSACAO",
    "CD_SITUACAO_DCONST_DIPLOMA",
    "DS_SITUACAO_DCONST_DIPLOMA",
    "TP_AGREMIACAO",
    "NR_PARTIDO",
    "SG_PARTIDO",
    "NM_PARTIDO",
    "NR_FEDERACAO",
    "NM_FEDERACAO",
    "SG_FEDERACAO",
    "DS_COMPOSICAO_FEDERACAO",
    "SQ_COLIGACAO",
    "NM_COLIGACAO",
    "DS_COMPOSICAO_COLIGACAO",
    "ST_VOTO_EM_TRANSITO",
    "QT_VOTOS_NOMINAIS",
    "NM_TIPO_DESTINACAO_VOTOS",
    "QT_VOTOS_NOMINAIS_VALIDOS",
    "CD_SIT_TOT_TURNO",
    "DS_SIT_TOT_TURNO",
)

TSE_NOMINAL_VOTE_GRAIN_HEADERS = (
    "ANO_ELEICAO",
    "CD_ELEICAO",
    "NR_TURNO",
    "SG_UF",
    "CD_MUNICIPIO",
    "NR_ZONA",
    "SQ_CANDIDATO",
    "ST_VOTO_EM_TRANSITO",
)

TSE_TABULAR_DISCOVERY_REQUIRED_HEADERS = (
    "DT_GERACAO",
    "HH_GERACAO",
    "ANO_ELEICAO",
)


TSE_VOTE_DISCOVERY_REQUIRED_HEADERS = (
    *TSE_TABULAR_DISCOVERY_REQUIRED_HEADERS,
    "CD_ELEICAO",
    "NR_TURNO",
    "SG_UF",
    "CD_MUNICIPIO",
    "NR_ZONA",
    "SQ_CANDIDATO",
    "ST_VOTO_EM_TRANSITO",
    "QT_VOTOS_NOMINAIS",
)

TSE_CANDIDATE_DISCOVERY_REQUIRED_HEADERS = (
    *TSE_TABULAR_DISCOVERY_REQUIRED_HEADERS,
    "CD_ELEICAO",
    "SQ_CANDIDATO",
)


@dataclass(frozen=True, slots=True)
class TseResourceContract:
    """Immutable contract for one official TSE CKAN resource."""

    source: str
    dataset: str
    election_year: int
    package_id: str
    resource_id: str
    ckan_api_base_url: str
    artifact_name: str
    canonical_csv_name: str
    encoding: str
    delimiter: str
    quotechar: str
    source_timezone: str
    expected_mimetype: str
    expected_headers: tuple[str, ...] | None
    fallback_download_url: str | None = None
    discovery_required_headers: tuple[str, ...] = TSE_CANDIDATE_DISCOVERY_REQUIRED_HEADERS

    @property
    def resource_show_url(self) -> str:
        """Return the CKAN endpoint used to discover the current download URL."""

        return f"{self.ckan_api_base_url}/resource_show"

    @property
    def is_schema_discovery(self) -> bool:
        """Return whether this contract discovers instead of freezing the CSV schema."""

        return self.expected_headers is None

    @property
    def scope_key(self) -> str:
        """Return the audit/idempotency scope for this annual election resource."""

        return f"election-year:{self.election_year}"


CANDIDATES_2026 = TseResourceContract(
    source="TSE",
    dataset="candidatos",
    election_year=2026,
    package_id="ba2d7d69-5bf5-4379-8c91-664c11f75a2e",
    resource_id="7748de82-a23b-47c4-9ec1-35535d945e5b",
    ckan_api_base_url="https://dadosabertos.tse.jus.br/api/3/action",
    artifact_name="consulta_cand_2026.zip",
    canonical_csv_name="consulta_cand_2026_BRASIL.csv",
    encoding="latin-1",
    delimiter=";",
    quotechar='"',
    source_timezone="America/Sao_Paulo",
    expected_mimetype="application/zip",
    expected_headers=TSE_CANDIDATES_2026_HEADERS,
    fallback_download_url=(
        "https://cdn.tse.jus.br/estatistica/sead/odsele/consulta_cand/consulta_cand_2026.zip"
    ),
)

CANDIDATES_2022 = TseResourceContract(
    source="TSE",
    dataset="candidatos",
    election_year=2022,
    package_id="8747bd50-e1f7-407a-8e24-2707126ccde6",
    resource_id="435145fd-bc9d-446a-ac9d-273f585a0bb9",
    ckan_api_base_url="https://dadosabertos.tse.jus.br/api/3/action",
    artifact_name="consulta_cand_2022.zip",
    canonical_csv_name="consulta_cand_2022_BRASIL.csv",
    encoding="latin-1",
    delimiter=";",
    quotechar='"',
    source_timezone="America/Sao_Paulo",
    expected_mimetype="application/zip",
    expected_headers=TSE_CANDIDATES_2022_HEADERS,
    fallback_download_url=(
        "https://cdn.tse.jus.br/estatistica/sead/odsele/consulta_cand/consulta_cand_2022.zip"
    ),
)

# Retained as a deliberately schema-open contract for reproducible future probes.
CANDIDATES_2022_DISCOVERY = replace(CANDIDATES_2022, expected_headers=None)

_SUPPORTED_CANDIDATE_CONTRACTS = {
    2022: CANDIDATES_2022,
    2026: CANDIDATES_2026,
}
SUPPORTED_CANDIDATE_YEARS = tuple(sorted(_SUPPORTED_CANDIDATE_CONTRACTS))


def candidates_contract_for_year(year: int) -> TseResourceContract:
    """Return the frozen official candidates contract for one supported election year."""

    try:
        return _SUPPORTED_CANDIDATE_CONTRACTS[year]
    except KeyError as exc:
        raise ValueError(f"unsupported TSE candidates year: {year}") from exc


ASSETS_2022_DISCOVERY = TseResourceContract(
    source="TSE",
    dataset="bens_candidatos",
    election_year=2022,
    package_id="8747bd50-e1f7-407a-8e24-2707126ccde6",
    resource_id="fac824ef-8519-4c75-b634-378e6fcc717f",
    ckan_api_base_url="https://dadosabertos.tse.jus.br/api/3/action",
    artifact_name="bem_candidato_2022.zip",
    canonical_csv_name="bem_candidato_2022_BRASIL.csv",
    encoding="latin-1",
    delimiter=";",
    quotechar='"',
    source_timezone="America/Sao_Paulo",
    expected_mimetype="application/zip",
    expected_headers=None,
    fallback_download_url=(
        "https://cdn.tse.jus.br/estatistica/sead/odsele/bem_candidato/"
        "bem_candidato_2022.zip"
    ),
    discovery_required_headers=TSE_TABULAR_DISCOVERY_REQUIRED_HEADERS,
)

ASSETS_2026_DISCOVERY = TseResourceContract(
    source="TSE",
    dataset="bens_candidatos",
    election_year=2026,
    package_id="ba2d7d69-5bf5-4379-8c91-664c11f75a2e",
    resource_id="33fbda56-eb41-46f5-a8a0-8b499c285a1d",
    ckan_api_base_url="https://dadosabertos.tse.jus.br/api/3/action",
    artifact_name="bem_candidato_2026.zip",
    canonical_csv_name="bem_candidato_2026_BRASIL.csv",
    encoding="latin-1",
    delimiter=";",
    quotechar='"',
    source_timezone="America/Sao_Paulo",
    expected_mimetype="application/zip",
    expected_headers=None,
    fallback_download_url=(
        "https://cdn.tse.jus.br/estatistica/sead/odsele/bem_candidato/"
        "bem_candidato_2026.zip"
    ),
    discovery_required_headers=TSE_TABULAR_DISCOVERY_REQUIRED_HEADERS,
)

_SUPPORTED_ASSET_DISCOVERY_CONTRACTS = {
    2022: ASSETS_2022_DISCOVERY,
    2026: ASSETS_2026_DISCOVERY,
}
SUPPORTED_ASSET_DISCOVERY_YEARS = tuple(sorted(_SUPPORTED_ASSET_DISCOVERY_CONTRACTS))


def assets_discovery_contract_for_year(year: int) -> TseResourceContract:
    """Return the schema-open official assets contract for one supported election year."""

    try:
        return _SUPPORTED_ASSET_DISCOVERY_CONTRACTS[year]
    except KeyError as exc:
        raise ValueError(f"unsupported TSE assets discovery year: {year}") from exc


ASSETS_2022 = replace(
    ASSETS_2022_DISCOVERY,
    expected_headers=TSE_ASSETS_2022_HEADERS,
)

ASSETS_2026 = replace(
    ASSETS_2026_DISCOVERY,
    expected_headers=TSE_ASSETS_2026_HEADERS,
)

_SUPPORTED_ASSET_CONTRACTS = {
    2022: ASSETS_2022,
    2026: ASSETS_2026,
}
SUPPORTED_ASSET_YEARS = tuple(sorted(_SUPPORTED_ASSET_CONTRACTS))


def assets_contract_for_year(year: int) -> TseResourceContract:
    """Return the frozen official declared-assets contract for one supported year."""

    try:
        return _SUPPORTED_ASSET_CONTRACTS[year]
    except KeyError as exc:
        raise ValueError(f"unsupported TSE assets year: {year}") from exc

VOTES_2014_DISCOVERY = TseResourceContract(
    source="TSE",
    dataset="votacao_candidato_munzona",
    election_year=2014,
    package_id="05b7d86e-d784-4b9c-8ba5-4428d64e4ec2",
    resource_id="9df2487a-7d41-4e1f-8ca1-a9dbe43fdd02",
    ckan_api_base_url="https://dadosabertos.tse.jus.br/api/3/action",
    artifact_name="votacao_candidato_munzona_2014.zip",
    canonical_csv_name="votacao_candidato_munzona_2014_BRASIL.csv",
    encoding="latin-1",
    delimiter=";",
    quotechar='"',
    source_timezone="America/Sao_Paulo",
    expected_mimetype="application/zip",
    expected_headers=None,
    fallback_download_url=(
        "https://cdn.tse.jus.br/estatistica/sead/odsele/votacao_candidato_munzona/"
        "votacao_candidato_munzona_2014.zip"
    ),
    discovery_required_headers=TSE_VOTE_DISCOVERY_REQUIRED_HEADERS,
)

VOTES_2018_DISCOVERY = TseResourceContract(
    source="TSE",
    dataset="votacao_candidato_munzona",
    election_year=2018,
    package_id="76d7bbbb-14c6-4b9a-beec-9ed87c2ad8b6",
    resource_id="e1dae37e-c2d6-493c-bf66-437f3788af89",
    ckan_api_base_url="https://dadosabertos.tse.jus.br/api/3/action",
    artifact_name="votacao_candidato_munzona_2018.zip",
    canonical_csv_name="votacao_candidato_munzona_2018_BRASIL.csv",
    encoding="latin-1",
    delimiter=";",
    quotechar='"',
    source_timezone="America/Sao_Paulo",
    expected_mimetype="application/zip",
    expected_headers=None,
    fallback_download_url=(
        "https://cdn.tse.jus.br/estatistica/sead/odsele/votacao_candidato_munzona/"
        "votacao_candidato_munzona_2018.zip"
    ),
    discovery_required_headers=TSE_VOTE_DISCOVERY_REQUIRED_HEADERS,
)

VOTES_2022_DISCOVERY = TseResourceContract(
    source="TSE",
    dataset="votacao_candidato_munzona",
    election_year=2022,
    package_id="5db2c9ef-a63b-4c0c-a2ec-d08002f49897",
    resource_id="40fdcf49-256a-4c81-87cf-711545bd1528",
    ckan_api_base_url="https://dadosabertos.tse.jus.br/api/3/action",
    artifact_name="votacao_candidato_munzona_2022.zip",
    canonical_csv_name="votacao_candidato_munzona_2022_BRASIL.csv",
    encoding="latin-1",
    delimiter=";",
    quotechar='"',
    source_timezone="America/Sao_Paulo",
    expected_mimetype="application/zip",
    expected_headers=None,
    fallback_download_url=(
        "https://cdn.tse.jus.br/estatistica/sead/odsele/votacao_candidato_munzona/"
        "votacao_candidato_munzona_2022.zip"
    ),
    discovery_required_headers=TSE_VOTE_DISCOVERY_REQUIRED_HEADERS,
)

_SUPPORTED_VOTE_DISCOVERY_CONTRACTS = {
    2014: VOTES_2014_DISCOVERY,
    2018: VOTES_2018_DISCOVERY,
    2022: VOTES_2022_DISCOVERY,
}
SUPPORTED_VOTE_DISCOVERY_YEARS = tuple(sorted(_SUPPORTED_VOTE_DISCOVERY_CONTRACTS))


def votes_discovery_contract_for_year(year: int) -> TseResourceContract:
    """Return the schema-open official nominal-vote contract for one supported year."""

    try:
        return _SUPPORTED_VOTE_DISCOVERY_CONTRACTS[year]
    except KeyError as exc:
        raise ValueError(f"unsupported TSE votes discovery year: {year}") from exc


VOTES_2014 = replace(
    VOTES_2014_DISCOVERY,
    expected_headers=TSE_VOTES_2014_HEADERS,
)

VOTES_2018 = replace(
    VOTES_2018_DISCOVERY,
    expected_headers=TSE_VOTES_2018_HEADERS,
)

VOTES_2022 = replace(
    VOTES_2022_DISCOVERY,
    expected_headers=TSE_VOTES_2022_HEADERS,
)

_SUPPORTED_VOTE_CONTRACTS = {
    2014: VOTES_2014,
    2018: VOTES_2018,
    2022: VOTES_2022,
}
SUPPORTED_VOTE_YEARS = tuple(sorted(_SUPPORTED_VOTE_CONTRACTS))


def votes_contract_for_year(year: int) -> TseResourceContract:
    """Return the frozen official nominal-vote contract for one supported year."""

    try:
        return _SUPPORTED_VOTE_CONTRACTS[year]
    except KeyError as exc:
        raise ValueError(f"unsupported TSE votes year: {year}") from exc

