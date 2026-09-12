"""Ensure Alembic compares tables outside PostgreSQL's default schema."""

import runpy
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
from alembic.config import Config
from pydantic import SecretStr

from wv_eleicoes_data.db.base import Base


@pytest.mark.parametrize("offline", [False, True])
def test_alembic_compares_named_schemas(offline: bool) -> None:
    config = Config()
    settings = SimpleNamespace(database_url=SecretStr("postgresql://localhost/test"))
    engine = MagicMock()
    with (
        patch("wv_eleicoes_data.config.get_settings", return_value=settings),
        patch("alembic.context.config", config, create=True),
        patch("alembic.context.is_offline_mode", return_value=offline),
        patch("alembic.context.configure") as configure,
        patch("alembic.context.begin_transaction"),
        patch("alembic.context.run_migrations") as run_migrations,
        patch("sqlalchemy.engine_from_config", return_value=engine),
    ):
        runpy.run_path("migrations/env.py")

    configure.assert_called_once()
    assert configure.call_args.kwargs["include_schemas"] is True
    assert configure.call_args.kwargs["compare_type"] is True
    assert configure.call_args.kwargs["target_metadata"] is Base.metadata
    assert {"raw.tse_candidate", "audit.ingestion_run"} <= Base.metadata.tables.keys()
    run_migrations.assert_called_once()
