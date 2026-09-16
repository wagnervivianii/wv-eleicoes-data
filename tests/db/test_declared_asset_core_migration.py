from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
from unittest.mock import patch


def migration():
    path = next(Path("migrations/versions").glob("i1472026as02_*.py"))
    spec = spec_from_file_location("declared_asset_core_migration", path)
    assert spec is not None and spec.loader is not None
    module = module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_core_asset_migration_is_linear_and_longitudinal() -> None:
    module = migration()

    assert module.revision == "i1472026as02"
    assert module.down_revision == "h0362026as01"
    sql = module.CREATE_CORE
    assert "CREATE VIEW core.candidate_asset" in sql
    assert "FROM raw.tse_candidate_asset AS a" in sql
    assert "a.valid_to_run_id IS NULL" in sql
    assert "r.status = 'success'" in sql
    assert "r.dataset = 'bens_candidatos'" in sql
    assert "identifier.identifier_type = 'candidacy_sequence'" in sql
    assert "'election:' || btrim(a.ano_eleicao) || ':' || btrim(a.cd_eleicao)" in sql
    assert "identifier.person_id" in sql


def test_core_asset_normalizes_values_without_changing_raw_semantics() -> None:
    module = migration()
    sql = module.CREATE_CORE

    assert "replace(declared_value_text, ',', '.')::numeric" in sql
    assert "replace(replace(declared_value_text, '.', ''), ',', '.')::numeric" in sql
    assert "replace(declared_value_text, ',', '')::numeric" in sql
    assert "declared_value_status" in sql
    assert "THEN 'parsed'" in sql
    assert "THEN 'missing'" in sql
    assert "ELSE 'unrecognized'" in sql
    assert "ABS(" not in sql.upper()
    assert "GREATEST(" not in sql.upper()
    assert "declared_value < 0" not in sql
    assert "asset_description_text IN" in sql
    assert "THEN NULL" in sql
    assert "AT TIME ZONE 'America/Sao_Paulo'" in sql


def test_core_asset_public_contract_excludes_sensitive_candidate_fields() -> None:
    module = migration()
    sql = module.CREATE_CORE.lower()

    for sensitive in (
        "nr_cpf_candidato",
        "nr_titulo_eleitoral_candidato",
        "ds_email",
    ):
        assert sensitive not in sql

    for public_field in (
        "person_id",
        "election_year",
        "election_code",
        "candidacy_sequence",
        "asset_order",
        "asset_type_code",
        "asset_type_name",
        "asset_description",
        "declared_value",
        "asset_updated_at",
    ):
        assert public_field in sql


def test_upgrade_gates_row_loss_and_grants_api_read_only() -> None:
    module = migration()

    assert "active_source_rows <> core_rows" in module.VALIDATE_CORE
    assert "declared_value_status = 'unrecognized'" in module.VALIDATE_CORE

    with patch.object(module, "op") as operations:
        module.upgrade()

    statements = [
        call.args[0]
        for call in operations.execute.call_args_list
        if isinstance(call.args[0], str)
    ]
    assert module.CREATE_CORE in statements
    assert module.VALIDATE_CORE in statements
    assert (
        "REVOKE ALL ON core.candidate_asset "
        "FROM PUBLIC, wv_eleicoes_ingestion, wv_eleicoes_api"
    ) in statements
    assert "GRANT SELECT ON core.candidate_asset TO wv_eleicoes_api" in statements


def test_downgrade_only_drops_derived_view() -> None:
    module = migration()

    with patch.object(module, "op") as operations:
        module.downgrade()

    operations.execute.assert_called_once_with("DROP VIEW core.candidate_asset")
