import csv
from io import StringIO
from pathlib import Path
from unittest.mock import patch
from zipfile import ZipFile

import pytest
import sqlalchemy as sa

from wv_eleicoes_data.db.models import IngestionRun, TseCandidate
from wv_eleicoes_data.db.models.tse_candidate import TSE_CANDIDATE_SOURCE_HEADERS
from wv_eleicoes_data.ingestion.tse import persistence, pipeline
from wv_eleicoes_data.ingestion.tse.connector import (
    TseCandidatesConnector,
    TseResourceMetadata,
)
from wv_eleicoes_data.ingestion.tse.contracts import CANDIDATES_2026


@pytest.fixture
def engine():
    engine = sa.create_engine("sqlite://")
    # SQLite's INTEGER PK is the local equivalent of PostgreSQL BIGSERIAL.
    metadata = sa.MetaData()
    for model in (IngestionRun, TseCandidate):
        table = model.__table__.to_metadata(metadata)
        table.c.id.type = sa.Integer()
    with engine.begin() as connection:
        connection.exec_driver_sql("ATTACH DATABASE ':memory:' AS audit")
        connection.exec_driver_sql("ATTACH DATABASE ':memory:' AS raw")
        metadata.create_all(connection)
    yield engine
    engine.dispose()


@pytest.fixture
def artifact(tmp_path):
    values = ["#NULO", "#NE", "NÃO DIVULGÁVEL", "-1", "-3", "-4", "", "000123", " Á "]
    row = [values[i % len(values)] for i in range(50)]
    row[:2] = ["12/09/2026", "10:11:12"]
    row[17] = " Nome\r\ncom continuação "
    row[20] = "00000000001"
    row[21] = " internal@example.test "
    row[37] = "000000000002"
    stream = StringIO(newline="")
    writer = csv.writer(stream, delimiter=";", lineterminator="\r\n")
    writer.writerow(CANDIDATES_2026.expected_headers)
    writer.writerows([row] * 5)
    path = tmp_path / "source.zip"
    with ZipFile(path, "w") as archive:
        archive.writestr(CANDIDATES_2026.canonical_csv_name, stream.getvalue().encode("latin-1"))
    metadata = TseResourceMetadata(
        "id", "package", "name", "https://example.test", "application/zip"
    )
    return TseCandidatesConnector().inspect_artifact(path, metadata), row


def test_success_repeat_preservation_and_batches(engine, artifact):
    snapshot, row = artifact
    batches = []

    def track(conn, cursor, statement, parameters, context, executemany):
        if statement.startswith("INSERT INTO raw.tse_candidate"):
            batches.append(len(parameters) if executemany else 1)

    sa.event.listen(engine, "before_cursor_execute", track)
    with (
        patch.object(TseCandidatesConnector, "fetch", return_value=snapshot),
        patch.object(persistence, "lock_artifact") as lock,
    ):
        run_id, status = pipeline.run_pipeline(engine, batch_size=2)
        repeat_id, repeat_status = pipeline.run_pipeline(engine, batch_size=2)
    assert (status, repeat_status) == ("success", "skipped")
    assert lock.call_count == 2
    assert batches == [2, 2, 1]
    with engine.connect() as connection:
        rows = connection.execute(sa.select(TseCandidate)).mappings().all()
        assert len(rows) == 5
        assert [r["source_row_number"] for r in rows] == [2, 4, 6, 8, 10]
        for stored in rows:
            assert [stored[key] for key in TSE_CANDIDATE_SOURCE_HEADERS] == row
            assert stored["source_file"] == CANDIDATES_2026.canonical_csv_name
            assert stored["ingestion_run_id"] == run_id
        runs = (
            connection.execute(sa.select(IngestionRun).order_by(IngestionRun.id)).mappings().all()
        )
        assert runs[1]["id"] == repeat_id
        for run, count in zip(runs, [5, 0], strict=True):
            assert run["finished_at"] is not None
            assert run["source_updated_at"] is not None
            assert run["checksum"] == snapshot.sha256
            assert run["rows_downloaded"] == 5
            assert run["rows_inserted"] == count
            assert run["rows_updated"] == run["rows_rejected"] == 0


@pytest.mark.parametrize("after_insert", [False, True])
def test_failure_is_observable_and_raw_rolls_back(engine, artifact, after_insert):
    snapshot, _ = artifact

    def fetch(directory: Path):
        with engine.connect() as connection:
            assert connection.scalar(sa.select(IngestionRun.status)) == "running"
        if not after_insert:
            raise RuntimeError("secret source row or credential")
        return snapshot

    def fail_on_second_batch(conn, cursor, statement, parameters, context, executemany):
        if statement.startswith("INSERT INTO raw.tse_candidate"):
            count = conn.scalar(sa.select(sa.func.count()).select_from(TseCandidate))
            if count:
                raise RuntimeError("secret source row or credential")

    sa.event.listen(engine, "before_cursor_execute", fail_on_second_batch)
    with (
        patch.object(TseCandidatesConnector, "fetch", side_effect=fetch),
        patch.object(persistence, "lock_artifact"),
        pytest.raises(RuntimeError),
    ):
        pipeline.run_pipeline(engine, batch_size=2)
    with engine.connect() as connection:
        assert connection.scalar(sa.select(sa.func.count()).select_from(TseCandidate)) == 0
        run = connection.execute(sa.select(IngestionRun)).mappings().one()
        assert run["status"] == "failed"
        assert run["finished_at"] is not None
        assert "secret" not in run["error_message"]
        assert len(run["error_message"]) < 200


def test_cli_help_and_no_owner_fallback(monkeypatch, capsys):
    with pytest.raises(SystemExit) as result:
        pipeline.main(["--help"])
    assert result.value.code == 0
    monkeypatch.delenv("WV_ELEICOES_INGESTION_DATABASE_URL", raising=False)
    monkeypatch.setenv("WV_ELEICOES_DATABASE_URL", "postgresql://owner:secret@localhost/db")
    with patch.object(pipeline, "create_engine") as create:
        assert pipeline.main([]) == 2
        create.assert_not_called()
    output = capsys.readouterr().out
    assert "WV_ELEICOES_INGESTION_DATABASE_URL" in output
    assert "secret" not in output


def test_postgresql_lock_is_stable_and_parameterized():
    from unittest.mock import MagicMock

    connection = MagicMock()
    persistence.lock_artifact(connection, CANDIDATES_2026, "abc")
    first = connection.execute.call_args
    persistence.lock_artifact(connection, CANDIDATES_2026, "abc")
    assert first.args[1] == connection.execute.call_args.args[1]
    assert str(first.args[0]) == "SELECT pg_advisory_xact_lock(:key)"
    assert -(2**63) <= first.args[1]["key"] < 2**63
