from __future__ import annotations

import argparse
import json
from dataclasses import asdict, dataclass
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Sequence

from wv_eleicoes_data.ingestion.tse.connector import TseCandidatesConnector
from wv_eleicoes_data.ingestion.tse.contracts import (
    CANDIDATES_2022_DISCOVERY,
    TSE_CANDIDATES_2026_HEADERS,
    TseResourceContract,
)

_SUPPORTED_CONTRACTS: dict[int, TseResourceContract] = {
    2022: CANDIDATES_2022_DISCOVERY,
}

_IDENTITY_RELEVANT_HEADERS = (
    "SQ_CANDIDATO",
    "NR_CPF_CANDIDATO",
    "NR_TITULO_ELEITORAL_CANDIDATO",
    "NM_CANDIDATO",
    "DT_NASCIMENTO",
)


@dataclass(frozen=True, slots=True)
class TseCandidatesProbeReport:
    """Non-sensitive evidence used to freeze a historical TSE candidates contract."""

    source: str
    dataset: str
    election_year: int
    package_id: str
    resource_id: str
    download_url: str
    artifact_name: str
    canonical_csv_name: str
    sha256: str
    size_bytes: int
    row_count: int
    column_count: int
    headers: tuple[str, ...]
    source_updated_at: str
    same_layout_as_2026: bool
    missing_vs_2026: tuple[str, ...]
    extra_vs_2026: tuple[str, ...]
    identity_relevant_headers_present: tuple[str, ...]


def build_probe_report(year: int) -> TseCandidatesProbeReport:
    """Download one official historical snapshot and return schema evidence only."""

    contract = _contract_for_year(year)
    with TemporaryDirectory(prefix=f"wv-eleicoes-tse-{year}-") as temporary_dir:
        artifact = TseCandidatesConnector(contract).fetch(Path(temporary_dir))

    headers = artifact.headers
    header_set = set(headers)
    current_set = set(TSE_CANDIDATES_2026_HEADERS)

    return TseCandidatesProbeReport(
        source=contract.source,
        dataset=contract.dataset,
        election_year=contract.election_year,
        package_id=artifact.resource.package_id,
        resource_id=artifact.resource.resource_id,
        download_url=artifact.resource.download_url,
        artifact_name=contract.artifact_name,
        canonical_csv_name=artifact.canonical_csv_name,
        sha256=artifact.sha256,
        size_bytes=artifact.size_bytes,
        row_count=artifact.row_count,
        column_count=len(headers),
        headers=headers,
        source_updated_at=artifact.source_updated_at.isoformat(),
        same_layout_as_2026=headers == TSE_CANDIDATES_2026_HEADERS,
        missing_vs_2026=tuple(
            field for field in TSE_CANDIDATES_2026_HEADERS if field not in header_set
        ),
        extra_vs_2026=tuple(field for field in headers if field not in current_set),
        identity_relevant_headers_present=tuple(
            field for field in _IDENTITY_RELEVANT_HEADERS if field in header_set
        ),
    )


def render_probe_report(report: TseCandidatesProbeReport) -> str:
    """Render a deterministic, UTF-8-safe JSON representation of a probe report."""

    return json.dumps(asdict(report), ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def main(argv: Sequence[str] | None = None) -> int:
    """CLI entry point for the historical candidates contract probe."""

    parser = argparse.ArgumentParser(
        description=(
            "Probe an official historical TSE candidates resource without touching PostgreSQL."
        )
    )
    parser.add_argument(
        "--year",
        type=int,
        required=True,
        choices=sorted(_SUPPORTED_CONTRACTS),
        help="Election year whose official candidates resource will be inspected.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        help="Optional path for the JSON report. Existing files are refused.",
    )
    args = parser.parse_args(argv)

    report_text = render_probe_report(build_probe_report(args.year))
    if args.output is not None:
        output = args.output.expanduser()
        if output.exists():
            parser.error(f"output already exists: {output}")
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(report_text, encoding="utf-8")

    print(report_text, end="")
    return 0


def _contract_for_year(year: int) -> TseResourceContract:
    try:
        return _SUPPORTED_CONTRACTS[year]
    except KeyError as exc:
        raise ValueError(f"unsupported historical TSE candidates year: {year}") from exc


if __name__ == "__main__":
    raise SystemExit(main())
