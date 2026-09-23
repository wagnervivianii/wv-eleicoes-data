import pytest

from wv_eleicoes_data.ingestion.tse.contracts import (
    ASSETS_2022,
    ASSETS_2022_DISCOVERY,
    ASSETS_2026,
    ASSETS_2026_DISCOVERY,
    CANDIDATES_2022,
    CANDIDATES_2022_DISCOVERY,
    CANDIDATES_2026,
    SUPPORTED_ASSET_DISCOVERY_YEARS,
    SUPPORTED_ASSET_YEARS,
    SUPPORTED_CANDIDATE_YEARS,
    SUPPORTED_VOTE_DISCOVERY_YEARS,
    SUPPORTED_VOTE_YEARS,
    TSE_ASSETS_2022_HEADERS,
    TSE_ASSETS_2026_HEADERS,
    TSE_CANDIDATES_2022_HEADERS,
    TSE_CANDIDATES_2026_HEADERS,
    TSE_NOMINAL_VOTE_GRAIN_HEADERS,
    TSE_VOTES_2014_HEADERS,
    TSE_VOTES_2018_HEADERS,
    TSE_VOTES_2022_HEADERS,
    VOTES_2014,
    VOTES_2014_DISCOVERY,
    VOTES_2018,
    VOTES_2018_DISCOVERY,
    VOTES_2022,
    VOTES_2022_DISCOVERY,
    assets_contract_for_year,
    assets_discovery_contract_for_year,
    candidates_contract_for_year,
    votes_contract_for_year,
    votes_discovery_contract_for_year,
)


def test_candidates_2026_contract_matches_observed_official_resource() -> None:
    assert CANDIDATES_2026.fallback_download_url == (
        "https://cdn.tse.jus.br/estatistica/sead/odsele/consulta_cand/consulta_cand_2026.zip"
    )
    assert CANDIDATES_2026.source == "TSE"
    assert CANDIDATES_2026.dataset == "candidatos"
    assert CANDIDATES_2026.election_year == 2026
    assert CANDIDATES_2026.resource_id == "7748de82-a23b-47c4-9ec1-35535d945e5b"
    assert CANDIDATES_2026.package_id == "ba2d7d69-5bf5-4379-8c91-664c11f75a2e"
    assert CANDIDATES_2026.artifact_name == "consulta_cand_2026.zip"
    assert CANDIDATES_2026.canonical_csv_name == "consulta_cand_2026_BRASIL.csv"
    assert CANDIDATES_2026.encoding == "latin-1"
    assert CANDIDATES_2026.delimiter == ";"
    assert CANDIDATES_2026.expected_mimetype == "application/zip"
    assert CANDIDATES_2026.scope_key == "election-year:2026"


def test_candidates_2026_contract_has_exactly_50_unique_headers() -> None:
    assert len(TSE_CANDIDATES_2026_HEADERS) == 50
    assert len(set(TSE_CANDIDATES_2026_HEADERS)) == 50
    assert TSE_CANDIDATES_2026_HEADERS[0:3] == (
        "DT_GERACAO",
        "HH_GERACAO",
        "ANO_ELEICAO",
    )
    assert TSE_CANDIDATES_2026_HEADERS[-2:] == (
        "CD_SIT_TOT_TURNO",
        "DS_SIT_TOT_TURNO",
    )


def test_candidates_2022_contract_is_frozen_from_official_probe() -> None:
    assert CANDIDATES_2022.source == "TSE"
    assert CANDIDATES_2022.dataset == "candidatos"
    assert CANDIDATES_2022.election_year == 2022
    assert CANDIDATES_2022.resource_id == "435145fd-bc9d-446a-ac9d-273f585a0bb9"
    assert CANDIDATES_2022.package_id == "8747bd50-e1f7-407a-8e24-2707126ccde6"
    assert CANDIDATES_2022.artifact_name == "consulta_cand_2022.zip"
    assert CANDIDATES_2022.canonical_csv_name == "consulta_cand_2022_BRASIL.csv"
    assert CANDIDATES_2022.expected_headers == TSE_CANDIDATES_2022_HEADERS
    assert TSE_CANDIDATES_2022_HEADERS == TSE_CANDIDATES_2026_HEADERS
    assert CANDIDATES_2022.scope_key == "election-year:2022"
    assert CANDIDATES_2022.is_schema_discovery is False


def test_candidates_2022_discovery_contract_remains_schema_open() -> None:
    assert CANDIDATES_2022_DISCOVERY.resource_id == CANDIDATES_2022.resource_id
    assert CANDIDATES_2022_DISCOVERY.package_id == CANDIDATES_2022.package_id
    assert CANDIDATES_2022_DISCOVERY.expected_headers is None
    assert CANDIDATES_2022_DISCOVERY.is_schema_discovery is True
    assert CANDIDATES_2022_DISCOVERY.fallback_download_url == (
        "https://cdn.tse.jus.br/estatistica/sead/odsele/consulta_cand/consulta_cand_2022.zip"
    )


def test_supported_candidate_year_contract_lookup_is_explicit() -> None:
    assert SUPPORTED_CANDIDATE_YEARS == (2022, 2026)
    assert candidates_contract_for_year(2022) is CANDIDATES_2022
    assert candidates_contract_for_year(2026) is CANDIDATES_2026
    with pytest.raises(ValueError, match="unsupported TSE candidates year"):
        candidates_contract_for_year(2018)


def test_assets_discovery_contracts_match_official_resource_metadata() -> None:
    assert SUPPORTED_ASSET_DISCOVERY_YEARS == (2022, 2026)
    assert ASSETS_2022_DISCOVERY.package_id == "8747bd50-e1f7-407a-8e24-2707126ccde6"
    assert ASSETS_2022_DISCOVERY.resource_id == "fac824ef-8519-4c75-b634-378e6fcc717f"
    assert ASSETS_2026_DISCOVERY.package_id == "ba2d7d69-5bf5-4379-8c91-664c11f75a2e"
    assert ASSETS_2026_DISCOVERY.resource_id == "33fbda56-eb41-46f5-a8a0-8b499c285a1d"
    assert ASSETS_2022_DISCOVERY.canonical_csv_name == "bem_candidato_2022_BRASIL.csv"
    assert ASSETS_2026_DISCOVERY.canonical_csv_name == "bem_candidato_2026_BRASIL.csv"
    assert ASSETS_2022_DISCOVERY.expected_headers is None
    assert ASSETS_2026_DISCOVERY.expected_headers is None
    assert ASSETS_2022_DISCOVERY.is_schema_discovery is True
    assert ASSETS_2026_DISCOVERY.is_schema_discovery is True
    assert assets_discovery_contract_for_year(2022) is ASSETS_2022_DISCOVERY
    assert assets_discovery_contract_for_year(2026) is ASSETS_2026_DISCOVERY
    with pytest.raises(ValueError, match="unsupported TSE assets discovery year"):
        assets_discovery_contract_for_year(2018)


def test_assets_probe_uses_only_generic_structural_headers_before_freezing_schema() -> None:
    expected = ("DT_GERACAO", "HH_GERACAO", "ANO_ELEICAO")
    assert ASSETS_2022_DISCOVERY.discovery_required_headers == expected
    assert ASSETS_2026_DISCOVERY.discovery_required_headers == expected


def test_assets_frozen_contracts_match_observed_two_year_layout() -> None:
    assert SUPPORTED_ASSET_YEARS == (2022, 2026)
    assert len(TSE_ASSETS_2022_HEADERS) == 19
    assert len(set(TSE_ASSETS_2022_HEADERS)) == 19
    assert TSE_ASSETS_2022_HEADERS == TSE_ASSETS_2026_HEADERS
    assert TSE_ASSETS_2022_HEADERS[-7:] == (
        "NR_ORDEM_BEM_CANDIDATO",
        "CD_TIPO_BEM_CANDIDATO",
        "DS_TIPO_BEM_CANDIDATO",
        "DS_BEM_CANDIDATO",
        "VR_BEM_CANDIDATO",
        "DT_ULT_ATUAL_BEM_CANDIDATO",
        "HH_ULT_ATUAL_BEM_CANDIDATO",
    )
    assert ASSETS_2022.expected_headers == TSE_ASSETS_2022_HEADERS
    assert ASSETS_2026.expected_headers == TSE_ASSETS_2026_HEADERS
    assert ASSETS_2022.is_schema_discovery is False
    assert ASSETS_2026.is_schema_discovery is False
    assert assets_contract_for_year(2022) is ASSETS_2022
    assert assets_contract_for_year(2026) is ASSETS_2026
    with pytest.raises(ValueError, match="unsupported TSE assets year"):
        assets_contract_for_year(2018)


def test_assets_discovery_contracts_remain_open_after_freezing() -> None:
    assert ASSETS_2022_DISCOVERY.expected_headers is None
    assert ASSETS_2026_DISCOVERY.expected_headers is None
    assert ASSETS_2022.resource_id == ASSETS_2022_DISCOVERY.resource_id
    assert ASSETS_2026.resource_id == ASSETS_2026_DISCOVERY.resource_id

def test_vote_discovery_contracts_match_official_resource_metadata() -> None:
    assert SUPPORTED_VOTE_DISCOVERY_YEARS == (2014, 2018, 2022)

    assert VOTES_2014_DISCOVERY.package_id == "05b7d86e-d784-4b9c-8ba5-4428d64e4ec2"
    assert VOTES_2014_DISCOVERY.resource_id == "9df2487a-7d41-4e1f-8ca1-a9dbe43fdd02"
    assert VOTES_2018_DISCOVERY.package_id == "76d7bbbb-14c6-4b9a-beec-9ed87c2ad8b6"
    assert VOTES_2018_DISCOVERY.resource_id == "e1dae37e-c2d6-493c-bf66-437f3788af89"
    assert VOTES_2022_DISCOVERY.package_id == "5db2c9ef-a63b-4c0c-a2ec-d08002f49897"
    assert VOTES_2022_DISCOVERY.resource_id == "40fdcf49-256a-4c81-87cf-711545bd1528"

    assert VOTES_2014_DISCOVERY.canonical_csv_name == (
        "votacao_candidato_munzona_2014_BRASIL.csv"
    )
    assert VOTES_2018_DISCOVERY.canonical_csv_name == (
        "votacao_candidato_munzona_2018_BRASIL.csv"
    )
    assert VOTES_2022_DISCOVERY.canonical_csv_name == (
        "votacao_candidato_munzona_2022_BRASIL.csv"
    )

    for contract in (
        VOTES_2014_DISCOVERY,
        VOTES_2018_DISCOVERY,
        VOTES_2022_DISCOVERY,
    ):
        assert contract.source == "TSE"
        assert contract.dataset == "votacao_candidato_munzona"
        assert contract.expected_mimetype == "application/zip"
        assert contract.expected_headers is None
        assert contract.is_schema_discovery is True
        assert contract.fallback_download_url is not None

    assert votes_discovery_contract_for_year(2014) is VOTES_2014_DISCOVERY
    assert votes_discovery_contract_for_year(2018) is VOTES_2018_DISCOVERY
    assert votes_discovery_contract_for_year(2022) is VOTES_2022_DISCOVERY

    with pytest.raises(ValueError, match="unsupported TSE votes discovery year"):
        votes_discovery_contract_for_year(2026)


def test_vote_discovery_requires_the_stable_cross_year_grain_headers() -> None:
    expected = (
        "DT_GERACAO",
        "HH_GERACAO",
        "ANO_ELEICAO",
        "CD_ELEICAO",
        "NR_TURNO",
        "SG_UF",
        "CD_MUNICIPIO",
        "NR_ZONA",
        "SQ_CANDIDATO",
        "ST_VOTO_EM_TRANSITO",
        "QT_VOTOS_NOMINAIS",
    )

    assert VOTES_2014_DISCOVERY.discovery_required_headers == expected
    assert VOTES_2018_DISCOVERY.discovery_required_headers == expected
    assert VOTES_2022_DISCOVERY.discovery_required_headers == expected


def test_vote_frozen_contracts_preserve_observed_historical_layouts() -> None:
    assert SUPPORTED_VOTE_YEARS == (2014, 2018, 2022)

    assert len(TSE_VOTES_2014_HEADERS) == 38
    assert len(set(TSE_VOTES_2014_HEADERS)) == 38

    assert len(TSE_VOTES_2018_HEADERS) == 50
    assert len(set(TSE_VOTES_2018_HEADERS)) == 50

    assert len(TSE_VOTES_2022_HEADERS) == 50
    assert len(set(TSE_VOTES_2022_HEADERS)) == 50

    assert TSE_VOTES_2018_HEADERS[:31] == TSE_VOTES_2022_HEADERS[:31]
    assert TSE_VOTES_2018_HEADERS[31:33] == (
        "CD_SITUACAO_DIPLOMA",
        "DS_SITUACAO_DIPLOMA",
    )
    assert TSE_VOTES_2022_HEADERS[31:33] == (
        "CD_SITUACAO_DCONST_DIPLOMA",
        "DS_SITUACAO_DCONST_DIPLOMA",
    )
    assert TSE_VOTES_2018_HEADERS[33:] == TSE_VOTES_2022_HEADERS[33:]

    assert VOTES_2014.expected_headers == TSE_VOTES_2014_HEADERS
    assert VOTES_2018.expected_headers == TSE_VOTES_2018_HEADERS
    assert VOTES_2022.expected_headers == TSE_VOTES_2022_HEADERS

    assert votes_contract_for_year(2014) is VOTES_2014
    assert votes_contract_for_year(2018) is VOTES_2018
    assert votes_contract_for_year(2022) is VOTES_2022

    with pytest.raises(ValueError, match="unsupported TSE votes year"):
        votes_contract_for_year(2026)


def test_nominal_vote_grain_is_available_in_every_supported_layout() -> None:
    assert TSE_NOMINAL_VOTE_GRAIN_HEADERS == (
        "ANO_ELEICAO",
        "CD_ELEICAO",
        "NR_TURNO",
        "SG_UF",
        "CD_MUNICIPIO",
        "NR_ZONA",
        "SQ_CANDIDATO",
        "ST_VOTO_EM_TRANSITO",
    )

    for headers in (
        TSE_VOTES_2014_HEADERS,
        TSE_VOTES_2018_HEADERS,
        TSE_VOTES_2022_HEADERS,
    ):
        assert all(field in headers for field in TSE_NOMINAL_VOTE_GRAIN_HEADERS)


def test_vote_fallback_urls_are_pinned_to_the_official_tse_cdn() -> None:
    assert VOTES_2014_DISCOVERY.fallback_download_url == (
        "https://cdn.tse.jus.br/estatistica/sead/odsele/votacao_candidato_munzona/"
        "votacao_candidato_munzona_2014.zip"
    )
    assert VOTES_2018_DISCOVERY.fallback_download_url == (
        "https://cdn.tse.jus.br/estatistica/sead/odsele/votacao_candidato_munzona/"
        "votacao_candidato_munzona_2018.zip"
    )
    assert VOTES_2022_DISCOVERY.fallback_download_url == (
        "https://cdn.tse.jus.br/estatistica/sead/odsele/votacao_candidato_munzona/"
        "votacao_candidato_munzona_2022.zip"
    )

