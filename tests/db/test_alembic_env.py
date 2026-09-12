"""Ensure Alembic compares tables outside PostgreSQL's default schema."""

import runpy
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
from alembic.config import Config
from pydantic import SecretStr

from wv_eleicoes_data.db.base import Base


def test_alembic_imports_current_checkout(tmp_path: Path) -> None:
    checkout = Path(__file__).resolve().parents[2]
    external = tmp_path / "external"
    package = external / "wv_eleicoes_data"
    package.mkdir(parents=True)
    (package / "__init__.py").write_text(
        'raise AssertionError("Imported external editable installation")\n'
    )
    # A fresh interpreter avoids pytest's pythonpath and already imported models.
    # Put a competing installation first, and invoke Alembic from another cwd.
    script = """
import io
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from alembic import command
from alembic.config import Config
from alembic.script import ScriptDirectory
from pydantic import SecretStr

checkout = Path(sys.argv[1])
sys.path.insert(0, sys.argv[2])
output = io.StringIO()
config = Config(str(checkout / "alembic.ini"), output_buffer=output)
ScriptDirectory.from_config(config)

import wv_eleicoes_data
assert Path(wv_eleicoes_data.__file__).resolve() == (
    checkout / "src/wv_eleicoes_data/__init__.py"
).resolve()
settings = SimpleNamespace(database_url=SecretStr("postgresql://localhost/test"))
with patch("wv_eleicoes_data.config.get_settings", return_value=settings):
    command.upgrade(config, "head", sql=True)
assert "CREATE TABLE raw.tse_candidate" in output.getvalue()
"""
    result = subprocess.run(
        [sys.executable, "-I", "-c", script, str(checkout), str(external)],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr


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
