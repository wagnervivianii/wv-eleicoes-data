"""Transactional audit and bounded, source-faithful RAW persistence."""

import csv
import hashlib
import json
from collections.abc import Mapping
from datetime import UTC, datetime
from io import TextIOWrapper
from zipfile import ZipFile

from sqlalchemy import Connection, Engine, insert, select, text, update

from wv_eleicoes_data.db.models import CandidateChange, IngestionRun, TseCandidate
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
                    scope_key=contract.scope_key,
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
    """Serialize one source/dataset/election-year partition until commit.

    The checksum parameter remains part of the public helper signature because callers
    already pass it, but the lock intentionally represents the logical partition,
    not one artifact revision.
    """
    del checksum
    key = int.from_bytes(
        hashlib.sha256(
            f"{contract.source}\0{contract.dataset}\0{contract.scope_key}".encode()
        ).digest()[:8],
        signed=True,
    )
    connection.execute(text("SELECT pg_advisory_xact_lock(:key)"), {"key": key})


KEY_FIELDS = ("ano_eleicao", "cd_eleicao", "sq_candidato")
SENTINELS = {"", "#NULO", "#NE", "NÃO DIVULGÁVEL", "-1", "-3", "-4"}
IGNORED_CHANGE_FIELDS = {"dt_geracao", "hh_geracao"}


def content_hash(source: Mapping[str, object]) -> str:
    """SHA-256 of compact UTF-8 JSON array in official column order, without generation time."""
    values = [
        source[name]
        for name in TSE_CANDIDATE_SOURCE_HEADERS
        if name not in IGNORED_CHANGE_FIELDS
    ]
    return hashlib.sha256(
        json.dumps(values, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


def changed_fields(
    previous: Mapping[str, object],
    incoming: Mapping[str, object],
) -> list[str]:
    """Return exact official headers that changed, in official source-column order."""
    return [
        official_header
        for name, official_header in TSE_CANDIDATE_SOURCE_HEADERS.items()
        if name not in IGNORED_CHANGE_FIELDS and previous[name] != incoming[name]
    ]


def sync_person_identity(connection: Connection) -> int:
    """Reconcile all successful TSE candidacies into the stable person identity graph.

    Production ingestion is PostgreSQL-only. SQLite is used by fast unit tests and
    cannot execute the PostgreSQL SECURITY DEFINER function, so it deliberately
    returns zero there.
    """
    if connection.dialect.name != "postgresql":
        return 0
    value = connection.scalar(text("SELECT core.sync_person_identity_from_tse()"))
    return int(value or 0)


def _source_values(connection: Connection, raw_candidate_id: int) -> Mapping[str, object]:
    columns = [getattr(TseCandidate, name).label(name) for name in TSE_CANDIDATE_SOURCE_HEADERS]
    row = connection.execute(
        select(*columns).where(TseCandidate.id == raw_candidate_id)
    ).mappings().one()
    return dict(row)


def insert_rows(
    connection: Connection,
    artifact: TseArtifact,
    contract: TseResourceContract,
    run_id: int,
    batch_size: int,
) -> tuple[int, int, int, int]:
    if not 1 <= batch_size <= 1000:
        raise ValueError("batch_size must be between 1 and 1000")
    current = {}
    for stored in connection.execute(
        select(TseCandidate).where(
            TseCandidate.valid_to_run_id.is_(None),
            TseCandidate.ano_eleicao == str(contract.election_year),
        )
    ).mappings():
        key = tuple(stored[name] for name in KEY_FIELDS)
        current[key] = (
            stored["id"],
            stored["content_hash"]
            or content_hash({name: stored[name] for name in TSE_CANDIDATE_SOURCE_HEADERS}),
        )
        if stored["content_hash"] is None:
            connection.execute(
                update(TseCandidate)
                .where(TseCandidate.id == stored["id"])
                .values(content_hash=current[key][1])
            )
    seen = set()
    added = modified = unchanged = count = 0
    batch: list[dict[str, object]] = []
    changes: list[dict[str, object]] = []

    def flush() -> None:
        if not batch:
            return
        ids = (
            connection.execute(
                insert(TseCandidate).returning(TseCandidate.id, sort_by_parameter_order=True), batch
            )
            .scalars()
            .all()
        )
        for change, new_id in zip(changes, ids, strict=True):
            change["new_raw_candidate_id"] = new_id
        connection.execute(insert(CandidateChange), changes)
        batch.clear()
        changes.clear()

    with (
        ZipFile(artifact.path) as archive,
        archive.open(artifact.canonical_csv_name) as raw,
        TextIOWrapper(raw, encoding=contract.encoding, newline="") as stream,
    ):
        reader = csv.reader(
            stream, delimiter=contract.delimiter, quotechar=contract.quotechar, strict=True
        )
        if tuple(next(reader)) != tuple(TSE_CANDIDATE_SOURCE_HEADERS.values()):
            raise TseIngestionError("Unexpected source headers")
        while True:
            line_number = reader.line_num + 1
            row = next(reader, None)
            if row is None:
                break
            if len(row) != len(TSE_CANDIDATE_SOURCE_HEADERS):
                raise TseIngestionError("Unexpected source column count")
            source = dict(zip(TSE_CANDIDATE_SOURCE_HEADERS, row, strict=True))
            key = tuple(source[name] for name in KEY_FIELDS)
            if any(value.strip() in SENTINELS for value in key) or key in seen:
                raise TseIngestionError("Invalid or duplicate candidacy key")
            if source["ano_eleicao"] != str(contract.election_year):
                raise TseIngestionError("Unexpected election year")
            seen.add(key)
            count += 1
            digest = content_hash(source)
            old = current.pop(key, None)
            if old is not None and old[1] == digest:
                unchanged += 1
                continue

            fields: list[str] | None = None
            if old is not None:
                fields = changed_fields(_source_values(connection, old[0]), source)
                if not fields:
                    raise TseIngestionError("Candidate hash changed without source-field delta")
                modified += 1
                connection.execute(
                    update(TseCandidate)
                    .where(TseCandidate.id == old[0])
                    .values(valid_to_run_id=run_id)
                )
            else:
                added += 1

            batch.append(
                dict(
                    source,
                    ingestion_run_id=run_id,
                    valid_from_run_id=run_id,
                    content_hash=digest,
                    source_file=artifact.canonical_csv_name,
                    source_row_number=line_number,
                )
            )
            changes.append(
                dict(
                    zip(KEY_FIELDS, key, strict=True),
                    run_id=run_id,
                    change_type="M" if old else "A",
                    old_raw_candidate_id=old[0] if old else None,
                    source_snapshot_at=artifact.source_updated_at,
                    changed_fields=fields,
                )
            )
            if len(batch) == batch_size:
                flush()
        flush()
    if count != artifact.row_count:
        raise TseIngestionError("Source row count changed")
    for key, old in current.items():
        connection.execute(
            update(TseCandidate).where(TseCandidate.id == old[0]).values(valid_to_run_id=run_id)
        )
        connection.execute(
            insert(CandidateChange).values(
                **dict(zip(KEY_FIELDS, key, strict=True)),
                run_id=run_id,
                change_type="D",
                old_raw_candidate_id=old[0],
                new_raw_candidate_id=None,
                source_snapshot_at=artifact.source_updated_at,
                changed_fields=None,
            )
        )
    return added, modified, len(current), unchanged


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
            select(IngestionRun.checksum)
            .where(
                IngestionRun.source == contract.source,
                IngestionRun.dataset == contract.dataset,
                IngestionRun.scope_key == contract.scope_key,
                IngestionRun.status == "success",
            )
            .order_by(IngestionRun.finished_at.desc().nulls_last(), IngestionRun.id.desc())
            .limit(1)
        )
        # Run IDs reflect start order; completion under the scoped lock is apply order.
        skip = previous == artifact.sha256
        status = "skipped" if skip else "success"
        added, modified, removed, unchanged = (
            (0, 0, 0, 0)
            if skip
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
                rows_inserted=added + modified,
                rows_updated=modified,
                rows_added=added,
                rows_removed=removed,
                rows_unchanged=unchanged,
                rows_rejected=0,
            )
        )
        if not skip:
            sync_person_identity(connection)
    return status
