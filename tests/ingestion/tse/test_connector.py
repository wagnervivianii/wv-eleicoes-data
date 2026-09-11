import csv
import hashlib
import io
from datetime import timedelta
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

import httpx
import pytest

from wv_eleicoes_data.ingestion.tse.connector import (
    TseCandidatesConnector,
    TseIngestionError,
    TseResourceMetadata,
)
from wv_eleicoes_data.ingestion.tse.contracts import CANDIDATES_2026


def _candidate_row(
    *,
    generation_date: str = "11/09/2026",
    generation_time: str = "12:30:43",
) -> list[str]:
    row = [""] * len(CANDIDATES_2026.expected_headers)
    row[0] = generation_date
    row[1] = generation_time
    row[2] = "2026"
    row[10] = "SP"
    row[15] = "250000000001"
    row[17] = "CANDIDATO TESTE"
    return row


def _build_zip(rows: list[list[str]], *, header: tuple[str, ...] | None = None) -> bytes:
    text_buffer = io.StringIO(newline="")
    writer = csv.writer(
        text_buffer,
        delimiter=CANDIDATES_2026.delimiter,
        quotechar=CANDIDATES_2026.quotechar,
        lineterminator="\r\n",
    )
    writer.writerow(header or CANDIDATES_2026.expected_headers)
    writer.writerows(rows)

    zip_buffer = io.BytesIO()
    with ZipFile(zip_buffer, "w", compression=ZIP_DEFLATED) as archive:
        archive.writestr(
            CANDIDATES_2026.canonical_csv_name,
            text_buffer.getvalue().encode(CANDIDATES_2026.encoding),
        )
        archive.writestr("consulta_cand_2026_SP.csv", b"qa-only")

    return zip_buffer.getvalue()


def _resource() -> TseResourceMetadata:
    return TseResourceMetadata(
        resource_id=CANDIDATES_2026.resource_id,
        package_id=CANDIDATES_2026.package_id,
        name="Candidatos",
        download_url="https://example.invalid/consulta_cand_2026.zip",
        mimetype=CANDIDATES_2026.expected_mimetype,
    )


def test_inspect_artifact_returns_checksum_rows_and_source_timestamp(tmp_path: Path) -> None:
    zip_bytes = _build_zip([_candidate_row(), _candidate_row()])
    artifact_path = tmp_path / CANDIDATES_2026.artifact_name
    artifact_path.write_bytes(zip_bytes)

    artifact = TseCandidatesConnector().inspect_artifact(artifact_path, _resource())

    assert artifact.sha256 == hashlib.sha256(zip_bytes).hexdigest()
    assert artifact.size_bytes == len(zip_bytes)
    assert artifact.row_count == 2
    assert artifact.canonical_csv_name == CANDIDATES_2026.canonical_csv_name
    assert artifact.source_updated_at.isoformat() == "2026-09-11T12:30:43-03:00"
    assert artifact.source_updated_at.utcoffset() == timedelta(hours=-3)


def test_inspect_artifact_rejects_header_drift(tmp_path: Path) -> None:
    bad_header = list(CANDIDATES_2026.expected_headers)
    bad_header[0] = "CAMPO_DESCONHECIDO"
    artifact_path = tmp_path / CANDIDATES_2026.artifact_name
    artifact_path.write_bytes(_build_zip([_candidate_row()], header=tuple(bad_header)))

    with pytest.raises(TseIngestionError, match="header differs"):
        TseCandidatesConnector().inspect_artifact(artifact_path, _resource())


def test_inspect_artifact_rejects_multiple_generation_timestamps(tmp_path: Path) -> None:
    artifact_path = tmp_path / CANDIDATES_2026.artifact_name
    artifact_path.write_bytes(
        _build_zip(
            [
                _candidate_row(),
                _candidate_row(generation_time="13:30:43"),
            ]
        )
    )

    with pytest.raises(TseIngestionError, match="multiple DT_GERACAO"):
        TseCandidatesConnector().inspect_artifact(artifact_path, _resource())


def test_fetch_discovers_downloads_and_validates_artifact(tmp_path: Path) -> None:
    zip_bytes = _build_zip([_candidate_row()])
    download_url = "https://download.example/consulta_cand_2026.zip"

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/resource_show"):
            assert request.url.params["id"] == CANDIDATES_2026.resource_id
            return httpx.Response(
                200,
                json={
                    "success": True,
                    "result": {
                        "id": CANDIDATES_2026.resource_id,
                        "package_id": CANDIDATES_2026.package_id,
                        "name": "Candidatos",
                        "url": download_url,
                        "mimetype": CANDIDATES_2026.expected_mimetype,
                    },
                },
            )

        if str(request.url) == download_url:
            return httpx.Response(200, content=zip_bytes)

        return httpx.Response(404)

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        artifact = TseCandidatesConnector(client=client).fetch(tmp_path)

    assert artifact.path == tmp_path / CANDIDATES_2026.artifact_name
    assert artifact.path.read_bytes() == zip_bytes
    assert artifact.row_count == 1


def test_inspect_artifact_rejects_non_zip(tmp_path: Path) -> None:
    artifact_path = tmp_path / CANDIDATES_2026.artifact_name
    artifact_path.write_text("not a zip", encoding="utf-8")

    with pytest.raises(TseIngestionError, match="not a valid ZIP"):
        TseCandidatesConnector().inspect_artifact(artifact_path, _resource())
