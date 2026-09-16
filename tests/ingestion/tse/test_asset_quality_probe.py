import csv
import io
from datetime import datetime
from decimal import Decimal
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile
from zoneinfo import ZoneInfo

from wv_eleicoes_data.ingestion.tse.asset_quality_probe import (
    TseAssetQualityBundle,
    _analyze_assets,
    _classify_asset_value,
    render_asset_quality_bundle,
)
from wv_eleicoes_data.ingestion.tse.connector import TseArtifact, TseResourceMetadata
from wv_eleicoes_data.ingestion.tse.contracts import ASSETS_2022, TSE_ASSETS_2022_HEADERS


def _row(**overrides: str) -> list[str]:
    values = {header: "x" for header in TSE_ASSETS_2022_HEADERS}
    values.update(
        {
            "DT_GERACAO": "02/10/2022",
            "HH_GERACAO": "08:30:00",
            "ANO_ELEICAO": "2022",
            "CD_ELEICAO": "544",
            "SQ_CANDIDATO": "100",
            "NR_ORDEM_BEM_CANDIDATO": "1",
            "CD_TIPO_BEM_CANDIDATO": "01",
            "DS_TIPO_BEM_CANDIDATO": "TIPO",
            "DS_BEM_CANDIDATO": "DESCRICAO",
            "VR_BEM_CANDIDATO": "1000,50",
            "DT_ULT_ATUAL_BEM_CANDIDATO": "01/10/2022",
            "HH_ULT_ATUAL_BEM_CANDIDATO": "10:20:30",
        }
    )
    values.update(overrides)
    return [values[header] for header in TSE_ASSETS_2022_HEADERS]


def _artifact(tmp_path: Path, rows: list[list[str]]) -> TseArtifact:
    text_buffer = io.StringIO(newline="")
    writer = csv.writer(
        text_buffer,
        delimiter=ASSETS_2022.delimiter,
        quotechar=ASSETS_2022.quotechar,
        lineterminator="\r\n",
    )
    writer.writerow(TSE_ASSETS_2022_HEADERS)
    writer.writerows(rows)

    path = tmp_path / ASSETS_2022.artifact_name
    with ZipFile(path, "w", compression=ZIP_DEFLATED) as archive:
        archive.writestr(
            ASSETS_2022.canonical_csv_name,
            text_buffer.getvalue().encode(ASSETS_2022.encoding),
        )

    return TseArtifact(
        path=path,
        sha256="a" * 64,
        size_bytes=path.stat().st_size,
        canonical_csv_name=ASSETS_2022.canonical_csv_name,
        row_count=len(rows),
        headers=TSE_ASSETS_2022_HEADERS,
        source_updated_at=datetime(2022, 10, 2, 8, 30, tzinfo=ZoneInfo("America/Sao_Paulo")),
        resource=TseResourceMetadata(
            resource_id=ASSETS_2022.resource_id,
            package_id=ASSETS_2022.package_id,
            name="Bens de candidatos",
            download_url="https://example.invalid/bem_candidato_2022.zip",
            mimetype=ASSETS_2022.expected_mimetype,
        ),
    )


def test_asset_value_classifier_keeps_format_evidence_without_emitting_values() -> None:
    assert _classify_asset_value("") == ("blank_asset_value_rows", None, None)
    assert _classify_asset_value("#NULO") == ("known_tse_sentinel_value_rows", None, None)
    assert _classify_asset_value("10") == ("integer_value_rows", Decimal("10"), 0)
    assert _classify_asset_value("10,50") == (
        "decimal_comma_value_rows",
        Decimal("10.50"),
        2,
    )
    assert _classify_asset_value("10.50") == (
        "decimal_dot_value_rows",
        Decimal("10.50"),
        2,
    )
    assert _classify_asset_value("1.234,56") == (
        "brazilian_grouped_value_rows",
        Decimal("1234.56"),
        2,
    )
    assert _classify_asset_value("1,234.56") == (
        "us_grouped_value_rows",
        Decimal("1234.56"),
        2,
    )
    assert _classify_asset_value("R$ 10") == ("unrecognized_value_rows", None, None)


def test_asset_quality_detects_duplicate_item_key_money_shapes_and_orphans(
    tmp_path: Path,
) -> None:
    rows = [
        _row(SQ_CANDIDATO="100", NR_ORDEM_BEM_CANDIDATO="1", VR_BEM_CANDIDATO="1000,50"),
        _row(
            SQ_CANDIDATO="100",
            NR_ORDEM_BEM_CANDIDATO="2",
            VR_BEM_CANDIDATO="1.234,56",
        ),
        _row(SQ_CANDIDATO="200", NR_ORDEM_BEM_CANDIDATO="1", VR_BEM_CANDIDATO="1234.56"),
        _row(SQ_CANDIDATO="200", NR_ORDEM_BEM_CANDIDATO="1", VR_BEM_CANDIDATO="#NULO"),
        _row(
            SQ_CANDIDATO="",
            NR_ORDEM_BEM_CANDIDATO="",
            CD_TIPO_BEM_CANDIDATO="",
            DS_TIPO_BEM_CANDIDATO="",
            DS_BEM_CANDIDATO="",
            VR_BEM_CANDIDATO="R$ 10",
            DT_ULT_ATUAL_BEM_CANDIDATO="31/02/2022",
            HH_ULT_ATUAL_BEM_CANDIDATO="10:20:30",
        ),
    ]
    report = _analyze_assets(_artifact(tmp_path, rows), ASSETS_2022, {("544", "100")})

    assert report.row_count == 5
    assert report.distinct_item_keys == 3
    assert report.duplicate_item_keys == 1
    assert report.duplicate_item_key_rows == 1
    assert report.blank_candidate_sequence_rows == 1
    assert report.blank_asset_order_rows == 1
    assert report.distinct_asset_candidate_keys == 2
    assert report.candidate_keys_missing_from_candidates == 1
    assert report.all_asset_candidate_keys_match_candidates is False
    assert report.blank_asset_type_code_rows == 1
    assert report.blank_asset_type_name_rows == 1
    assert report.blank_asset_description_rows == 1
    assert report.decimal_comma_value_rows == 1
    assert report.brazilian_grouped_value_rows == 1
    assert report.decimal_dot_value_rows == 1
    assert report.known_tse_sentinel_value_rows == 1
    assert report.unrecognized_value_rows == 1
    assert report.max_decimal_scale == 2
    assert report.invalid_asset_update_timestamp_rows == 1


def test_quality_bundle_render_is_deterministic_and_non_sensitive(tmp_path: Path) -> None:
    report = _analyze_assets(
        _artifact(tmp_path, [_row(SQ_CANDIDATO="candidate-secret")]),
        ASSETS_2022,
        {("544", "candidate-secret")},
    )
    bundle = TseAssetQualityBundle(
        reports=(report,),
        all_item_keys_unique=True,
        all_candidate_links_resolve=True,
        all_asset_values_recognized=True,
    )

    rendered = render_asset_quality_bundle(bundle)

    assert rendered.endswith("\n")
    assert '"all_item_keys_unique": true' in rendered
    assert '"decimal_comma_value_rows": 1' in rendered
    assert "candidate-secret" not in rendered
