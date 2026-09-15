from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
from unittest.mock import patch


def migration():
    path = next(Path("migrations/versions").glob("g9252026hi02_*.py"))
    spec = spec_from_file_location("longitudinal_candidate_read_model", path)
    assert spec is not None and spec.loader is not None
    module = module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_longitudinal_read_model_is_linear_and_reads_active_scoped_raw() -> None:
    module = migration()

    assert module.revision == "g9252026hi02"
    assert module.down_revision == "f8142026hi01"
    sql = module.CREATE_CORE_LONGITUDINAL
    assert "FROM raw.tse_candidate AS c" in sql
    assert "JOIN audit.ingestion_run AS r" in sql
    assert "c.valid_to_run_id IS NULL" in sql
    assert "r.status = 'success'" in sql
    assert "r.source = 'TSE'" in sql
    assert "r.dataset = 'candidatos'" in sql
    assert "r.scope_key = 'election-year:' || btrim(c.ano_eleicao)" in sql
    assert "analytics.candidate_2026" not in sql


def test_public_projection_keeps_safe_contract_and_profile_join_index() -> None:
    module = migration()

    for sensitive in ("nr_cpf_candidato", "ds_email", "nr_titulo_eleitoral_candidato"):
        assert sensitive not in module.CREATE_CORE_LONGITUDINAL + module.CREATE_PUBLIC

    assert any("ix_candidate_identity_scope" in statement for statement in module.INDEXES)
    identity_index = next(
        statement for statement in module.INDEXES if "ix_candidate_identity_scope" in statement
    )
    assert "election_year, election_code, candidacy_sequence" in identity_index


def test_upgrade_replaces_2026_bootstrap_with_longitudinal_projection() -> None:
    module = migration()

    with patch.object(module, "op") as operations:
        module.upgrade()

    statements = [
        call.args[0]
        for call in operations.execute.call_args_list
        if isinstance(call.args[0], str)
    ]
    assert statements[:3] == [
        "DROP MATERIALIZED VIEW analytics.candidate RESTRICT",
        "DROP VIEW core.candidate RESTRICT",
        "DROP MATERIALIZED VIEW analytics.candidate_2026 RESTRICT",
    ]
    assert module.CREATE_CORE_LONGITUDINAL in statements
    assert module.CREATE_PUBLIC in statements
    assert "GRANT SELECT ON core.candidate TO wv_eleicoes_api" in statements
    assert "GRANT SELECT ON analytics.candidate TO wv_eleicoes_api" in statements


def test_downgrade_restores_2026_bootstrap_without_deleting_raw_history() -> None:
    module = migration()

    with patch.object(module, "op") as operations:
        module.downgrade()

    statements = [
        call.args[0]
        for call in operations.execute.call_args_list
        if isinstance(call.args[0], str)
    ]
    assert module.LEGACY_CREATE_2026 in statements
    assert module.LEGACY_CREATE_CORE in statements
    assert not any("DELETE FROM raw.tse_candidate" in statement for statement in statements)
    assert not any("TRUNCATE" in statement for statement in statements)
