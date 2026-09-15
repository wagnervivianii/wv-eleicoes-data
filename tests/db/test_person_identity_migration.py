from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
from unittest.mock import patch


def migration():
    path = next(Path("migrations/versions").glob("e7032026id01_*.py"))
    spec = spec_from_file_location("person_identity_migration", path)
    assert spec is not None and spec.loader is not None
    module = module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_person_identity_migration_is_linear_and_scoped() -> None:
    module = migration()

    assert module.revision == "e7032026id01"
    assert module.down_revision == "d6922026ca03"
    assert "SECURITY DEFINER" in module.SYNC_FUNCTION
    assert "SET search_path = pg_catalog, pg_temp" in module.SYNC_FUNCTION
    assert "'TSE'" in module.SYNC_FUNCTION
    assert "'candidacy_sequence'" in module.SYNC_FUNCTION
    assert "'election:'" in module.SYNC_FUNCTION
    assert "nr_cpf_candidato" in module.SYNC_FUNCTION
    assert "INSERT INTO core.person_external_identifier" in module.SYNC_FUNCTION
    assert "ON CONFLICT" in module.SYNC_FUNCTION


def test_migration_grants_api_read_only_and_ingestion_sync_only() -> None:
    module = migration()

    with patch.object(module, "op") as operations:
        module.upgrade()

    sql = "\n".join(
        call.args[0]
        for call in operations.execute.call_args_list
        if isinstance(call.args[0], str)
    )

    for relation in ("core.person", "core.person_external_identifier"):
        assert f"GRANT SELECT ON {relation} TO wv_eleicoes_api" in sql
        assert f"REVOKE ALL ON {relation} FROM PUBLIC, wv_eleicoes_ingestion" in sql

    assert (
        "GRANT EXECUTE ON FUNCTION core.sync_person_identity_from_tse() "
        "TO wv_eleicoes_ingestion"
    ) in sql
    assert (
        "REVOKE ALL ON FUNCTION core.sync_person_identity_from_tse() "
        "FROM PUBLIC, wv_eleicoes_api"
    ) in sql


def test_cpf_is_transient_and_not_an_external_identifier() -> None:
    module = migration()

    assert "'cpf'" not in module.SYNC_FUNCTION
    assert "'candidacy_sequence'" in module.SYNC_FUNCTION
    assert "regexp_replace(btrim(r.nr_cpf_candidato)" in module.SYNC_FUNCTION
