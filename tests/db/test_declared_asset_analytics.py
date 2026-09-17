from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
from unittest.mock import MagicMock, patch

from wv_eleicoes_data.analytics.assets import refresh_declared_assets


def migration():
    path = next(Path("migrations/versions").glob("j2582026as03_*.py"))
    spec = spec_from_file_location("declared_asset_analytics_migration", path)
    assert spec is not None and spec.loader is not None
    module = module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_asset_analytics_migration_is_linear_and_serving_oriented() -> None:
    module = migration()

    assert module.revision == "j2582026as03"
    assert module.down_revision == "i1472026as02"
    assert "CREATE MATERIALIZED VIEW analytics.candidate_asset_summary" in module.CREATE_SUMMARY
    assert (
        "CREATE MATERIALIZED VIEW analytics.candidate_asset_type"
        in module.CREATE_TYPE_COMPOSITION
    )
    assert "CREATE MATERIALIZED VIEW analytics.person_asset_evolution" in module.CREATE_EVOLUTION
    assert "FROM core.candidate_asset" in module.CREATE_SUMMARY
    assert "person_id" in module.CREATE_SUMMARY
    assert "election_year" in module.CREATE_SUMMARY


def test_summary_keeps_negative_values_explicit_instead_of_hiding_them() -> None:
    module = migration()
    sql = module.CREATE_SUMMARY

    assert "declared_value_signed_total" in sql
    assert "declared_value_positive_total" in sql
    assert "declared_value_negative_total" in sql
    assert "negative_value_count" in sql
    assert "has_negative_values" in sql
    assert "largest_declared_value" in sql
    assert "ABS(" not in sql.upper()
    assert "GREATEST(" not in sql.upper()


def test_type_composition_uses_unambiguous_share_denominators() -> None:
    module = migration()
    sql = module.CREATE_TYPE_COMPOSITION

    assert "item_share_pct" in sql
    assert "positive_value_share_pct" in sql
    assert "declared_value_positive_total" in sql
    assert "summary.declared_value_positive_total > 0" in sql
    assert "declared_value_signed_total * 100" not in sql


def test_evolution_is_one_row_per_person_year_and_never_compares_same_year() -> None:
    module = migration()
    sql = module.CREATE_EVOLUTION

    assert "GROUP BY s.person_id, s.election_year" in sql
    assert "candidacy_snapshot_count" in sql
    assert "election_count" in sql
    assert "multiple_candidacy_snapshots" in sql
    assert "PARTITION BY a.person_id" in sql
    assert "ORDER BY a.election_year" in sql
    assert "ORDER BY a.election_year, a.election_code" not in sql
    assert "current_ambiguous" in sql
    assert "previous_ambiguous" in sql


def test_evolution_suppresses_unsafe_percentages() -> None:
    module = migration()
    sql = module.CREATE_EVOLUTION

    assert "declared_value_nominal_change" in sql
    assert "declared_value_change_pct" in sql
    assert "contains_negative_values" in sql
    assert "zero_baseline" in sql
    assert "comparison_status" in sql
    assert "snapshot_status = 'single_snapshot'" in sql
    assert "previous_snapshot_status = 'single_snapshot'" in sql
    assert "NOT has_negative_values" in sql
    assert "NOT previous_has_negative_values" in sql


def test_data_gate_reconciles_serving_layers_and_guards_evolution() -> None:
    module = migration()
    sql = module.VALIDATE_ANALYTICS

    assert "summary_rows <> expected_summaries" in sql
    assert "summary_assets <> core_rows" in sql
    assert "type_assets <> core_rows" in sql
    assert "evolution_rows <> expected_evolution_rows" in sql
    assert "previous_election_year >= election_year" in sql
    assert "snapshot status mismatch" in sql
    assert "published an unsafe percentage" in sql
    assert "declared_value_positive_total + declared_value_negative_total" in sql


def test_upgrade_indexes_and_grants_api_read_only() -> None:
    module = migration()

    with patch.object(module, "op") as operations:
        module.upgrade()

    statements = [
        call.args[0]
        for call in operations.execute.call_args_list
        if isinstance(call.args[0], str)
    ]
    assert module.CREATE_SUMMARY in statements
    assert module.CREATE_TYPE_COMPOSITION in statements
    assert module.CREATE_EVOLUTION in statements
    assert module.VALIDATE_ANALYTICS in statements
    assert any("uq_candidate_asset_summary_scope" in statement for statement in statements)
    assert any("uq_candidate_asset_type_scope" in statement for statement in statements)
    assert any(
        "uq_person_asset_evolution_person_year" in statement
        for statement in statements
    )
    for relation in module.RELATIONS:
        assert (
            f"REVOKE ALL ON {relation} "
            "FROM PUBLIC, wv_eleicoes_ingestion, wv_eleicoes_api"
        ) in statements
        assert f"GRANT SELECT ON {relation} TO wv_eleicoes_api" in statements


def test_refresh_declared_assets_is_locked_and_dependency_ordered() -> None:
    engine = MagicMock()
    connection = MagicMock()
    transaction = MagicMock()
    transaction.__enter__.return_value = connection
    engine.begin.return_value = transaction

    refresh_declared_assets(engine)

    sql = [call.args[0].text for call in connection.execute.call_args_list]
    assert sql == [
        "SET TRANSACTION ISOLATION LEVEL REPEATABLE READ",
        "SELECT pg_advisory_xact_lock(58102, 4)",
        "REFRESH MATERIALIZED VIEW analytics.candidate_asset_item",
        "REFRESH MATERIALIZED VIEW analytics.candidate_asset_summary",
        "REFRESH MATERIALIZED VIEW analytics.candidate_asset_type",
        "REFRESH MATERIALIZED VIEW analytics.person_asset_evolution",
    ]
