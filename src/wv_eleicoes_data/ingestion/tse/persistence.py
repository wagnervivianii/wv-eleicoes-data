"""Transactional audit and bounded, source-faithful RAW persistence."""

import csv
import hashlib
from datetime import UTC, datetime
from io import TextIOWrapper
from zipfile import ZipFile

from sqlalchemy import Connection, Engine, insert, select, text, update

from wv_eleicoes_data.db.models import IngestionRun, TseCandidate
from wv_eleicoes_data.db.models.tse_candidate import TSE_CANDIDATE_SOURCE_HEADERS
from wv_eleicoes_data.ingestion.tse.connector import TseArtifact, TseIngestionError
from wv_eleicoes_data.ingestion.tse.contracts import TseResourceContract


def start_run(engine: Engine, contract: TseResourceContract) -> int:
    with engine.begin() as connection:
        return int(
            connection.execute(
                insert(IngestionRun)
                .values(
                    source=contract.source,
                    dataset=contract.dataset,
                    status="running",
                )
                .returning(IngestionRun.id)
            ).scalar_one()
        )


def fail_run(engine: Engine, run_id: int) -> None:
    # Never retain exception text: DB exceptions can include SQL parameters/PII/URLs.
    with engine.begin() as connection:
        connection.execute(
            update(IngestionRun)
            .where(IngestionRun.id == run_id)
            .values(
                status="failed",
                finished_at=datetime.now(UTC),
                error_message="Candidates ingestion failed; RAW transaction rolled back.",
            )
        )


def lock_artifact(connection: Connection, contract: TseResourceContract, checksum: str) -> None:
    """Serialize identical artifacts until RAW and success status commit together.

    The runner uses READ COMMITTED so the lookup after waiting sees the winner.
    Hash collisions only serialize unrelated artifacts; they cannot skip them.
    """
    key = int.from_bytes(
        hashlib.sha256(f"{contract.source}\0{contract.dataset}\0{checksum}".encode()).digest()[:8],
        signed=True,
    )
    connection.execute(text("SELECT pg_advisory_xact_lock(:key)"), {"key": key})


def insert_rows(
    connection: Connection,
    artifact: TseArtifact,
    contract: TseResourceContract,
    run_id: int,
    batch_size: int,
) -> int:
    """Store decoded strings unchanged; row number is the physical starting line.

    newline='' preserves embedded CR/LF. A multiline record advances the next
    record's source_row_number by its physical line count, not by one.
    """
    batch: list[dict[str, str | int]] = []
    count = 0
    with (
        ZipFile(artifact.path) as archive,
        archive.open(artifact.canonical_csv_name) as raw,
        TextIOWrapper(raw, encoding=contract.encoding, newline="") as stream,
    ):
        reader = csv.reader(
            stream, delimiter=contract.delimiter, quotechar=contract.quotechar, strict=True
        )
        headers = next(reader)
        if tuple(headers) != tuple(TSE_CANDIDATE_SOURCE_HEADERS.values()):
            raise TseIngestionError("Unexpected source headers")
        while True:
            line_number = reader.line_num + 1
            row = next(reader, None)
            if row is None:
                break
            if len(row) != len(headers):
                raise TseIngestionError("Unexpected source column count")
            source = dict(zip(headers, row, strict=True))
            payload: dict[str, str | int] = {
                name: source[header] for name, header in TSE_CANDIDATE_SOURCE_HEADERS.items()
            }
            payload.update(
                ingestion_run_id=run_id,
                source_file=artifact.canonical_csv_name,
                source_row_number=line_number,
            )
            batch.append(payload)
            count += 1
            if len(batch) == batch_size:
                connection.execute(insert(TseCandidate), batch)
                batch = []
        if batch:
            connection.execute(insert(TseCandidate), batch)
    if count != artifact.row_count:
        raise TseIngestionError("Source row count changed")
    return count


def load_artifact(
    engine: Engine,
    artifact: TseArtifact,
    contract: TseResourceContract,
    run_id: int,
    batch_size: int,
) -> str:
    with engine.begin() as connection:
        lock_artifact(connection, contract, artifact.sha256)
        previous = connection.scalar(
            select(IngestionRun.id)
            .where(
                IngestionRun.source == contract.source,
                IngestionRun.dataset == contract.dataset,
                IngestionRun.checksum == artifact.sha256,
                IngestionRun.status == "success",
            )
            .limit(1)
        )
        status = "skipped" if previous is not None else "success"
        inserted = (
            0
            if previous is not None
            else insert_rows(
                connection,
                artifact,
                contract,
                run_id,
                batch_size,
            )
        )
        connection.execute(
            update(IngestionRun)
            .where(IngestionRun.id == run_id)
            .values(
                status=status,
                finished_at=datetime.now(UTC),
                source_updated_at=artifact.source_updated_at,
                checksum=artifact.sha256,
                rows_downloaded=artifact.row_count,
                rows_inserted=inserted,
                rows_updated=0,
                rows_rejected=0,
            )
        )
    return status
