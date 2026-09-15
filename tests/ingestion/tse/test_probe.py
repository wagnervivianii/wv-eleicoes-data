from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from wv_eleicoes_data.ingestion.tse.connector import TseArtifact, TseResourceMetadata
from wv_eleicoes_data.ingestion.tse.contracts import CANDIDATES_2022_DISCOVERY
from wv_eleicoes_data.ingestion.tse.probe import (
    TseCandidatesProbeReport,
    render_probe_report,
)


def test_render_probe_report_is_deterministic_and_contains_no_row_values() -> None:
    report = TseCandidatesProbeReport(
        source="TSE",
        dataset="candidatos",
        election_year=2022,
        package_id=CANDIDATES_2022_DISCOVERY.package_id,
        resource_id=CANDIDATES_2022_DISCOVERY.resource_id,
        download_url=str(CANDIDATES_2022_DISCOVERY.fallback_download_url),
        artifact_name=CANDIDATES_2022_DISCOVERY.artifact_name,
        canonical_csv_name=CANDIDATES_2022_DISCOVERY.canonical_csv_name,
        sha256="a" * 64,
        size_bytes=123,
        row_count=2,
        column_count=6,
        headers=(
            "DT_GERACAO",
            "HH_GERACAO",
            "ANO_ELEICAO",
            "CD_ELEICAO",
            "SQ_CANDIDATO",
            "CAMPO_HISTORICO",
        ),
        source_updated_at="2022-10-02T08:30:00-03:00",
        same_layout_as_2026=False,
        missing_vs_2026=("NR_CANDIDATO",),
        extra_vs_2026=("CAMPO_HISTORICO",),
        identity_relevant_headers_present=("SQ_CANDIDATO",),
    )

    rendered = render_probe_report(report)

    assert rendered.endswith("\n")
    assert '"election_year": 2022' in rendered
    assert '"CAMPO_HISTORICO"' in rendered
    assert "candidate row value" not in rendered


def test_artifact_type_carries_observed_headers() -> None:
    headers = ("DT_GERACAO", "HH_GERACAO", "ANO_ELEICAO", "CD_ELEICAO", "SQ_CANDIDATO")
    artifact = TseArtifact(
        path=Path("consulta_cand_2022.zip"),
        sha256="b" * 64,
        size_bytes=10,
        canonical_csv_name="consulta_cand_2022_BRASIL.csv",
        row_count=1,
        headers=headers,
        source_updated_at=datetime(2022, 10, 2, 8, 30, tzinfo=ZoneInfo("America/Sao_Paulo")),
        resource=TseResourceMetadata(
            resource_id=CANDIDATES_2022_DISCOVERY.resource_id,
            package_id=CANDIDATES_2022_DISCOVERY.package_id,
            name="Candidatos",
            download_url="https://example.invalid/file.zip",
            mimetype="application/zip",
        ),
    )

    assert artifact.headers == headers
