from datetime import UTC, datetime
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
from unittest.mock import patch

import pytest
import sqlalchemy as sa
from alembic.config import Config
from alembic.migration import MigrationContext
from alembic.operations import Operations
from alembic.script import ScriptDirectory
from sqlalchemy.dialects import postgresql

from wv_eleicoes_data.db.base import Base
from wv_eleicoes_data.db.models import TseCandidate
from wv_eleicoes_data.db.models.tse_candidate import TSE_CANDIDATE_SOURCE_HEADERS
from wv_eleicoes_data.ingestion.tse.contracts import TSE_CANDIDATES_2026_HEADERS

TABLE = TseCandidate.__table__
PROVENANCE = {"id", "ingestion_run_id", "source_file", "source_row_number", "ingested_at"}


def test_metadata_and_complete_source_mapping() -> None:
    assert TABLE.schema == "raw"
    assert TABLE.name == "tse_candidate"
    assert Base.metadata.tables["raw.tse_candidate"] is TABLE
    source_names = (
        set(TABLE.columns.keys())
        - PROVENANCE
        - {"valid_from_run_id", "valid_to_run_id", "content_hash"}
    )
    assert len(source_names) == len(TSE_CANDIDATES_2026_HEADERS) == 50
    assert len(set(TSE_CANDIDATES_2026_HEADERS)) == 50
    assert source_names == set(TSE_CANDIDATE_SOURCE_HEADERS)
    assert tuple(TSE_CANDIDATE_SOURCE_HEADERS.values()) == TSE_CANDIDATES_2026_HEADERS
    for attribute, header in TSE_CANDIDATE_SOURCE_HEADERS.items():
        assert attribute == header.lower()
        assert getattr(TseCandidate, attribute).property.columns[0] is TABLE.c[attribute]
        assert isinstance(TABLE.c[attribute].type, sa.Text)
        assert not TABLE.c[attribute].nullable


def test_provenance_and_identity() -> None:
    assert list(TABLE.primary_key.columns.keys()) == ["id"]
    assert TABLE.c.id.autoincrement is True
    for name in PROVENANCE:
        assert not TABLE.c[name].nullable
    (fk,) = TABLE.c.ingestion_run_id.foreign_keys
    assert fk.target_fullname == "audit.ingestion_run.id"
    assert fk.column is Base.metadata.tables["audit.ingestion_run"].c.id
    (unique,) = [c for c in TABLE.constraints if isinstance(c, sa.UniqueConstraint)]
    assert list(unique.columns.keys()) == ["ingestion_run_id", "source_file", "source_row_number"]
    assert {index.name for index in TABLE.indexes} == {"uq_tse_candidate_active"}
    assert isinstance(TABLE.c.ingested_at.type, sa.DateTime)
    assert TABLE.c.ingested_at.type.timezone
    assert TABLE.c.ingested_at.server_default is not None


def test_lossless_storage_and_provenance_uniqueness() -> None:
    # SQLite exercises storage/uniqueness locally; PostgreSQL DDL is checked below.
    engine = sa.create_engine("sqlite://")
    values = ["#NULO", "#NE", "NÃO DIVULGÁVEL", "-1", "-3", "-4", "", "000123", "  Á  "]
    payload = {name: values[i % len(values)] for i, name in enumerate(TSE_CANDIDATE_SOURCE_HEADERS)}
    with engine.begin() as connection:
        connection.exec_driver_sql("ATTACH DATABASE ':memory:' AS raw")
        TABLE.create(connection)
        row = dict(
            payload,
            id=1,
            ingestion_run_id=1,
            valid_from_run_id=1,
            valid_to_run_id=2,
            source_file="consulta_cand_2026_BRASIL.csv",
            source_row_number=1,
            ingested_at=datetime.now(UTC),
        )
        connection.execute(TABLE.insert(), row)
        stored = connection.execute(sa.select(TABLE)).mappings().one()
        assert {name: stored[name] for name in payload} == payload
        with pytest.raises(sa.exc.IntegrityError):
            connection.execute(TABLE.insert(), dict(row, id=2))
        connection.execute(TABLE.insert(), dict(row, id=3, ingestion_run_id=2))
        connection.execute(TABLE.insert(), dict(row, id=4, source_row_number=2))
        connection.execute(TABLE.insert(), dict(row, id=5, source_file="another.csv"))
        assert connection.scalar(sa.select(sa.func.count()).select_from(TABLE)) == 4


def test_frozen_migration_ddl_and_linear_history() -> None:
    scripts = ScriptDirectory.from_config(Config("alembic.ini"))
    assert len(scripts.get_heads()) == 1
    revision = scripts.get_revision("8c31b79e5a02")
    assert revision is not None
    assert revision.down_revision == "2ae610ff28cd"
    spec = spec_from_file_location("raw_migration", Path(revision.path))
    assert spec is not None and spec.loader is not None
    migration = module_from_spec(spec)
    spec.loader.exec_module(migration)
    statements: list[str] = []
    engine = sa.create_mock_engine(
        "postgresql://",
        lambda sql, *args, **kwargs: statements.append(
            str(sql.compile(dialect=postgresql.dialect()))
        ),
    )
    operations = Operations(MigrationContext.configure(engine.connect()))
    with patch.object(migration, "op", operations):
        migration.upgrade()
        migration.downgrade()
    # This fixture belongs to this revision, independently of future ORM/contracts.
    expected = (Path(__file__).parent / "fixtures" / "8c31b79e5a02.sql").read_text()
    assert len(statements) == 2
    # Constraint ordering is immaterial and may differ between metadata instances.
    actual_lines = statements[0].strip().splitlines()
    assert sorted(line.strip().rstrip(",") for line in actual_lines) == sorted(
        line.strip().rstrip(",") for line in expected.strip().splitlines()
    )
    assert statements[1].strip() == "DROP TABLE raw.tse_candidate"
