import csv
import hashlib
import io
from dataclasses import replace
from datetime import timedelta
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

import httpx
import pytest

from wv_eleicoes_data.ingestion.tse.connector import (
    TseCandidatesConnector,
    TseIngestionError,
    TseResourceMetadata,
    TseRetryableHttpError,
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


@pytest.mark.parametrize("invalid_artifact", [False, True])
def test_fetch_uses_pinned_fallback_only_on_discovery_403(
    tmp_path: Path, invalid_artifact: bool
) -> None:
    content = (
        _build_zip([_candidate_row()], header=("INVALID",))
        if invalid_artifact
        else _build_zip([_candidate_row()])
    )
    urls: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        urls.append(str(request.url))
        if request.url.path.endswith("/resource_show"):
            return httpx.Response(403, json={"result": {"name": "untrusted"}})
        assert str(request.url) == CANDIDATES_2026.fallback_download_url
        return httpx.Response(200, content=content)

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        connector = TseCandidatesConnector(client=client)
        if invalid_artifact:
            with pytest.raises(TseIngestionError, match="header differs"):
                connector.fetch(tmp_path)
            assert not (tmp_path / CANDIDATES_2026.artifact_name).exists()
        else:
            artifact = connector.fetch(tmp_path)
            assert artifact.resource == TseResourceMetadata(
                resource_id=CANDIDATES_2026.resource_id,
                package_id=CANDIDATES_2026.package_id,
                name=CANDIDATES_2026.artifact_name,
                download_url=str(CANDIDATES_2026.fallback_download_url),
                mimetype=CANDIDATES_2026.expected_mimetype,
            )
            assert artifact.row_count == 1
            assert artifact.sha256 == hashlib.sha256(content).hexdigest()
            assert artifact.source_updated_at.isoformat() == "2026-09-11T12:30:43-03:00"
    assert len(urls) == 2


@pytest.mark.parametrize("status,has_fallback", [(403, False), (401, True), (404, True)])
def test_discovery_http_errors_fail_closed(status: int, has_fallback: bool) -> None:
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(status)

    contract = (
        CANDIDATES_2026 if has_fallback else replace(CANDIDATES_2026, fallback_download_url=None)
    )
    with (
        httpx.Client(transport=httpx.MockTransport(handler)) as client,
        pytest.raises(httpx.HTTPStatusError) as error,
    ):
        TseCandidatesConnector(contract, client=client).discover_resource()
    assert error.value.response.status_code == status
    assert len(requests) == 1


@pytest.mark.parametrize(
    "defect", ["json", "success", "result", "id", "package_id", "mimetype", "url"]
)
def test_invalid_ckan_success_never_falls_back(defect: str, tmp_path: Path) -> None:
    requests: list[httpx.Request] = []
    result = {
        "id": CANDIDATES_2026.resource_id,
        "package_id": CANDIDATES_2026.package_id,
        "mimetype": CANDIDATES_2026.expected_mimetype,
        "name": "Candidatos",
        "url": "https://example.invalid/candidates.zip",
    }
    payload: dict[str, object] = {"success": True, "result": result}
    if defect == "success":
        payload["success"] = False
    elif defect == "result":
        del payload["result"]
    elif defect in result:
        result[defect] = "" if defect == "url" else "mismatch"

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        if defect == "json":
            return httpx.Response(200, content=b"not JSON")
        return httpx.Response(200, json=payload)

    with (
        httpx.Client(transport=httpx.MockTransport(handler)) as client,
        pytest.raises(TseIngestionError),
    ):
        TseCandidatesConnector(client=client).fetch(tmp_path)
    assert len(requests) == 1
    assert not list(tmp_path.iterdir())


@pytest.mark.parametrize("failure", [429, 503, "transport"])
def test_discovery_retries_exhaust_without_fallback(
    failure: int | str, monkeypatch: pytest.MonkeyPatch
) -> None:
    from tenacity import wait_none

    monkeypatch.setattr(TseCandidatesConnector._request_resource_show.retry, "wait", wait_none())
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        assert request.url.path.endswith("/resource_show")
        if isinstance(failure, str):
            raise httpx.ConnectError("unavailable", request=request)
        return httpx.Response(failure)

    expected = httpx.ConnectError if failure == "transport" else TseRetryableHttpError
    with (
        httpx.Client(transport=httpx.MockTransport(handler)) as client,
        pytest.raises(expected),
    ):
        TseCandidatesConnector(client=client).discover_resource()
    assert len(requests) == 4
