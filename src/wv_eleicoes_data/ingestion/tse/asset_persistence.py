"""Transactional, temporal RAW persistence for TSE declared assets."""

import csv
import hashlib
import json
from collections.abc import Mapping
from datetime import UTC, datetime
from io import TextIOWrapper
from zipfile import ZipFile

from sqlalchemy import Connection, Engine, insert, select, text, update

from wv_eleicoes_data.db.models import (
    AssetChange,
    IngestionRun,
    TseCandidate,
    TseCandidateAsset,
)
from wv_eleicoes_data.db.models.tse_candidate_asset import TSE_ASSET_SOURCE_HEADERS
from wv_eleicoes_data.ingestion.tse.connector import TseArtifact, TseIngestionError
from wv_eleicoes_data.ingestion.tse.contracts import TseResourceContract

ASSET_KEY_FIELDS = (
    "ano_eleicao",
    "cd_eleicao",
    "sq_candidato",
    "nr_ordem_bem_candidato",
)
CANDIDACY_KEY_FIELDS = ("ano_eleicao", "cd_eleicao", "sq_candidato")
SENTINELS = {"", "#NULO", "#NE", "NÃO DIVULGÁVEL", "-1", "-3", "-4"}
IGNORED_CHANGE_FIELDS = {"dt_geracao", "hh_geracao"}


def start_run(engine: Engine, contract: TseResourceContract) -> int:
    """Create one scoped audit run for the declared-assets dataset."""

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
    """Mark an asset run failed without persisting exception text or row values."""

    with engine.begin() as connection:
        connection.execute(
            update(IngestionRun)
            .where(IngestionRun.id == run_id)
            .values(
                status="failed",
                finished_at=datetime.now(UTC),
                error_message="Declared-assets ingestion failed; RAW transaction rolled back.",
            )
        )


def lock_artifact(connection: Connection, contract: TseResourceContract, checksum: str) -> None:
    """Serialize one source/dataset/election-year partition until commit."""

    del checksum
    key = int.from_bytes(
        hashlib.sha256(
            f"{contract.source}\0{contract.dataset}\0{contract.scope_key}".encode()
        ).digest()[:8],
        signed=True,
    )
    connection.execute(text("SELECT pg_advisory_xact_lock(:key)"), {"key": key})


def content_hash(source: Mapping[str, object]) -> str:
    """Hash exact source values except artifact-generation timestamp fields."""

    values = [
        source[name]
        for name in TSE_ASSET_SOURCE_HEADERS
        if name not in IGNORED_CHANGE_FIELDS
    ]
    return hashlib.sha256(
        json.dumps(values, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


def changed_fields(
    previous: Mapping[str, object],
    incoming: Mapping[str, object],
) -> list[str]:
    """Return changed official headers in frozen source-column order."""

    return [
        official_header
        for name, official_header in TSE_ASSET_SOURCE_HEADERS.items()
        if name not in IGNORED_CHANGE_FIELDS and previous[name] != incoming[name]
    ]


def _source_values(connection: Connection, raw_asset_id: int) -> Mapping[str, object]:
    columns = [
        getattr(TseCandidateAsset, name).label(name) for name in TSE_ASSET_SOURCE_HEADERS
    ]
    row = connection.execute(
        select(*columns).where(TseCandidateAsset.id == raw_asset_id)
    ).mappings().one()
    return dict(row)


def _active_candidate_keys(
    connection: Connection,
    election_year: int,
) -> set[tuple[str, str, str]]:
    """Return active candidacy natural keys required by the assets snapshot."""

    return {
        (str(year), str(election), str(sequence))
        for year, election, sequence in connection.execute(
            select(
                TseCandidate.ano_eleicao,
                TseCandidate.cd_eleicao,
                TseCandidate.sq_candidato,
            ).where(
                TseCandidate.valid_to_run_id.is_(None),
                TseCandidate.ano_eleicao == str(election_year),
            )
        )
    }


def _validate_key(
    source: Mapping[str, str],
    contract: TseResourceContract,
    seen: set[tuple[str, str, str, str]],
    candidate_keys: set[tuple[str, str, str]],
) -> tuple[str, str, str, str]:
    key = (
        source["ano_eleicao"],
        source["cd_eleicao"],
        source["sq_candidato"],
        source["nr_ordem_bem_candidato"],
    )
    if any(value.strip() in SENTINELS for value in key):
        raise TseIngestionError("Invalid declared-asset natural key")
    if key in seen:
        raise TseIngestionError("Duplicate declared-asset natural key")
    if source["ano_eleicao"] != str(contract.election_year):
        raise TseIngestionError("Unexpected declared-assets election year")

    order = source["nr_ordem_bem_candidato"].strip()
    if not order.isdigit() or int(order) <= 0:
        raise TseIngestionError("Invalid declared-asset order")

    candidacy_key = (
        source["ano_eleicao"],
        source["cd_eleicao"],
        source["sq_candidato"],
    )
    if candidacy_key not in candidate_keys:
        raise TseIngestionError("Declared asset references unknown active candidacy")
    return key


def insert_rows(
    connection: Connection,
    artifact: TseArtifact,
    contract: TseResourceContract,
    run_id: int,
    batch_size: int,
) -> tuple[int, int, int, int]:
    """Apply one complete annual assets snapshot as temporal A/M/D changes."""

    if not 1 <= batch_size <= 1000:
        raise ValueError("batch_size must be between 1 and 1000")

    candidate_keys = _active_candidate_keys(connection, contract.election_year)
    if not candidate_keys:
        raise TseIngestionError("No active candidacies loaded for declared-assets election year")

    current: dict[tuple[str, str, str, str], tuple[int, str]] = {}
    for stored in connection.execute(
        select(TseCandidateAsset).where(
            TseCandidateAsset.valid_to_run_id.is_(None),
            TseCandidateAsset.ano_eleicao == str(contract.election_year),
        )
    ).mappings():
        key = (
            str(stored["ano_eleicao"]),
            str(stored["cd_eleicao"]),
            str(stored["sq_candidato"]),
            str(stored["nr_ordem_bem_candidato"]),
        )
        current[key] = (int(stored["id"]), str(stored["content_hash"]))

    seen: set[tuple[str, str, str, str]] = set()
    added = modified = unchanged = count = 0
    batch: list[dict[str, object]] = []
    changes: list[dict[str, object]] = []

    def flush() -> None:
        if not batch:
            return
        ids = (
            connection.execute(
                insert(TseCandidateAsset).returning(
                    TseCandidateAsset.id,
                    sort_by_parameter_order=True,
                ),
                batch,
            )
            .scalars()
            .all()
        )
        for change, new_id in zip(changes, ids, strict=True):
            change["new_raw_asset_id"] = new_id
        connection.execute(insert(AssetChange), changes)
        batch.clear()
        changes.clear()

    with (
        ZipFile(artifact.path) as archive,
        archive.open(artifact.canonical_csv_name) as raw,
        TextIOWrapper(raw, encoding=contract.encoding, newline="") as stream,
    ):
        reader = csv.reader(
            stream,
            delimiter=contract.delimiter,
            quotechar=contract.quotechar,
            strict=True,
        )
        if tuple(next(reader)) != tuple(TSE_ASSET_SOURCE_HEADERS.values()):
            raise TseIngestionError("Unexpected declared-assets source headers")

        while True:
            line_number = reader.line_num + 1
            row = next(reader, None)
            if row is None:
                break
            if len(row) != len(TSE_ASSET_SOURCE_HEADERS):
                raise TseIngestionError("Unexpected declared-assets source column count")

            source = dict(zip(TSE_ASSET_SOURCE_HEADERS, row, strict=True))
            key = _validate_key(source, contract, seen, candidate_keys)
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
                    raise TseIngestionError(
                        "Declared-asset hash changed without source-field delta"
                    )
                modified += 1
                connection.execute(
                    update(TseCandidateAsset)
                    .where(TseCandidateAsset.id == old[0])
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
                    zip(ASSET_KEY_FIELDS, key, strict=True),
                    run_id=run_id,
                    change_type="M" if old else "A",
                    old_raw_asset_id=old[0] if old else None,
                    source_snapshot_at=artifact.source_updated_at,
                    changed_fields=fields,
                )
            )
            if len(batch) == batch_size:
                flush()
        flush()

    if count != artifact.row_count:
        raise TseIngestionError("Declared-assets source row count changed")

    for key, old in current.items():
        connection.execute(
            update(TseCandidateAsset)
            .where(TseCandidateAsset.id == old[0])
            .values(valid_to_run_id=run_id)
        )
        connection.execute(
            insert(AssetChange).values(
                **dict(zip(ASSET_KEY_FIELDS, key, strict=True)),
                run_id=run_id,
                change_type="D",
                old_raw_asset_id=old[0],
                new_raw_asset_id=None,
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
    """Persist one snapshot transactionally and finalize its audit counters."""

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
            .order_by(
                IngestionRun.finished_at.desc().nulls_last(),
                IngestionRun.id.desc(),
            )
            .limit(1)
        )
        skip = previous == artifact.sha256
        status = "skipped" if skip else "success"
        added, modified, removed, unchanged = (
            (0, 0, 0, 0)
            if skip
            else insert_rows(connection, artifact, contract, run_id, batch_size)
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
    return status
