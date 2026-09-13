import csv
from io import StringIO
from pathlib import Path
from unittest.mock import patch
from zipfile import ZipFile

import pytest
import sqlalchemy as sa

from wv_eleicoes_data.db.models import CandidateChange, IngestionRun, TseCandidate
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
    for model in (IngestionRun, TseCandidate, CandidateChange):
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
    row[2], row[6] = "2026", "123"
    for i in range(5):
        row[15] = str(i)
        writer.writerow(row)
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
            batches.append(
                len(context.compiled_parameters)
                if context.execute_style.name != "INSERTMANYVALUES"
                else 1
            )

    sa.event.listen(engine, "before_cursor_execute", track)
    with (
        patch.object(TseCandidatesConnector, "fetch", return_value=snapshot),
        patch.object(persistence, "lock_artifact") as lock,
    ):
        run_id, status = pipeline.run_pipeline(engine, batch_size=2)
        repeat_id, repeat_status = pipeline.run_pipeline(engine, batch_size=2)
    assert (status, repeat_status) == ("success", "skipped")
    assert lock.call_count == 2
    assert sum(batches) == 5
    assert max(batches) <= 2
    with engine.connect() as connection:
        rows = connection.execute(sa.select(TseCandidate)).mappings().all()
        assert len(rows) == 5
        assert [r["source_row_number"] for r in rows] == [2, 4, 6, 8, 10]
        for i, stored in enumerate(rows):
            row[15] = str(i)
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


def make_snapshot(tmp_path, rows):
    stream = StringIO(newline="")
    writer = csv.writer(stream, delimiter=";", lineterminator="\r\n")
    writer.writerow(CANDIDATES_2026.expected_headers)
    writer.writerows(rows)
    path = tmp_path / "diff.zip"
    with ZipFile(path, "w") as archive:
        archive.writestr(CANDIDATES_2026.canonical_csv_name, stream.getvalue().encode("latin-1"))
    return TseCandidatesConnector().inspect_artifact(
        path,
        TseResourceMetadata("id", "package", "name", "https://example.test", "application/zip"),
    )


def ingest(engine, snapshot):
    with (
        patch.object(TseCandidatesConnector, "fetch", return_value=snapshot),
        patch.object(persistence, "lock_artifact"),
    ):
        return pipeline.run_pipeline(engine, batch_size=2)


def test_regeneration_and_mixed_diff(engine, artifact, tmp_path):
    snapshot, template = artifact
    first, _ = ingest(engine, snapshot)
    rows = []
    for i in range(5):
        row = template.copy()
        row[15] = str(i)
        row[1] = "11:12:13"
        rows.append(row)
    regenerated, status = ingest(engine, make_snapshot(tmp_path, rows))
    assert status == "success"
    with engine.connect() as conn:
        run = (
            conn.execute(sa.select(IngestionRun).where(IngestionRun.id == regenerated))
            .mappings()
            .one()
        )
        assert run["rows_unchanged"] == 5
        assert run["rows_inserted"] == run["rows_updated"] == 0
        assert (
            conn.scalar(
                sa.select(sa.func.count())
                .select_from(CandidateChange)
                .where(CandidateChange.run_id == regenerated)
            )
            == 0
        )
    rows[0][17] = "Substantive change"
    rows[1][15] = "new"
    mixed, _ = ingest(engine, make_snapshot(tmp_path, rows))
    with engine.connect() as conn:
        run = conn.execute(sa.select(IngestionRun).where(IngestionRun.id == mixed)).mappings().one()
        assert [
            run[name]
            for name in (
                "rows_added",
                "rows_updated",
                "rows_removed",
                "rows_unchanged",
                "rows_inserted",
            )
        ] == [1, 1, 1, 3, 2]
        changes = (
            conn.execute(sa.select(CandidateChange).where(CandidateChange.run_id == mixed))
            .mappings()
            .all()
        )
        assert sorted(c["change_type"] for c in changes) == ["A", "D", "M"]
        active = (
            conn.execute(sa.select(TseCandidate).where(TseCandidate.valid_to_run_id.is_(None)))
            .mappings()
            .all()
        )
        assert {r["sq_candidato"] for r in active} == {"0", "new", "2", "3", "4"}
        assert sum(r["ingestion_run_id"] == first for r in active) == 3
        assert conn.scalar(sa.select(sa.func.count()).select_from(TseCandidate)) == 7
        for change in changes:
            if change["old_raw_candidate_id"]:
                assert (
                    conn.scalar(
                        sa.select(TseCandidate.valid_to_run_id).where(
                            TseCandidate.id == change["old_raw_candidate_id"]
                        )
                    )
                    == mixed
                )


@pytest.mark.parametrize(
    "invalid", ["duplicate", "", " #NULO ", "#NE", "-1", "-3", "-4", "NÃO DIVULGÁVEL"]
)
def test_invalid_keys_rollback_diff(engine, artifact, tmp_path, invalid):
    snapshot, template = artifact
    ingest(engine, snapshot)
    rows = []
    for i in range(3):
        row = template.copy()
        row[15] = str(i)
        row[17] = "changed"
        rows.append(row)
    rows[-1][15] = "0" if invalid == "duplicate" else invalid
    with pytest.raises(persistence.TseIngestionError):
        ingest(engine, make_snapshot(tmp_path, rows))
    with engine.connect() as conn:
        assert conn.scalar(sa.select(sa.func.count()).select_from(TseCandidate)) == 5
        assert (
            conn.scalar(
                sa.select(sa.func.count())
                .select_from(TseCandidate)
                .where(TseCandidate.valid_to_run_id.is_not(None))
            )
            == 0
        )
        assert conn.scalar(sa.select(sa.func.count()).select_from(CandidateChange)) == 5


def test_dataset_lock_serializes_different_checksums():
    from unittest.mock import MagicMock

    connection = MagicMock()
    persistence.lock_artifact(connection, CANDIDATES_2026, "abc")
    first = connection.execute.call_args.args[1]
    persistence.lock_artifact(connection, CANDIDATES_2026, "def")
    assert first == connection.execute.call_args.args[1]


def test_hash_bootstrap_and_active_uniqueness(engine, artifact, tmp_path):
    snapshot, template = artifact
    ingest(engine, snapshot)
    with engine.begin() as conn:
        conn.execute(sa.update(TseCandidate).values(content_hash=None))
    rows = []
    for i in range(5):
        row = template.copy()
        row[15] = str(i)
        row[0] = "13/09/2026"
        rows.append(row)
    run_id, _ = ingest(engine, make_snapshot(tmp_path, rows))
    with engine.begin() as conn:
        assert (
            conn.scalar(sa.select(IngestionRun.rows_unchanged).where(IngestionRun.id == run_id))
            == 5
        )
        assert (
            conn.scalar(
                sa.select(sa.func.count())
                .select_from(TseCandidate)
                .where(TseCandidate.content_hash.is_(None))
            )
            == 0
        )
        row = dict(conn.execute(sa.select(TseCandidate)).mappings().first())
        row.pop("id")
        row["source_row_number"] = 999
        with pytest.raises(sa.exc.IntegrityError):
            conn.execute(sa.insert(TseCandidate).values(**row))


def test_hash_preserves_exact_values_and_boundaries():
    source = dict.fromkeys(TSE_CANDIDATE_SOURCE_HEADERS, "")
    digest = persistence.content_hash(source)
    source.update(dt_geracao="different", hh_geracao="different")
    assert persistence.content_hash(source) == digest
    source["nm_candidato"] = " "
    assert persistence.content_hash(source) != digest
    source.update(nm_candidato="ab", nm_urna_candidato="c")
    first = persistence.content_hash(source)
    source.update(nm_candidato="a", nm_urna_candidato="bc")
    assert persistence.content_hash(source) != first


def test_historical_checksum_replay_restores_snapshot(engine, artifact, tmp_path):
    snapshot_a, template = artifact
    ingest(engine, snapshot_a)
    rows = [template.copy() for _ in range(5)]
    for i, row in enumerate(rows):
        row[15] = str(i)
    rows[0][17] = "Changed name"
    rows[1][15] = "new"
    ingest(engine, make_snapshot(tmp_path, rows))
    replay, status = ingest(engine, snapshot_a)
    assert status == "success"
    with engine.connect() as conn:
        active = (
            conn.execute(sa.select(TseCandidate).where(TseCandidate.valid_to_run_id.is_(None)))
            .mappings()
            .all()
        )
        assert {row["sq_candidato"] for row in active} == {str(i) for i in range(5)}
        for stored in active:
            expected = template.copy()
            expected[15] = stored["sq_candidato"]
            assert [stored[key] for key in TSE_CANDIDATE_SOURCE_HEADERS] == expected
        changes = (
            conn.execute(
                sa.select(CandidateChange.change_type).where(CandidateChange.run_id == replay)
            )
            .scalars()
            .all()
        )
        assert sorted(changes) == ["A", "D", "M"]
    assert ingest(engine, snapshot_a)[1] == "skipped"


def test_snapshot_preserves_other_election(engine, artifact):
    snapshot, template = artifact
    legacy_run = persistence.start_run(engine, CANDIDATES_2026)
    payload = dict(zip(TSE_CANDIDATE_SOURCE_HEADERS, template, strict=True))
    payload["ano_eleicao"] = "2022"
    with engine.begin() as conn:
        other_id = conn.scalar(
            sa.insert(TseCandidate)
            .values(
                **payload,
                ingestion_run_id=legacy_run,
                valid_from_run_id=legacy_run,
                source_file="consulta_cand_2022_BRASIL.csv",
                source_row_number=2,
            )
            .returning(TseCandidate.id)
        )
    run_id, status = ingest(engine, snapshot)
    assert status == "success"
    with engine.connect() as conn:
        other = (
            conn.execute(sa.select(TseCandidate).where(TseCandidate.id == other_id))
            .mappings()
            .one()
        )
        assert other["valid_to_run_id"] is None
        assert other["content_hash"] is None
        assert (
            conn.scalar(sa.select(IngestionRun.rows_removed).where(IngestionRun.id == run_id)) == 0
        )
        assert (
            conn.scalar(
                sa.select(sa.func.count())
                .select_from(CandidateChange)
                .where(CandidateChange.ano_eleicao == "2022")
            )
            == 0
        )
