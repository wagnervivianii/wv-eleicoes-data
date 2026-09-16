from __future__ import annotations

import argparse
import csv
import json
import re
from collections import Counter
from collections.abc import Sequence
from dataclasses import asdict, dataclass
from datetime import datetime
from decimal import Decimal, InvalidOperation
from io import TextIOWrapper
from pathlib import Path
from tempfile import TemporaryDirectory
from zipfile import ZipFile

from wv_eleicoes_data.ingestion.tse.connector import TseArtifact, TseCandidatesConnector
from wv_eleicoes_data.ingestion.tse.contracts import (
    SUPPORTED_ASSET_YEARS,
    TseResourceContract,
    assets_contract_for_year,
    candidates_contract_for_year,
)

_ITEM_KEY_HEADERS = (
    "ANO_ELEICAO",
    "CD_ELEICAO",
    "SQ_CANDIDATO",
    "NR_ORDEM_BEM_CANDIDATO",
)
_KNOWN_TSE_SENTINELS = {"#NULO", "#NE", "NÃO DIVULGÁVEL", "-1", "-3", "-4"}
_INTEGER_RE = re.compile(r"^[+-]?\d+$")
_DECIMAL_COMMA_RE = re.compile(r"^[+-]?\d+,\d+$")
_DECIMAL_DOT_RE = re.compile(r"^[+-]?\d+\.\d+$")
_BR_GROUPED_RE = re.compile(r"^[+-]?\d{1,3}(?:\.\d{3})+,\d+$")
_US_GROUPED_RE = re.compile(r"^[+-]?\d{1,3}(?:,\d{3})+\.\d+$")


@dataclass(frozen=True, slots=True)
class TseAssetQualityReport:
    """Non-sensitive quality evidence for one frozen TSE declared-assets contract."""

    source: str
    dataset: str
    election_year: int
    package_id: str
    resource_id: str
    artifact_name: str
    canonical_csv_name: str
    sha256: str
    row_count: int
    item_key_headers: tuple[str, ...]
    distinct_item_keys: int
    duplicate_item_keys: int
    duplicate_item_key_rows: int
    blank_election_code_rows: int
    blank_candidate_sequence_rows: int
    blank_asset_order_rows: int
    non_integer_asset_order_rows: int
    zero_asset_order_rows: int
    negative_asset_order_rows: int
    distinct_asset_candidate_keys: int
    candidate_keys_missing_from_candidates: int
    all_asset_candidate_keys_match_candidates: bool
    blank_asset_type_code_rows: int
    blank_asset_type_name_rows: int
    blank_asset_description_rows: int
    blank_asset_value_rows: int
    known_tse_sentinel_value_rows: int
    integer_value_rows: int
    decimal_comma_value_rows: int
    decimal_dot_value_rows: int
    brazilian_grouped_value_rows: int
    us_grouped_value_rows: int
    unrecognized_value_rows: int
    negative_numeric_value_rows: int
    max_decimal_scale: int | None
    blank_asset_update_date_rows: int
    blank_asset_update_time_rows: int
    invalid_asset_update_timestamp_rows: int


@dataclass(frozen=True, slots=True)
class TseAssetQualityBundle:
    """Comparable two-year quality evidence used before RAW persistence is designed."""

    reports: tuple[TseAssetQualityReport, ...]
    all_item_keys_unique: bool
    all_candidate_links_resolve: bool
    all_asset_values_recognized: bool


def build_asset_quality_bundle() -> TseAssetQualityBundle:
    """Probe frozen 2022/2026 assets plus candidate-link coverage without database access."""

    reports = tuple(_probe_year(year) for year in SUPPORTED_ASSET_YEARS)
    return TseAssetQualityBundle(
        reports=reports,
        all_item_keys_unique=all(report.duplicate_item_keys == 0 for report in reports),
        all_candidate_links_resolve=all(
            report.all_asset_candidate_keys_match_candidates for report in reports
        ),
        all_asset_values_recognized=all(report.unrecognized_value_rows == 0 for report in reports),
    )


def render_asset_quality_bundle(bundle: TseAssetQualityBundle) -> str:
    """Render deterministic JSON containing only schema/quality aggregates."""

    return json.dumps(asdict(bundle), ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def _probe_year(year: int) -> TseAssetQualityReport:
    assets_contract = assets_contract_for_year(year)
    candidates_contract = candidates_contract_for_year(year)
    with TemporaryDirectory(prefix=f"wv-eleicoes-tse-assets-quality-{year}-") as temporary_dir:
        directory = Path(temporary_dir)
        assets_artifact = TseCandidatesConnector(assets_contract).fetch(directory)
        candidates_artifact = TseCandidatesConnector(candidates_contract).fetch(directory)
        candidate_keys = _candidate_keys(candidates_artifact, candidates_contract)
        return _analyze_assets(assets_artifact, assets_contract, candidate_keys)


def _candidate_keys(
    artifact: TseArtifact,
    contract: TseResourceContract,
) -> set[tuple[str, str]]:
    keys: set[tuple[str, str]] = set()
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
            election_code = (row.get("CD_ELEICAO") or "").strip()
            candidate_sequence = (row.get("SQ_CANDIDATO") or "").strip()
            if election_code and candidate_sequence:
                keys.add((election_code, candidate_sequence))
    return keys


def _analyze_assets(
    artifact: TseArtifact,
    contract: TseResourceContract,
    candidate_keys: set[tuple[str, str]],
) -> TseAssetQualityReport:
    item_counts: Counter[tuple[str, str, str, str]] = Counter()
    asset_candidate_keys: set[tuple[str, str]] = set()
    counts: Counter[str] = Counter()
    max_decimal_scale: int | None = None

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
            election_year = (row.get("ANO_ELEICAO") or "").strip()
            election_code = (row.get("CD_ELEICAO") or "").strip()
            candidate_sequence = (row.get("SQ_CANDIDATO") or "").strip()
            asset_order = (row.get("NR_ORDEM_BEM_CANDIDATO") or "").strip()

            if not election_code:
                counts["blank_election_code_rows"] += 1
            if not candidate_sequence:
                counts["blank_candidate_sequence_rows"] += 1
            if not asset_order:
                counts["blank_asset_order_rows"] += 1
            elif not _INTEGER_RE.fullmatch(asset_order):
                counts["non_integer_asset_order_rows"] += 1
            else:
                order_number = int(asset_order)
                if order_number == 0:
                    counts["zero_asset_order_rows"] += 1
                elif order_number < 0:
                    counts["negative_asset_order_rows"] += 1

            if election_code and candidate_sequence:
                asset_candidate_keys.add((election_code, candidate_sequence))
            if election_year and election_code and candidate_sequence and asset_order:
                item_counts[(election_year, election_code, candidate_sequence, asset_order)] += 1

            if not (row.get("CD_TIPO_BEM_CANDIDATO") or "").strip():
                counts["blank_asset_type_code_rows"] += 1
            if not (row.get("DS_TIPO_BEM_CANDIDATO") or "").strip():
                counts["blank_asset_type_name_rows"] += 1
            if not (row.get("DS_BEM_CANDIDATO") or "").strip():
                counts["blank_asset_description_rows"] += 1

            category, numeric_value, scale = _classify_asset_value(
                (row.get("VR_BEM_CANDIDATO") or "").strip()
            )
            counts[category] += 1
            if numeric_value is not None and numeric_value < 0:
                counts["negative_numeric_value_rows"] += 1
            if scale is not None:
                max_decimal_scale = (
                    scale if max_decimal_scale is None else max(max_decimal_scale, scale)
                )

            update_date = (row.get("DT_ULT_ATUAL_BEM_CANDIDATO") or "").strip()
            update_time = (row.get("HH_ULT_ATUAL_BEM_CANDIDATO") or "").strip()
            if not update_date:
                counts["blank_asset_update_date_rows"] += 1
            if not update_time:
                counts["blank_asset_update_time_rows"] += 1
            if update_date and update_time:
                try:
                    datetime.strptime(
                        f"{update_date} {update_time}",
                        "%d/%m/%Y %H:%M:%S",
                    )
                except ValueError:
                    counts["invalid_asset_update_timestamp_rows"] += 1

    duplicate_item_counts = [count for count in item_counts.values() if count > 1]
    missing_candidate_keys = asset_candidate_keys - candidate_keys

    return TseAssetQualityReport(
        source=contract.source,
        dataset=contract.dataset,
        election_year=contract.election_year,
        package_id=artifact.resource.package_id,
        resource_id=artifact.resource.resource_id,
        artifact_name=contract.artifact_name,
        canonical_csv_name=artifact.canonical_csv_name,
        sha256=artifact.sha256,
        row_count=artifact.row_count,
        item_key_headers=_ITEM_KEY_HEADERS,
        distinct_item_keys=len(item_counts),
        duplicate_item_keys=len(duplicate_item_counts),
        duplicate_item_key_rows=sum(count - 1 for count in duplicate_item_counts),
        blank_election_code_rows=counts["blank_election_code_rows"],
        blank_candidate_sequence_rows=counts["blank_candidate_sequence_rows"],
        blank_asset_order_rows=counts["blank_asset_order_rows"],
        non_integer_asset_order_rows=counts["non_integer_asset_order_rows"],
        zero_asset_order_rows=counts["zero_asset_order_rows"],
        negative_asset_order_rows=counts["negative_asset_order_rows"],
        distinct_asset_candidate_keys=len(asset_candidate_keys),
        candidate_keys_missing_from_candidates=len(missing_candidate_keys),
        all_asset_candidate_keys_match_candidates=not missing_candidate_keys,
        blank_asset_type_code_rows=counts["blank_asset_type_code_rows"],
        blank_asset_type_name_rows=counts["blank_asset_type_name_rows"],
        blank_asset_description_rows=counts["blank_asset_description_rows"],
        blank_asset_value_rows=counts["blank_asset_value_rows"],
        known_tse_sentinel_value_rows=counts["known_tse_sentinel_value_rows"],
        integer_value_rows=counts["integer_value_rows"],
        decimal_comma_value_rows=counts["decimal_comma_value_rows"],
        decimal_dot_value_rows=counts["decimal_dot_value_rows"],
        brazilian_grouped_value_rows=counts["brazilian_grouped_value_rows"],
        us_grouped_value_rows=counts["us_grouped_value_rows"],
        unrecognized_value_rows=counts["unrecognized_value_rows"],
        negative_numeric_value_rows=counts["negative_numeric_value_rows"],
        max_decimal_scale=max_decimal_scale,
        blank_asset_update_date_rows=counts["blank_asset_update_date_rows"],
        blank_asset_update_time_rows=counts["blank_asset_update_time_rows"],
        invalid_asset_update_timestamp_rows=counts["invalid_asset_update_timestamp_rows"],
    )


def _classify_asset_value(value: str) -> tuple[str, Decimal | None, int | None]:
    if not value:
        return "blank_asset_value_rows", None, None
    if value in _KNOWN_TSE_SENTINELS:
        return "known_tse_sentinel_value_rows", None, None

    category: str
    normalized: str
    scale: int
    if _INTEGER_RE.fullmatch(value):
        category = "integer_value_rows"
        normalized = value
        scale = 0
    elif _DECIMAL_COMMA_RE.fullmatch(value):
        category = "decimal_comma_value_rows"
        normalized = value.replace(",", ".")
        scale = len(value.rsplit(",", 1)[1])
    elif _DECIMAL_DOT_RE.fullmatch(value):
        category = "decimal_dot_value_rows"
        normalized = value
        scale = len(value.rsplit(".", 1)[1])
    elif _BR_GROUPED_RE.fullmatch(value):
        category = "brazilian_grouped_value_rows"
        normalized = value.replace(".", "").replace(",", ".")
        scale = len(value.rsplit(",", 1)[1])
    elif _US_GROUPED_RE.fullmatch(value):
        category = "us_grouped_value_rows"
        normalized = value.replace(",", "")
        scale = len(value.rsplit(".", 1)[1])
    else:
        return "unrecognized_value_rows", None, None

    try:
        numeric = Decimal(normalized)
    except InvalidOperation:
        return "unrecognized_value_rows", None, None
    return category, numeric, scale


def main(argv: Sequence[str] | None = None) -> int:
    """CLI entry point for frozen-contract and quality evidence gathering."""

    parser = argparse.ArgumentParser(
        description=(
            "Validate frozen TSE declared-assets contracts and emit non-sensitive "
            "item-key, monetary-format and candidate-link quality evidence."
        )
    )
    parser.add_argument(
        "--output",
        type=Path,
        help="Optional JSON output path. Existing files are refused.",
    )
    args = parser.parse_args(argv)

    report_text = render_asset_quality_bundle(build_asset_quality_bundle())
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
