from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
from unittest.mock import patch


def migration():
    path = next(Path("migrations/versions").glob("k3692026as04_*.py"))
    spec = spec_from_file_location("declared_asset_item_serving_migration", path)
    assert spec is not None and spec.loader is not None
    module = module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_item_serving_migration_is_linear_and_core_derived() -> None:
    module = migration()

    assert module.revision == "k3692026as04"
    assert module.down_revision == "j2582026as03"
    assert "CREATE MATERIALIZED VIEW analytics.candidate_asset_item" in module.CREATE_ITEM
    assert "FROM core.candidate_asset" in module.CREATE_ITEM
    assert "raw.tse_candidate_asset" not in module.CREATE_ITEM
    assert "audit.ingestion_run" not in module.CREATE_ITEM
    assert "WITH DATA" in module.CREATE_ITEM


def test_item_serving_preserves_identity_and_signed_values() -> None:
    module = migration()
    sql = module.CREATE_ITEM

    assert "raw_asset_id" in sql
    assert "person_id" in sql
    assert "election_year" in sql
    assert "election_code" in sql
    assert "candidacy_sequence" in sql
    assert "asset_order" in sql
    assert "declared_value" in sql
    assert "declared_value_status" in sql
    assert "ABS(" not in sql.upper()
    assert "GREATEST(" not in sql.upper()


def test_item_serving_has_identity_and_declaration_lookup_indexes() -> None:
    module = migration()
    indexes = "\n".join(module.INDEXES)

    assert "CREATE UNIQUE INDEX uq_candidate_asset_item_raw_asset" in indexes
    assert "(raw_asset_id)" in indexes
    assert "CREATE INDEX ix_candidate_asset_item_declaration" in indexes
    assert (
        "(person_id, election_year, election_code, candidacy_sequence, "
        "asset_order, raw_asset_id)"
    ) in indexes


def test_item_integrity_gate_reconciles_core_summary_and_negative_values() -> None:
    module = migration()
    sql = module.VALIDATE_ITEM

    assert "item_rows <> core_rows" in sql
    assert "GROUP BY raw_asset_id" in sql
    assert "incomplete serving key" in sql
    assert "FULL JOIN analytics.candidate_asset_summary" in sql
    assert "items.asset_count <> summary.asset_count" in sql
    assert "items.negative_value_count <> summary.negative_value_count" in sql
    assert "IS DISTINCT FROM summary.declared_value_signed_total" in sql


def test_upgrade_grants_api_read_only_and_keeps_ingestion_out() -> None:
    module = migration()

    with patch.object(module, "op") as operations:
        module.upgrade()

    statements = [
        call.args[0]
        for call in operations.execute.call_args_list
        if isinstance(call.args[0], str)
    ]

    assert module.CREATE_ITEM in statements
    assert module.VALIDATE_ITEM in statements
    assert any("uq_candidate_asset_item_raw_asset" in statement for statement in statements)
    assert any("ix_candidate_asset_item_declaration" in statement for statement in statements)
    assert (
        "REVOKE ALL ON analytics.candidate_asset_item "
        "FROM PUBLIC, wv_eleicoes_ingestion, wv_eleicoes_api"
    ) in statements
    assert (
        "GRANT SELECT ON analytics.candidate_asset_item TO wv_eleicoes_api"
        in statements
    )
