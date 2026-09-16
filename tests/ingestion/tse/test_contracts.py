import pytest

from wv_eleicoes_data.ingestion.tse.contracts import (
    ASSETS_2022_DISCOVERY,
    ASSETS_2026_DISCOVERY,
    CANDIDATES_2022,
    CANDIDATES_2022_DISCOVERY,
    CANDIDATES_2026,
    SUPPORTED_ASSET_DISCOVERY_YEARS,
    SUPPORTED_CANDIDATE_YEARS,
    TSE_CANDIDATES_2022_HEADERS,
    TSE_CANDIDATES_2026_HEADERS,
    assets_discovery_contract_for_year,
    candidates_contract_for_year,
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
