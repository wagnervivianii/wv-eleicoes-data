from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
from unittest.mock import patch

import pytest


def migration(name: str):
    path = next(Path("migrations/versions").glob(f"{name}_*.py"))
    spec = spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_declared_asset_raw_migration_contract() -> None:
    module = migration("h0362026as01")

    assert module.down_revision == "g9252026hi02"
    assert "CREATE TABLE raw.tse_candidate_asset" in module.CREATE_RAW
    assert "vr_bem_candidato text NOT NULL" in module.CREATE_RAW
    assert "ds_bem_candidato text NOT NULL" in module.CREATE_RAW
    assert "content_hash varchar(64) NOT NULL" in module.CREATE_RAW
    assert "CREATE TABLE audit.asset_change" in module.CREATE_CHANGE
    assert "changed_fields jsonb" in module.CREATE_CHANGE
    assert "jsonb_array_length(changed_fields) > 0" in module.CREATE_CHANGE

    with patch.object(module, "op") as operations:
        module.upgrade()
    sql = "\n".join(call.args[0] for call in operations.execute.call_args_list)

    assert "uq_tse_candidate_asset_active" in sql
    assert "WHERE valid_to_run_id IS NULL" in sql
    assert "ix_tse_candidate_asset_active_candidacy" in sql
    assert "ix_tse_candidate_asset_history" in sql
    assert "ix_audit_asset_change_candidacy_history" in sql
    assert "GRANT SELECT, INSERT ON raw.tse_candidate_asset TO wv_eleicoes_ingestion" in sql
    assert "GRANT UPDATE (valid_to_run_id, content_hash)" in sql
    assert "GRANT SELECT, INSERT ON audit.asset_change TO wv_eleicoes_ingestion" in sql
    assert "wv_eleicoes_api" in sql
    assert "GRANT SELECT ON raw.tse_candidate_asset TO wv_eleicoes_api" not in sql
    assert "core." not in sql
    assert "analytics." not in sql


def test_declared_asset_raw_migration_refuses_destructive_downgrade() -> None:
    module = migration("h0362026as01")
    with pytest.raises(RuntimeError, match="cannot be safely removed"):
        module.downgrade()
