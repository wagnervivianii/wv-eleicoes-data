from __future__ import annotations

import argparse
import csv
import json
from collections import Counter
from collections.abc import Sequence
from dataclasses import asdict, dataclass
from io import TextIOWrapper
from pathlib import Path
from tempfile import TemporaryDirectory
from zipfile import ZipFile

from wv_eleicoes_data.ingestion.tse.connector import TseArtifact, TseCandidatesConnector
from wv_eleicoes_data.ingestion.tse.contracts import (
    SUPPORTED_ASSET_DISCOVERY_YEARS,
    TseResourceContract,
    assets_discovery_contract_for_year,
)


@dataclass(frozen=True, slots=True)
class TseAssetsYearProbeReport:
    """Non-sensitive evidence for one official TSE declared-assets resource."""

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
    candidate_sequence_header_present: bool
    election_code_header_present: bool
    asset_type_code_header_present: bool
    asset_type_name_header_present: bool
    asset_description_header_present: bool
    asset_value_header_present: bool
    distinct_candidate_sequences: int | None
    candidate_sequences_with_multiple_assets: int | None
    max_assets_per_candidate: int | None
    blank_candidate_sequence_rows: int | None


@dataclass(frozen=True, slots=True)
class TseAssetsProbeBundle:
    """Comparable evidence for the 2022 and 2026 assets resources."""

    reports: tuple[TseAssetsYearProbeReport, ...]
    same_ordered_layout: bool
    common_headers: tuple[str, ...]
    only_2022_headers: tuple[str, ...]
    only_2026_headers: tuple[str, ...]


def build_assets_probe_bundle() -> TseAssetsProbeBundle:
    """Probe both official annual assets resources without touching PostgreSQL."""

    reports = tuple(_probe_year(year) for year in SUPPORTED_ASSET_DISCOVERY_YEARS)
    by_year = {report.election_year: report for report in reports}
    report_2022 = by_year[2022]
    report_2026 = by_year[2026]
    headers_2022 = set(report_2022.headers)
    headers_2026 = set(report_2026.headers)

    return TseAssetsProbeBundle(
        reports=reports,
        same_ordered_layout=report_2022.headers == report_2026.headers,
        common_headers=tuple(header for header in report_2026.headers if header in headers_2022),
        only_2022_headers=tuple(
            header for header in report_2022.headers if header not in headers_2026
        ),
        only_2026_headers=tuple(
            header for header in report_2026.headers if header not in headers_2022
        ),
    )


def render_assets_probe_bundle(bundle: TseAssetsProbeBundle) -> str:
    """Render deterministic UTF-8 JSON containing schema evidence and safe aggregates only."""

    return json.dumps(asdict(bundle), ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def _probe_year(year: int) -> TseAssetsYearProbeReport:
    contract = assets_discovery_contract_for_year(year)
    with TemporaryDirectory(prefix=f"wv-eleicoes-tse-assets-{year}-") as temporary_dir:
        artifact = TseCandidatesConnector(contract).fetch(Path(temporary_dir))
        aggregates = _safe_asset_aggregates(artifact, contract)

    headers = set(artifact.headers)
    return TseAssetsYearProbeReport(
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
        column_count=len(artifact.headers),
        headers=artifact.headers,
        source_updated_at=artifact.source_updated_at.isoformat(),
        candidate_sequence_header_present="SQ_CANDIDATO" in headers,
        election_code_header_present="CD_ELEICAO" in headers,
        asset_type_code_header_present="CD_TIPO_BEM_CANDIDATO" in headers,
        asset_type_name_header_present="DS_TIPO_BEM_CANDIDATO" in headers,
        asset_description_header_present="DS_BEM_CANDIDATO" in headers,
        asset_value_header_present="VR_BEM_CANDIDATO" in headers,
        distinct_candidate_sequences=aggregates[0],
        candidate_sequences_with_multiple_assets=aggregates[1],
        max_assets_per_candidate=aggregates[2],
        blank_candidate_sequence_rows=aggregates[3],
    )


def _safe_asset_aggregates(
    artifact: TseArtifact,
    contract: TseResourceContract,
) -> tuple[int | None, int | None, int | None, int | None]:
    """Return only aggregate linkage evidence; candidate identifiers are never emitted."""

    if "SQ_CANDIDATO" not in artifact.headers:
        return None, None, None, None

    counts: Counter[str] = Counter()
    blank_rows = 0
    with (
        ZipFile(artifact.path) as archive,
        archive.open(artifact.canonical_csv_name) as raw,
        TextIOWrapper(raw, encoding=contract.encoding, newline="") as stream,
    ):
        reader = csv.DictReader(
            stream,
            delimiter=contract.delimiter,
            quotechar=contract.quotechar,
        )
        for row in reader:
            value = (row.get("SQ_CANDIDATO") or "").strip()
            if not value:
                blank_rows += 1
                continue
            counts[value] += 1

    return (
        len(counts),
        sum(1 for count in counts.values() if count > 1),
        max(counts.values(), default=0),
        blank_rows,
    )


def main(argv: Sequence[str] | None = None) -> int:
    """CLI entry point for the two-year declared-assets contract probe."""

    parser = argparse.ArgumentParser(
        description=(
            "Probe official TSE declared-assets resources for 2022 and 2026 "
            "without touching PostgreSQL."
        )
    )
    parser.add_argument(
        "--output",
        type=Path,
        help="Optional JSON output path. Existing files are refused.",
    )
    args = parser.parse_args(argv)

    report_text = render_assets_probe_bundle(build_assets_probe_bundle())
    if args.output is not None:
        output = args.output.expanduser()
        if output.exists():
            parser.error(f"output already exists: {output}")
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(report_text, encoding="utf-8")

    print(report_text, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
