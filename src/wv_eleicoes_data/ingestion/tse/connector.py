from __future__ import annotations

import csv
import hashlib
import json
from dataclasses import dataclass
from datetime import datetime
from io import TextIOWrapper
from pathlib import Path, PurePosixPath
from tempfile import NamedTemporaryFile
from typing import Any
from zipfile import BadZipFile, ZipFile, is_zipfile
from zoneinfo import ZoneInfo

import httpx
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from wv_eleicoes_data.ingestion.tse.contracts import CANDIDATES_2026, TseResourceContract


class TseIngestionError(RuntimeError):
    """Base exception for TSE ingestion contract violations."""


class TseRetryableHttpError(TseIngestionError):
    """Temporary HTTP failure that may succeed on a later attempt."""


@dataclass(frozen=True, slots=True)
class TseResourceMetadata:
    """Metadata returned by the TSE CKAN resource API."""

    resource_id: str
    package_id: str
    name: str
    download_url: str
    mimetype: str


@dataclass(frozen=True, slots=True)
class TseArtifact:
    """Validated local snapshot of the canonical TSE candidates resource."""

    path: Path
    sha256: str
    size_bytes: int
    canonical_csv_name: str
    row_count: int
    source_updated_at: datetime
    resource: TseResourceMetadata


class TseCandidatesConnector:
    """Download and validate the official TSE candidates artifact."""

    def __init__(
        self,
        contract: TseResourceContract = CANDIDATES_2026,
        *,
        client: httpx.Client | None = None,
        timeout: httpx.Timeout | None = None,
    ) -> None:
        self.contract = contract
        self._client = client
        self._timeout = timeout or httpx.Timeout(
            connect=10.0,
            read=120.0,
            write=30.0,
            pool=10.0,
        )

    def fetch(self, destination_dir: Path) -> TseArtifact:
        """Discover, download and validate the current official artifact."""

        destination_dir.mkdir(parents=True, exist_ok=True)
        resource = self.discover_resource()
        destination = destination_dir / self.contract.artifact_name

        self._download(resource.download_url, destination)

        try:
            return self.inspect_artifact(destination, resource)
        except Exception:
            destination.unlink(missing_ok=True)
            raise

    def discover_resource(self) -> TseResourceMetadata:
        """Resolve the current resource URL through the official CKAN API."""

        response = self._request_resource_show()

        try:
            payload = response.json()
        except json.JSONDecodeError as exc:
            raise TseIngestionError("TSE CKAN response is not valid JSON") from exc

        if not isinstance(payload, dict) or payload.get("success") is not True:
            raise TseIngestionError("TSE CKAN resource_show did not report success")

        result = payload.get("result")
        if not isinstance(result, dict):
            raise TseIngestionError("TSE CKAN response is missing result metadata")

        resource_id = self._required_string(result, "id")
        package_id = self._required_string(result, "package_id")
        download_url = self._required_string(result, "url")
        name = self._required_string(result, "name")
        mimetype = self._required_string(result, "mimetype")

        if resource_id != self.contract.resource_id:
            raise TseIngestionError("TSE resource id differs from the configured contract")

        if package_id != self.contract.package_id:
            raise TseIngestionError("TSE package id differs from the configured contract")

        if mimetype != self.contract.expected_mimetype:
            raise TseIngestionError(
                f"unexpected TSE mimetype: {mimetype!r}; "
                f"expected {self.contract.expected_mimetype!r}"
            )

        return TseResourceMetadata(
            resource_id=resource_id,
            package_id=package_id,
            name=name,
            download_url=download_url,
            mimetype=mimetype,
        )

    def inspect_artifact(self, path: Path, resource: TseResourceMetadata) -> TseArtifact:
        """Validate ZIP structure, CSV contract, checksum and source timestamp."""

        if not path.is_file():
            raise TseIngestionError(f"TSE artifact does not exist: {path}")

        if not is_zipfile(path):
            raise TseIngestionError("downloaded TSE artifact is not a valid ZIP")

        sha256 = self._sha256(path)

        try:
            with ZipFile(path) as archive:
                self._validate_archive_paths(archive)
                if archive.namelist().count(self.contract.canonical_csv_name) != 1:
                    raise TseIngestionError("canonical TSE CSV must occur exactly once")
                row_count, source_updated_at = self._inspect_canonical_csv(archive)
        except BadZipFile as exc:
            raise TseIngestionError("downloaded TSE artifact is a corrupt ZIP") from exc

        return TseArtifact(
            path=path,
            sha256=sha256,
            size_bytes=path.stat().st_size,
            canonical_csv_name=self.contract.canonical_csv_name,
            row_count=row_count,
            source_updated_at=source_updated_at,
            resource=resource,
        )

    @retry(
        retry=retry_if_exception_type((httpx.TransportError, TseRetryableHttpError)),
        stop=stop_after_attempt(4),
        wait=wait_exponential(multiplier=1, min=1, max=8),
        reraise=True,
    )
    def _request_resource_show(self) -> httpx.Response:
        with self._client_context() as client:
            response = client.get(
                self.contract.resource_show_url,
                params={"id": self.contract.resource_id},
            )
            self._raise_for_status(response)
            return response

    @retry(
        retry=retry_if_exception_type((httpx.TransportError, TseRetryableHttpError)),
        stop=stop_after_attempt(4),
        wait=wait_exponential(multiplier=1, min=1, max=8),
        reraise=True,
    )
    def _download(self, url: str, destination: Path) -> None:
        temp_path: Path | None = None

        try:
            with NamedTemporaryFile(
                mode="wb",
                prefix=f".{destination.name}.",
                suffix=".part",
                dir=destination.parent,
                delete=False,
            ) as temp_file:
                temp_path = Path(temp_file.name)

                with (
                    self._client_context() as client,
                    client.stream("GET", url) as response,
                ):
                    self._raise_for_status(response)
                    for chunk in response.iter_bytes(1024 * 1024):
                        temp_file.write(chunk)

            temp_path.replace(destination)
        except Exception:
            if temp_path is not None:
                temp_path.unlink(missing_ok=True)
            raise

    def _client_context(self) -> _HttpClientContext:
        return _HttpClientContext(self._client, self._timeout)

    def _inspect_canonical_csv(self, archive: ZipFile) -> tuple[int, datetime]:
        csv_name = self.contract.canonical_csv_name

        try:
            raw_file = archive.open(csv_name, "r")
        except KeyError as exc:
            raise TseIngestionError(f"canonical TSE CSV is missing: {csv_name}") from exc

        generation_value: tuple[str, str] | None = None
        row_count = 0

        with raw_file, TextIOWrapper(
            raw_file, encoding=self.contract.encoding, newline=""
        ) as lines:
            reader = csv.reader(
                lines,
                delimiter=self.contract.delimiter,
                quotechar=self.contract.quotechar,
                strict=True,
            )

            try:
                header = tuple(next(reader))
            except StopIteration as exc:
                raise TseIngestionError("canonical TSE CSV is empty") from exc

            if header != self.contract.expected_headers:
                raise TseIngestionError(
                    "canonical TSE CSV header differs from the configured contract"
                )

            for row_number, row in enumerate(reader, start=2):
                if len(row) != len(header):
                    raise TseIngestionError(
                        f"canonical TSE CSV row {row_number} has {len(row)} columns; "
                        f"expected {len(header)}"
                    )

                row_generation = (row[0], row[1])
                if generation_value is None:
                    generation_value = row_generation
                elif row_generation != generation_value:
                    raise TseIngestionError(
                        "canonical TSE CSV contains multiple DT_GERACAO/HH_GERACAO values"
                    )

                row_count += 1

        if row_count == 0 or generation_value is None:
            raise TseIngestionError("canonical TSE CSV contains no candidate rows")

        return row_count, self._parse_source_updated_at(*generation_value)

    def _parse_source_updated_at(self, date_value: str, time_value: str) -> datetime:
        try:
            naive = datetime.strptime(
                f"{date_value} {time_value}",
                "%d/%m/%Y %H:%M:%S",
            )
        except ValueError as exc:
            raise TseIngestionError("invalid DT_GERACAO/HH_GERACAO in canonical TSE CSV") from exc

        return naive.replace(tzinfo=ZoneInfo(self.contract.source_timezone))

    @staticmethod
    def _validate_archive_paths(archive: ZipFile) -> None:
        for info in archive.infolist():
            path = PurePosixPath(info.filename)
            if path.is_absolute() or any(part in {".", ".."} for part in path.parts):
                raise TseIngestionError(f"unsafe path inside TSE ZIP: {info.filename}")

    @staticmethod
    def _sha256(path: Path) -> str:
        digest = hashlib.sha256()
        with path.open("rb") as source:
            for chunk in iter(lambda: source.read(1024 * 1024), b""):
                digest.update(chunk)
        return digest.hexdigest()

    @staticmethod
    def _required_string(payload: dict[str, Any], key: str) -> str:
        value = payload.get(key)
        if not isinstance(value, str) or not value:
            raise TseIngestionError(f"TSE CKAN metadata field {key!r} is missing")
        return value

    @staticmethod
    def _raise_for_status(response: httpx.Response) -> None:
        if response.status_code == 429 or response.status_code >= 500:
            raise TseRetryableHttpError(
                f"temporary TSE HTTP failure: status={response.status_code}"
            )
        response.raise_for_status()


class _HttpClientContext:
    """Context manager that closes only internally-created HTTPX clients."""

    def __init__(self, client: httpx.Client | None, timeout: httpx.Timeout) -> None:
        self._provided_client = client
        self._timeout = timeout
        self._client: httpx.Client | None = None

    def __enter__(self) -> httpx.Client:
        if self._provided_client is not None:
            return self._provided_client

        self._client = httpx.Client(
            timeout=self._timeout,
            follow_redirects=True,
            headers={"User-Agent": "wv-eleicoes-data/0.1 (+official-data-ingestion)"},
        )
        return self._client

    def __exit__(self, exc_type: object, exc: object, traceback: object) -> None:
        if self._client is not None:
            self._client.close()
