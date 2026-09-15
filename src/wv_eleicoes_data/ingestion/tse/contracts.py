from dataclasses import dataclass

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

TSE_CANDIDATE_DISCOVERY_REQUIRED_HEADERS = (
    "DT_GERACAO",
    "HH_GERACAO",
    "ANO_ELEICAO",
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

    @property
    def resource_show_url(self) -> str:
        """Return the CKAN endpoint used to discover the current download URL."""

        return f"{self.ckan_api_base_url}/resource_show"

    @property
    def is_schema_discovery(self) -> bool:
        """Return whether this contract discovers instead of freezing the CSV schema."""

        return self.expected_headers is None


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

CANDIDATES_2022_DISCOVERY = TseResourceContract(
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
    expected_headers=None,
    fallback_download_url=(
        "https://cdn.tse.jus.br/estatistica/sead/odsele/consulta_cand/consulta_cand_2022.zip"
    ),
)
