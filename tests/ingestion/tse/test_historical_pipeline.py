from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import MagicMock, patch

import sqlalchemy as sa

from wv_eleicoes_data.db.models import IngestionRun
from wv_eleicoes_data.ingestion.tse import persistence, pipeline
from wv_eleicoes_data.ingestion.tse.connector import TseArtifact, TseResourceMetadata
from wv_eleicoes_data.ingestion.tse.contracts import CANDIDATES_2022, CANDIDATES_2026


def _engine() -> sa.Engine:
    engine = sa.create_engine("sqlite://")
    metadata = sa.MetaData()
    table = IngestionRun.__table__.to_metadata(metadata)
    table.c.id.type = sa.Integer()
    with engine.begin() as connection:
        connection.exec_driver_sql("ATTACH DATABASE ':memory:' AS audit")
        metadata.create_all(connection)
    return engine


def _artifact(checksum: str = "a" * 64) -> TseArtifact:
    return TseArtifact(
        path=Path("not-read-by-this-test.zip"),
        sha256=checksum,
        size_bytes=1,
        canonical_csv_name=CANDIDATES_2026.canonical_csv_name,
        row_count=1,
        headers=CANDIDATES_2026.expected_headers or (),
        source_updated_at=datetime(2026, 9, 15, 12, 0, tzinfo=UTC),
        resource=TseResourceMetadata(
            resource_id="resource",
            package_id="package",
            name="artifact",
            download_url="https://example.invalid/artifact.zip",
            mimetype="application/zip",
        ),
    )


def test_start_run_persists_election_year_scope() -> None:
    engine = _engine()
    try:
        run_2022 = persistence.start_run(engine, CANDIDATES_2022)
        run_2026 = persistence.start_run(engine, CANDIDATES_2026)
        with engine.connect() as connection:
            scopes = dict(
                connection.execute(
                    sa.select(IngestionRun.id, IngestionRun.scope_key).order_by(IngestionRun.id)
                ).all()
            )
        assert scopes == {
            run_2022: "election-year:2022",
            run_2026: "election-year:2026",
        }
    finally:
        engine.dispose()


def test_checksum_skip_is_isolated_by_election_year_scope() -> None:
    engine = _engine()
    artifact = _artifact()
    try:
        prior_2022 = persistence.start_run(engine, CANDIDATES_2022)
        with engine.begin() as connection:
            connection.execute(
                sa.update(IngestionRun)
                .where(IngestionRun.id == prior_2022)
                .values(
                    status="success",
                    checksum=artifact.sha256,
                    finished_at=datetime.now(UTC),
                )
            )

        first_2026 = persistence.start_run(engine, CANDIDATES_2026)
        with (
            patch.object(persistence, "lock_artifact"),
            patch.object(persistence, "insert_rows", return_value=(0, 0, 0, 0)) as insert_rows,
        ):
            assert (
                persistence.load_artifact(
                    engine,
                    artifact,
                    CANDIDATES_2026,
                    first_2026,
                    batch_size=1000,
                )
                == "success"
            )
            insert_rows.assert_called_once()

        repeat_2026 = persistence.start_run(engine, CANDIDATES_2026)
        with (
            patch.object(persistence, "lock_artifact"),
            patch.object(persistence, "insert_rows") as insert_rows,
        ):
            assert (
                persistence.load_artifact(
                    engine,
                    artifact,
                    CANDIDATES_2026,
                    repeat_2026,
                    batch_size=1000,
                )
                == "skipped"
            )
            insert_rows.assert_not_called()
    finally:
        engine.dispose()


def test_dataset_lock_is_partitioned_by_election_year_scope() -> None:
    connection = MagicMock()
    persistence.lock_artifact(connection, CANDIDATES_2022, "same-checksum")
    key_2022 = connection.execute.call_args.args[1]["key"]
    persistence.lock_artifact(connection, CANDIDATES_2026, "same-checksum")
    key_2026 = connection.execute.call_args.args[1]["key"]
    assert key_2022 != key_2026


def test_cli_routes_year_2022_to_frozen_contract() -> None:
    engine = MagicMock()
    with (
        patch.object(pipeline, "IngestionSettings"),
        patch.object(pipeline, "ingestion_engine", return_value=engine),
        patch.object(pipeline, "run_pipeline", return_value=(123, "success")) as run_pipeline,
    ):
        assert pipeline.main(["--year", "2022"]) == 0

    connector = run_pipeline.call_args.kwargs["connector"]
    assert connector.contract is CANDIDATES_2022
    engine.dispose.assert_called_once()
