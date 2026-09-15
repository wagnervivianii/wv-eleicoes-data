from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
from unittest.mock import patch

import pytest
import sqlalchemy as sa

from wv_eleicoes_data.db.base import Base
from wv_eleicoes_data.db.models import IngestionRun


def migration():
    path = next(Path("migrations/versions").glob("f8142026hi01_*.py"))
    spec = spec_from_file_location("historical_ingestion_scope_migration", path)
    assert spec is not None and spec.loader is not None
    module = module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_ingestion_run_model_has_scoped_audit_contract() -> None:
    table = IngestionRun.__table__
    assert Base.metadata.tables["audit.ingestion_run"] is table
    assert not table.c.scope_key.nullable
    assert table.c.scope_key.server_default is not None
    constraints = [
        constraint
        for constraint in table.constraints
        if isinstance(constraint, sa.CheckConstraint)
        and constraint.name == "ck_ingestion_run_scope_key_not_blank"
    ]
    assert len(constraints) == 1
    assert str(constraints[0].sqltext) == "trim(scope_key) <> ''"
    assert "ix_ingestion_run_source_dataset_scope_status" in {
        index.name for index in table.indexes
    }


def test_ingestion_run_scope_check_works_on_sqlite_test_database() -> None:
    engine = sa.create_engine("sqlite://")
    metadata = sa.MetaData()
    table = IngestionRun.__table__.to_metadata(metadata)
    table.c.id.type = sa.Integer()

    try:
        with engine.begin() as connection:
            connection.exec_driver_sql("ATTACH DATABASE ':memory:' AS audit")
            table.create(connection)
            connection.execute(
                sa.insert(table).values(
                    source="TSE",
                    dataset="candidatos",
                    scope_key="election-year:2022",
                    status="running",
                )
            )
            with pytest.raises(sa.exc.IntegrityError):
                connection.execute(
                    sa.insert(table).values(
                        source="TSE",
                        dataset="candidatos",
                        scope_key="   ",
                        status="running",
                    )
                )
    finally:
        engine.dispose()


def test_scope_migration_is_linear_and_backfills_existing_2026_runs() -> None:
    module = migration()
    assert module.revision == "f8142026hi01"
    assert module.down_revision == "e7032026id01"

    with patch.object(module, "op") as operations:
        module.upgrade()

    operations.add_column.assert_called_once()
    sql = "\n".join(
        call.args[0]
        for call in operations.execute.call_args_list
        if isinstance(call.args[0], str)
    )
    assert "SET scope_key = 'election-year:2026'" in sql
    assert "source = 'TSE'" in sql
    assert "dataset = 'candidatos'" in sql
    operations.create_index.assert_called_once_with(
        "ix_ingestion_run_source_dataset_scope_status",
        "ingestion_run",
        ["source", "dataset", "scope_key", "status", "finished_at", "id"],
        unique=False,
        schema="audit",
    )
