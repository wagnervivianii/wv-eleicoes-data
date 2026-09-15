from importlib.util import module_from_spec, spec_from_file_location
from types import ModuleType
from unittest.mock import MagicMock, patch

import pytest
import sqlalchemy as sa
from alembic.migration import MigrationContext
from alembic.operations import Operations

from wv_eleicoes_data.analytics.candidates import QUERIES, refresh_candidates


def migration() -> ModuleType:
    spec = spec_from_file_location(
        "typed_candidate", "migrations/versions/c5812026ca02_candidate_query_contract.py"
    )
    assert spec and spec.loader
    module = module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_refresh_order_and_failure() -> None:
    engine = MagicMock()
    conn = engine.begin.return_value.__enter__.return_value
    refresh_candidates(engine)
    statements = [str(call.args[0]) for call in conn.execute.call_args_list]
    assert statements == [
        "SELECT pg_advisory_xact_lock(58102, 3)",
        "REFRESH MATERIALIZED VIEW CONCURRENTLY analytics.candidate",
    ]
    conn.execute.side_effect = RuntimeError("refresh failed")
    with pytest.raises(RuntimeError, match="refresh failed"):
        refresh_candidates(engine)
    assert engine.begin.return_value.__exit__.call_args.args[0] is RuntimeError


def test_query_indexes_and_public_projection() -> None:
    module = migration()
    projection = module.CREATE_PUBLIC.split("SELECT ", 1)[1].split("FROM core.", 1)[0]
    assert {column.strip() for column in projection.split(",")} == {
        "raw_candidate_id", "ingestion_run_id", "election_year", "election_code",
        "election_round", "uf", "electoral_unit", "electoral_unit_name", "office_code",
        "office_name", "candidacy_sequence", "ballot_number", "ballot_name", "party_number",
        "party_acronym", "party_name", "status_code", "status_name",
    }
    with patch.object(module, "op") as operations:
        module.upgrade()
        statements = [call.args[0] for call in operations.execute.call_args_list]
        for relation in ("core.candidate", "analytics.candidate"):
            assert f"REVOKE ALL ON {relation} FROM wv_eleicoes_ingestion" in statements
            assert f"GRANT SELECT ON {relation} TO wv_eleicoes_api" in statements
    assert len(module.INDEXES) == 5
    assert "UNIQUE" in module.INDEXES[0]
    for name, query in QUERIES.items():
        assert "analytics.candidate" in query
        assert all(f":{p}" in query for p in ("year", "uf", "office"))
        if name != "counts":
            assert "raw_candidate_id > :after ORDER BY raw_candidate_id LIMIT :limit" in query
    assert "to_tsvector('simple'::regconfig, coalesce(ballot_name, ''))" in module.INDEXES[-1]
    for sensitive in ("cpf", "email", "titulo", "nascimento", "nm_candidato"):
        assert sensitive not in module.CREATE_CORE + module.CREATE_PUBLIC
    assert "sq_candidato::" not in module.CREATE_CORE
    assert "nr_candidato::" not in module.CREATE_CORE


def test_postgresql_typed_contract(request: pytest.FixtureRequest) -> None:
    url = request.config.getoption("--analytics-test-url")
    if url is None:
        pytest.skip("Orchestrator must supply an explicit disposable local PostgreSQL URL")
    parsed = sa.engine.make_url(url)
    assert parsed.get_backend_name() == "postgresql"
    assert parsed.host in (None, "localhost", "127.0.0.1", "::1")
    module = migration()
    # A source adapter fixture isolates typed behavior from the ingestion selector.
    engine = sa.create_engine(parsed, hide_parameters=True)
    try:
        with engine.connect() as conn, conn.begin():
            assert conn.scalar(sa.text("SELECT to_regclass('analytics.candidate_2026')")) is None
            columns = [
                "ano_eleicao", "cd_eleicao", "nr_turno", "sg_uf", "sg_ue", "nm_ue",
                "cd_cargo", "ds_cargo", "sq_candidato", "nr_candidato", "nm_urna_candidato",
                "nr_partido", "sg_partido", "nm_partido", "cd_situacao_candidatura",
                "ds_situacao_candidatura",
            ]
            conn.execute(sa.text(
                "CREATE TABLE analytics.candidate_2026 "
                "(raw_candidate_id bigint, ingestion_run_id bigint, "
                + ", ".join(f"{c} text" for c in columns) + ")"
            ))
            markers = ["#NULO", "#NE", "NÃO DIVULGÁVEL", "-1", "-3", "-4", "", "  "]
            for i, marker in enumerate(markers):
                conn.execute(sa.text(
                    "INSERT INTO analytics.candidate_2026 VALUES (:id, 1, "
                    + ", ".join(":value" for _ in columns) + ")"
                ), {"id": i + 1, "value": marker})
            for i, year in enumerate(("2026", "2030", "99999999999999999999", "abcd")):
                conn.execute(sa.text(
                    "INSERT INTO analytics.candidate_2026 VALUES (:id, 1, :year, "
                    + ", ".join("'001'" for _ in columns[1:]) + ")"
                ), {"id": i + 20, "year": year})
            with patch.object(module, "op", Operations(MigrationContext.configure(conn))):
                module.upgrade()
            rows = list(conn.execute(sa.text(
                "SELECT * FROM analytics.candidate ORDER BY raw_candidate_id"
            )).mappings())
            for row in rows[:8]:
                assert all(v is None for k, v in row.items()
                           if k not in ("raw_candidate_id", "ingestion_run_id"))
            assert [r["election_year"] for r in rows[8:]] == [2026, 2030, None, None]
            assert all(r["ballot_number"] == "001" for r in rows[8:])
            assert all(r["candidacy_sequence"] == "001" for r in rows[8:])
            conn.execute(sa.text("REFRESH MATERIALIZED VIEW CONCURRENTLY analytics.candidate"))
            assert conn.scalar(sa.text("SELECT count(*) FROM analytics.candidate")) == 12
            conn.rollback()
    finally:
        engine.dispose()
