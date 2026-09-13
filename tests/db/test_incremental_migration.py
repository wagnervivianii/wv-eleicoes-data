"""Frozen migration SQL and optional transactional PostgreSQL backfill integration."""

from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
from unittest.mock import patch

import pytest
import sqlalchemy as sa
from alembic.migration import MigrationContext
from alembic.operations import Operations


def migration(name):
    path = next(Path("migrations/versions").glob(f"{name}_*.py"))
    spec = spec_from_file_location(name, path)
    module = module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_incremental_sql_contract():
    module = migration("d6922026ca03")
    previous = migration("b4702026ca01")
    assert (
        module.CREATE_VIEW.split("SELECT\n")[1].split("FROM raw.")[0]
        == (previous.CREATE_VIEW.split("SELECT\n")[1].split("FROM raw.")[0])
    )
    assert "valid_to_run_id IS NULL" in module.CREATE_VIEW
    assert "latest_success" not in module.CREATE_VIEW
    with patch.object(module, "op") as operations:
        module.upgrade()
    sql = "\n".join(call.args[0] for call in operations.execute.call_args_list)
    assert "DELETE FROM" not in sql
    assert "lead(c.ingestion_run_id)" in sql
    assert "WHERE valid_to_run_id IS NULL" in sql
    assert "GRANT UPDATE (valid_to_run_id, content_hash)" in sql
    assert len(module.INDEXES) == 5
    for relation in ("analytics.candidate_2026", "core.candidate", "analytics.candidate"):
        assert f"GRANT SELECT ON {relation} TO wv_eleicoes_api" in sql


def test_postgresql_backfill_and_current_projection(request):
    url = request.config.getoption("--analytics-test-url")
    if url is None:
        pytest.skip("Orchestrator must supply an explicit disposable local PostgreSQL URL")
    parsed = sa.engine.make_url(url)
    assert parsed.get_backend_name() == "postgresql"
    assert parsed.host in (None, "localhost", "127.0.0.1", "::1")
    engine = sa.create_engine(parsed, hide_parameters=True)
    try:
        with engine.connect() as conn, conn.begin() as transaction:
            metadata = sa.MetaData()
            raw = sa.Table("tse_candidate", metadata, schema="raw", autoload_with=conn)
            runs = sa.Table("ingestion_run", metadata, schema="audit", autoload_with=conn)
            assert conn.scalar(sa.select(sa.func.count()).select_from(raw)) == 0
            for i in (1, 2, 3):
                conn.execute(
                    runs.insert().values(
                        id=i,
                        source="TSE",
                        dataset="candidatos",
                        status="success",
                        finished_at=f"2026-09-{i:02d}",
                    )
                )
            from wv_eleicoes_data.db.models.tse_candidate import TSE_CANDIDATE_SOURCE_HEADERS

            payload = dict.fromkeys(TSE_CANDIDATE_SOURCE_HEADERS, "#NULO")
            payload.update(ano_eleicao="2026", cd_eleicao="123", sq_candidato="1")
            for i, key in ((1, "1"), (2, "1"), (3, "2")):
                conn.execute(
                    raw.insert().values(
                        **dict(payload, sq_candidato=key),
                        id=i,
                        ingestion_run_id=1 if i == 1 else 2,
                        source_file="consulta_cand_2026_BRASIL.csv",
                        source_row_number=i,
                    )
                )
            operations = Operations(MigrationContext.configure(conn))
            for revision in ("b4702026ca01", "c5812026ca02", "d6922026ca03"):
                module = migration(revision)
                with patch.object(module, "op", operations):
                    module.upgrade()
            assert conn.scalar(sa.text("SELECT count(*) FROM raw.tse_candidate")) == 3
            assert conn.execute(
                sa.text(
                    "SELECT id FROM raw.tse_candidate WHERE valid_to_run_id IS NULL ORDER BY id"
                )
            ).scalars().all() == [2, 3]
            # Only one candidate gets a new version; the other must stay visible.
            conn.execute(sa.text("UPDATE raw.tse_candidate SET valid_to_run_id=3 WHERE id=2"))
            raw = sa.Table("tse_candidate", sa.MetaData(), schema="raw", autoload_with=conn)
            conn.execute(
                raw.insert().values(
                    **payload,
                    id=4,
                    ingestion_run_id=3,
                    valid_from_run_id=3,
                    source_file="consulta_cand_2026_BRASIL.csv",
                    source_row_number=2,
                )
            )
            for relation in ("analytics.candidate_2026", "analytics.candidate"):
                conn.execute(sa.text(f"REFRESH MATERIALIZED VIEW CONCURRENTLY {relation}"))
                assert conn.execute(
                    sa.text(f"SELECT raw_candidate_id FROM {relation} ORDER BY raw_candidate_id")
                ).scalars().all() == [3, 4]
            transaction.rollback()
    finally:
        engine.dispose()
