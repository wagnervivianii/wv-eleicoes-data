from wv_eleicoes_data.ingestion.tse.contracts import (
    CANDIDATES_2026,
    TSE_CANDIDATES_2026_HEADERS,
)


def test_candidates_2026_contract_matches_observed_official_resource() -> None:
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
