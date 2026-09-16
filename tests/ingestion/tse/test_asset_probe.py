import csv
import io
from dataclasses import replace
from datetime import datetime
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile
from zoneinfo import ZoneInfo

from wv_eleicoes_data.ingestion.tse.asset_probe import (
    TseAssetsProbeBundle,
    TseAssetsYearProbeReport,
    _safe_asset_aggregates,
    render_assets_probe_bundle,
)
from wv_eleicoes_data.ingestion.tse.connector import (
    TseArtifact,
    TseCandidatesConnector,
    TseResourceMetadata,
)
from wv_eleicoes_data.ingestion.tse.contracts import ASSETS_2022_DISCOVERY


def _asset_zip(headers: tuple[str, ...], rows: list[list[str]]) -> bytes:
    text_buffer = io.StringIO(newline="")
    writer = csv.writer(
        text_buffer,
        delimiter=ASSETS_2022_DISCOVERY.delimiter,
        quotechar=ASSETS_2022_DISCOVERY.quotechar,
        lineterminator="\r\n",
    )
    writer.writerow(headers)
    writer.writerows(rows)

    zip_buffer = io.BytesIO()
    with ZipFile(zip_buffer, "w", compression=ZIP_DEFLATED) as archive:
        archive.writestr(
            ASSETS_2022_DISCOVERY.canonical_csv_name,
            text_buffer.getvalue().encode(ASSETS_2022_DISCOVERY.encoding),
        )
    return zip_buffer.getvalue()


def _resource() -> TseResourceMetadata:
    return TseResourceMetadata(
        resource_id=ASSETS_2022_DISCOVERY.resource_id,
        package_id=ASSETS_2022_DISCOVERY.package_id,
        name="Bens de candidatos",
        download_url="https://example.invalid/bem_candidato_2022.zip",
        mimetype=ASSETS_2022_DISCOVERY.expected_mimetype,
    )


def test_assets_discovery_accepts_schema_before_candidate_linkage_is_known(tmp_path: Path) -> None:
    headers = ("ANO_ELEICAO", "DT_GERACAO", "HH_GERACAO", "CAMPO_DESCONHECIDO")
    row = ["2022", "02/10/2022", "08:30:00", "valor"]
    path = tmp_path / ASSETS_2022_DISCOVERY.artifact_name
    path.write_bytes(_asset_zip(headers, [row]))

    artifact = TseCandidatesConnector(ASSETS_2022_DISCOVERY).inspect_artifact(path, _resource())

    assert artifact.headers == headers
    assert artifact.row_count == 1
    assert artifact.source_updated_at.isoformat() == "2022-10-02T08:30:00-03:00"


def test_safe_asset_aggregates_prove_one_to_many_without_emitting_identifiers(
    tmp_path: Path,
) -> None:
    headers = ("DT_GERACAO", "HH_GERACAO", "ANO_ELEICAO", "SQ_CANDIDATO", "VR_BEM_CANDIDATO")
    rows = [
        ["02/10/2022", "08:30:00", "2022", "100", "10,00"],
        ["02/10/2022", "08:30:00", "2022", "100", "20,00"],
        ["02/10/2022", "08:30:00", "2022", "200", "30,00"],
        ["02/10/2022", "08:30:00", "2022", "", "40,00"],
    ]
    path = tmp_path / ASSETS_2022_DISCOVERY.artifact_name
    path.write_bytes(_asset_zip(headers, rows))
    artifact = TseArtifact(
        path=path,
        sha256="a" * 64,
        size_bytes=path.stat().st_size,
        canonical_csv_name=ASSETS_2022_DISCOVERY.canonical_csv_name,
        row_count=len(rows),
        headers=headers,
        source_updated_at=datetime(2022, 10, 2, 8, 30, tzinfo=ZoneInfo("America/Sao_Paulo")),
        resource=_resource(),
    )

    assert _safe_asset_aggregates(artifact, ASSETS_2022_DISCOVERY) == (2, 1, 2, 1)


def test_render_assets_probe_bundle_is_deterministic_and_non_sensitive() -> None:
    report_2022 = TseAssetsYearProbeReport(
        source="TSE",
        dataset="bens_candidatos",
        election_year=2022,
        package_id="package-2022",
        resource_id="resource-2022",
        download_url="https://example.invalid/2022.zip",
        artifact_name="bem_candidato_2022.zip",
        canonical_csv_name="bem_candidato_2022_BRASIL.csv",
        sha256="a" * 64,
        size_bytes=100,
        row_count=4,
        column_count=5,
        headers=("DT_GERACAO", "HH_GERACAO", "ANO_ELEICAO", "SQ_CANDIDATO", "VR_BEM_CANDIDATO"),
        source_updated_at="2022-10-02T08:30:00-03:00",
        candidate_sequence_header_present=True,
        election_code_header_present=False,
        asset_type_code_header_present=False,
        asset_type_name_header_present=False,
        asset_description_header_present=False,
        asset_value_header_present=True,
        distinct_candidate_sequences=2,
        candidate_sequences_with_multiple_assets=1,
        max_assets_per_candidate=2,
        blank_candidate_sequence_rows=0,
    )
    report_2026 = replace(
        report_2022,
        election_year=2026,
        package_id="package-2026",
        resource_id="resource-2026",
        artifact_name="bem_candidato_2026.zip",
        canonical_csv_name="bem_candidato_2026_BRASIL.csv",
        source_updated_at="2026-09-15T08:30:00-03:00",
    )
    bundle = TseAssetsProbeBundle(
        reports=(report_2022, report_2026),
        same_ordered_layout=True,
        common_headers=report_2022.headers,
        only_2022_headers=(),
        only_2026_headers=(),
    )

    rendered = render_assets_probe_bundle(bundle)

    assert rendered.endswith("\n")
    assert '"same_ordered_layout": true' in rendered
    assert '"distinct_candidate_sequences": 2' in rendered
    assert "candidate-100" not in rendered
