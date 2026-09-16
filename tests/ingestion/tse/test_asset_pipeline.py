import csv
from io import StringIO
from pathlib import Path
from unittest.mock import MagicMock, patch
from zipfile import ZipFile

import pytest
import sqlalchemy as sa

from wv_eleicoes_data.db.models import (
    AssetChange,
    IngestionRun,
    TseCandidate,
    TseCandidateAsset,
)
from wv_eleicoes_data.db.models.tse_candidate import TSE_CANDIDATE_SOURCE_HEADERS
from wv_eleicoes_data.db.models.tse_candidate_asset import TSE_ASSET_SOURCE_HEADERS
from wv_eleicoes_data.ingestion.tse import asset_persistence, asset_pipeline
from wv_eleicoes_data.ingestion.tse.connector import TseCandidatesConnector, TseResourceMetadata
from wv_eleicoes_data.ingestion.tse.contracts import ASSETS_2022, ASSETS_2026, CANDIDATES_2022


@pytest.fixture
def engine():
    engine = sa.create_engine("sqlite://")
    metadata = sa.MetaData()
    for model in (IngestionRun, TseCandidate, TseCandidateAsset, AssetChange):
        table = model.__table__.to_metadata(metadata)
        table.c.id.type = sa.Integer()
    with engine.begin() as connection:
        connection.exec_driver_sql("ATTACH DATABASE ':memory:' AS audit")
        connection.exec_driver_sql("ATTACH DATABASE ':memory:' AS raw")
        metadata.create_all(connection)
    yield engine
    engine.dispose()


def _candidate_payload(sequence: str, election_code: str = "544") -> dict[str, object]:
    values: dict[str, object] = dict.fromkeys(TSE_CANDIDATE_SOURCE_HEADERS, "#NULO")
    values.update(
        ano_eleicao="2022",
        cd_eleicao=election_code,
        sq_candidato=sequence,
        ingestion_run_id=1,
        valid_from_run_id=1,
        source_file=CANDIDATES_2022.canonical_csv_name,
        source_row_number=int(sequence) + 2,
    )
    return values


def _seed_candidates(engine: sa.Engine, sequences: tuple[str, ...] = ("100", "200")) -> None:
    with engine.begin() as connection:
        connection.execute(
            sa.insert(IngestionRun).values(
                id=1,
                source="TSE",
                dataset="candidatos",
                scope_key="election-year:2022",
                status="success",
            )
        )
        for sequence in sequences:
            connection.execute(sa.insert(TseCandidate).values(**_candidate_payload(sequence)))


def _asset_row(
    *,
    sequence: str,
    order: str,
    description: str = "",
    value: str = "1000,00",
    generation_time: str = "08:30:00",
) -> list[str]:
    values = {name: "x" for name in TSE_ASSET_SOURCE_HEADERS}
    values.update(
        dt_geracao="16/09/2026",
        hh_geracao=generation_time,
        ano_eleicao="2022",
        cd_eleicao="544",
        sq_candidato=sequence,
        nr_ordem_bem_candidato=order,
        cd_tipo_bem_candidato="01",
        ds_tipo_bem_candidato="TIPO",
        ds_bem_candidato=description,
        vr_bem_candidato=value,
        dt_ult_atual_bem_candidato="01/10/2022",
        hh_ult_atual_bem_candidato="10:20:30",
    )
    return [str(values[name]) for name in TSE_ASSET_SOURCE_HEADERS]


def _snapshot(tmp_path: Path, rows: list[list[str]], name: str = "assets.zip"):
    stream = StringIO(newline="")
    writer = csv.writer(stream, delimiter=";", lineterminator="\r\n")
    writer.writerow(ASSETS_2022.expected_headers)
    writer.writerows(rows)
    path = tmp_path / name
    with ZipFile(path, "w") as archive:
        archive.writestr(ASSETS_2022.canonical_csv_name, stream.getvalue().encode("latin-1"))
    return TseCandidatesConnector(ASSETS_2022).inspect_artifact(
        path,
        TseResourceMetadata(
            ASSETS_2022.resource_id,
            ASSETS_2022.package_id,
            "Bens de candidatos",
            "https://example.test/assets.zip",
            "application/zip",
        ),
    )


def _ingest(engine: sa.Engine, snapshot) -> tuple[int, str]:
    connector = TseCandidatesConnector(ASSETS_2022)
    with (
        patch.object(connector, "fetch", return_value=snapshot),
        patch.object(asset_persistence, "lock_artifact"),
    ):
        return asset_pipeline.run_pipeline(engine, connector=connector, batch_size=2)


def test_asset_source_mapping_matches_frozen_contract() -> None:
    assert tuple(TSE_ASSET_SOURCE_HEADERS.values()) == ASSETS_2022.expected_headers
    assert len(TSE_ASSET_SOURCE_HEADERS) == 19


def test_first_load_repeat_and_source_fidelity(engine, tmp_path: Path) -> None:
    _seed_candidates(engine)
    rows = [
        _asset_row(sequence="100", order="1", description="", value="1000,00"),
        _asset_row(sequence="100", order="2", description="CASA", value="-10,50"),
        _asset_row(sequence="200", order="1", description="CARRO", value="25000,00"),
    ]
    snapshot = _snapshot(tmp_path, rows)

    first_id, first_status = _ingest(engine, snapshot)
    repeat_id, repeat_status = _ingest(engine, snapshot)

    assert (first_status, repeat_status) == ("success", "skipped")
    with engine.connect() as connection:
        stored = (
            connection.execute(sa.select(TseCandidateAsset).order_by(TseCandidateAsset.id))
            .mappings()
            .all()
        )
        assert len(stored) == 3
        assert stored[0]["ds_bem_candidato"] == ""
        assert stored[1]["vr_bem_candidato"] == "-10,50"
        assert all(row["valid_to_run_id"] is None for row in stored)
        assert all(row["content_hash"] for row in stored)

        changes = (
            connection.execute(
                sa.select(AssetChange).where(AssetChange.run_id == first_id)
            )
            .mappings()
            .all()
        )
        assert len(changes) == 3
        assert {change["change_type"] for change in changes} == {"A"}

        repeat = connection.execute(
            sa.select(IngestionRun).where(IngestionRun.id == repeat_id)
        ).mappings().one()
        assert repeat["rows_downloaded"] == 3
        assert repeat["rows_inserted"] == 0
        assert repeat["rows_added"] == 0
        assert repeat["rows_updated"] == 0
        assert repeat["rows_removed"] == 0
        assert repeat["rows_unchanged"] == 0


def test_regeneration_then_add_modify_remove(engine, tmp_path: Path) -> None:
    _seed_candidates(engine)
    first_rows = [
        _asset_row(sequence="100", order="1", description="A"),
        _asset_row(sequence="100", order="2", description="B"),
        _asset_row(sequence="200", order="1", description="C"),
    ]
    first_snapshot = _snapshot(tmp_path, first_rows, "first.zip")
    first_run, _ = _ingest(engine, first_snapshot)

    regenerated_rows = [row.copy() for row in first_rows]
    for row in regenerated_rows:
        row[1] = "09:30:00"
    regenerated_snapshot = _snapshot(tmp_path, regenerated_rows, "regenerated.zip")
    regenerated_run, status = _ingest(engine, regenerated_snapshot)
    assert status == "success"

    with engine.connect() as connection:
        run = connection.execute(
            sa.select(IngestionRun).where(IngestionRun.id == regenerated_run)
        ).mappings().one()
        counters = [
            run["rows_added"],
            run["rows_updated"],
            run["rows_removed"],
            run["rows_unchanged"],
        ]
        assert counters == [
            0,
            0,
            0,
            3,
        ]
        assert connection.scalar(
            sa.select(sa.func.count())
            .select_from(AssetChange)
            .where(AssetChange.run_id == regenerated_run)
        ) == 0

    mixed_rows = [
        _asset_row(sequence="100", order="1", description="A2"),
        _asset_row(sequence="100", order="3", description="NEW", value="-5,00"),
        _asset_row(sequence="200", order="1", description="C"),
    ]
    mixed_snapshot = _snapshot(tmp_path, mixed_rows, "mixed.zip")
    mixed_run, _ = _ingest(engine, mixed_snapshot)

    with engine.connect() as connection:
        run = connection.execute(
            sa.select(IngestionRun).where(IngestionRun.id == mixed_run)
        ).mappings().one()
        counters = [
            run["rows_added"],
            run["rows_updated"],
            run["rows_removed"],
            run["rows_unchanged"],
        ]
        assert counters == [
            1,
            1,
            1,
            1,
        ]
        assert run["rows_inserted"] == 2

        changes = (
            connection.execute(sa.select(AssetChange).where(AssetChange.run_id == mixed_run))
            .mappings()
            .all()
        )
        assert sorted(change["change_type"] for change in changes) == ["A", "D", "M"]
        modified = next(change for change in changes if change["change_type"] == "M")
        assert modified["changed_fields"] == ["DS_BEM_CANDIDATO"]

        active = (
            connection.execute(
                sa.select(TseCandidateAsset).where(TseCandidateAsset.valid_to_run_id.is_(None))
            )
            .mappings()
            .all()
        )
        assert {
            (row["sq_candidato"], row["nr_ordem_bem_candidato"])
            for row in active
        } == {("100", "1"), ("100", "3"), ("200", "1")}
        assert sum(row["valid_from_run_id"] == first_run for row in active) == 1


def test_asset_ingestion_rejects_unknown_candidacy_and_rolls_back(engine, tmp_path: Path) -> None:
    _seed_candidates(engine, ("100",))
    snapshot = _snapshot(
        tmp_path,
        [
            _asset_row(sequence="100", order="1"),
            _asset_row(sequence="999", order="1"),
        ],
    )

    with pytest.raises(asset_persistence.TseIngestionError, match="unknown active candidacy"):
        _ingest(engine, snapshot)

    with engine.connect() as connection:
        assert connection.scalar(sa.select(sa.func.count()).select_from(TseCandidateAsset)) == 0
        assert connection.scalar(sa.select(sa.func.count()).select_from(AssetChange)) == 0
        asset_run = connection.execute(
            sa.select(IngestionRun)
            .where(IngestionRun.dataset == "bens_candidatos")
            .order_by(IngestionRun.id.desc())
        ).mappings().first()
        assert asset_run is not None
        assert asset_run["status"] == "failed"
        assert "999" not in asset_run["error_message"]


@pytest.mark.parametrize("order", ["", "0", "-1", "abc"])
def test_asset_ingestion_rejects_invalid_item_order(engine, tmp_path: Path, order: str) -> None:
    _seed_candidates(engine)
    snapshot = _snapshot(tmp_path, [_asset_row(sequence="100", order=order)])
    with pytest.raises(asset_persistence.TseIngestionError):
        _ingest(engine, snapshot)
    with engine.connect() as connection:
        assert connection.scalar(sa.select(sa.func.count()).select_from(TseCandidateAsset)) == 0


def test_asset_hash_ignores_only_artifact_generation_timestamp() -> None:
    source = dict.fromkeys(TSE_ASSET_SOURCE_HEADERS, "")
    digest = asset_persistence.content_hash(source)
    source.update(dt_geracao="16/09/2026", hh_geracao="12:34:56")
    assert asset_persistence.content_hash(source) == digest

    source["dt_ult_atual_bem_candidato"] = "15/09/2026"
    assert asset_persistence.content_hash(source) != digest


def test_asset_changed_fields_use_official_header_order() -> None:
    previous = dict.fromkeys(TSE_ASSET_SOURCE_HEADERS, "")
    incoming = dict(previous)
    incoming["dt_geracao"] = "16/09/2026"
    incoming["hh_geracao"] = "12:00:00"
    assert asset_persistence.changed_fields(previous, incoming) == []

    incoming["ds_bem_candidato"] = "novo"
    incoming["vr_bem_candidato"] = "-5,00"
    assert asset_persistence.changed_fields(previous, incoming) == [
        "DS_BEM_CANDIDATO",
        "VR_BEM_CANDIDATO",
    ]


def test_asset_lock_is_dataset_and_year_scoped() -> None:
    connection = MagicMock()
    asset_persistence.lock_artifact(connection, ASSETS_2022, "same")
    key_2022 = connection.execute.call_args.args[1]["key"]
    asset_persistence.lock_artifact(connection, ASSETS_2026, "same")
    key_2026 = connection.execute.call_args.args[1]["key"]
    assert key_2022 != key_2026


def test_asset_cli_routes_registered_year() -> None:
    engine = MagicMock()
    with (
        patch.object(asset_pipeline, "IngestionSettings"),
        patch.object(asset_pipeline, "ingestion_engine", return_value=engine),
        patch.object(asset_pipeline, "run_pipeline", return_value=(123, "success")) as run_pipeline,
    ):
        assert asset_pipeline.main(["--year", "2022"]) == 0

    connector = run_pipeline.call_args.kwargs["connector"]
    assert connector.contract is ASSETS_2022
    engine.dispose.assert_called_once()
