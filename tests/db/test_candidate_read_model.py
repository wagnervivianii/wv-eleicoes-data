from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
from types import ModuleType
from unittest.mock import patch

import pytest
import sqlalchemy as sa
from alembic.migration import MigrationContext
from alembic.operations import Operations

from wv_eleicoes_data.db.models import IngestionRun, TseCandidate
from wv_eleicoes_data.db.models.tse_candidate import TSE_CANDIDATE_SOURCE_HEADERS

PUBLIC = {
    "raw_candidate_id", "ingestion_run_id", "ano_eleicao", "cd_eleicao", "nr_turno",
    "sg_uf", "sg_ue", "nm_ue", "cd_cargo", "ds_cargo", "sq_candidato", "nr_candidato",
    "nm_urna_candidato", "nr_partido", "sg_partido", "nm_partido",
    "cd_situacao_candidatura", "ds_situacao_candidatura",
}


def migration() -> ModuleType:
    path = Path("migrations/versions/b4702026ca01_candidate_public_read_model.py")
    spec = spec_from_file_location("candidate_migration", path)
    assert spec is not None and spec.loader is not None
    module = module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_frozen_public_allowlist_and_refresh_ddl() -> None:
    module = migration()
    projection = module.CREATE_VIEW.split("SELECT\n", 1)[1].split("FROM raw.", 1)[0]
    columns = {item.strip().split(" AS ")[-1].removeprefix("c.")
               for item in projection.split(",")}
    assert columns == PUBLIC
    with patch.object(module, "op") as operations:
        module.upgrade()
        statements = [call.args[0] for call in operations.execute.call_args_list]
        assert "WITH DATA" in statements[0]
        assert statements[1] == (
            "CREATE UNIQUE INDEX uq_candidate_2026_raw_candidate_id "
            "ON analytics.candidate_2026 (raw_candidate_id)"
        )
        assert "GRANT SELECT ON analytics.candidate_2026 TO wv_eleicoes_api" in statements
        operations.reset_mock()
        module.downgrade()
        operations.execute.assert_called_once_with(
            "DROP MATERIALIZED VIEW analytics.candidate_2026 RESTRICT"
        )


def test_postgresql_snapshot_lifecycle(request: pytest.FixtureRequest) -> None:
    url = request.config.getoption("--analytics-test-url")
    if url is None:
        pytest.skip("Orchestrator must supply an explicit disposable local PostgreSQL URL")
    parsed = sa.engine.make_url(url)
    assert parsed.get_backend_name() == "postgresql"
    assert parsed.host in (None, "localhost", "127.0.0.1", "::1")
    engine = sa.create_engine(parsed, hide_parameters=True)
    module = migration()
    try:
        with engine.connect() as conn, conn.begin() as transaction:
            assert conn.scalar(sa.text("SELECT count(*) FROM audit.ingestion_run")) == 0
            assert conn.scalar(sa.text("SELECT count(*) FROM raw.tse_candidate")) == 0
            assert conn.scalar(sa.text("SELECT to_regclass('analytics.candidate_2026')")) is None
            operations = Operations(MigrationContext.configure(conn))
            with patch.object(module, "op", operations):
                module.upgrade()
            query = sa.text("SELECT * FROM analytics.candidate_2026 ORDER BY raw_candidate_id")

            def refresh() -> list[sa.RowMapping]:
                conn.execute(sa.text(
                    "REFRESH MATERIALIZED VIEW CONCURRENTLY analytics.candidate_2026"
                ))
                return list(conn.execute(query).mappings())

            assert refresh() == []
            for run_id, status, source, dataset, finished in [
                (1, "success", "TSE", "candidatos", "2026-09-10"),
                (2, "success", "TSE", "candidatos", "2026-09-11"),
                (3, "success", "TSE", "candidatos", "2026-09-11"),
                (4, "failed", "TSE", "candidatos", "2026-09-12"),
                (5, "skipped", "TSE", "candidatos", "2026-09-12"),
                (6, "running", "TSE", "candidatos", "2026-09-12"),
                (7, "success", "OTHER", "candidatos", "2026-09-12"),
                (8, "success", "TSE", "other", "2026-09-12"),
                (9, "success", "TSE", "candidatos", None),
            ]:
                conn.execute(sa.insert(IngestionRun).values(
                    id=run_id, source=source, dataset=dataset, status=status,
                    finished_at=finished,
                ))
            sentinels = ["#NULO", "#NE", "NÃO DIVULGÁVEL", "-1", "-3", "-4", "000123", ""]
            row_id = 0
            for run_id in range(1, 10):
                for sentinel in sentinels:
                    row_id += 1
                    payload = dict.fromkeys(TSE_CANDIDATE_SOURCE_HEADERS, sentinel)
                    payload.update(ano_eleicao="2026", sq_candidato="duplicate")
                    conn.execute(sa.insert(TseCandidate).values(
                        **payload, id=row_id, ingestion_run_id=run_id,
                        source_file="consulta_cand_2026_BRASIL.csv", source_row_number=row_id,
                    ))
            # Publication remains unchanged until the explicit refresh.
            assert list(conn.execute(query)) == []
            rows = refresh()
            assert len(rows) == len(sentinels)
            assert set(rows[0]) == PUBLIC
            assert {r["ingestion_run_id"] for r in rows} == {3}
            assert [r["nr_candidato"] for r in rows] == sentinels
            assert rows == refresh()
            conn.execute(sa.text("SET LOCAL ROLE wv_eleicoes_api"))
            assert list(conn.execute(query).mappings()) == rows
            assert not conn.scalar(sa.text(
                "SELECT has_schema_privilege(current_user, 'raw', 'USAGE')"
            ))
            assert not conn.scalar(sa.text(
                "SELECT has_table_privilege(current_user, 'analytics.candidate_2026', 'INSERT')"
            ))
            conn.execute(sa.text("RESET ROLE"))
            conn.execute(sa.update(TseCandidate).where(
                TseCandidate.ingestion_run_id == 3,
                TseCandidate.nr_candidato == "#NULO",
            ).values(ano_eleicao="-1"))
            conn.execute(sa.update(TseCandidate).where(
                TseCandidate.ingestion_run_id == 3,
                TseCandidate.nr_candidato == "#NE",
            ).values(source_file="other.csv"))
            assert len(refresh()) == conn.scalar(sa.text(
                "SELECT count(*) FROM raw.tse_candidate WHERE ingestion_run_id = 3 "
                "AND ano_eleicao = '2026' AND source_file = 'consulta_cand_2026_BRASIL.csv'"
            )) == 6
            conn.execute(sa.insert(IngestionRun).values(
                id=10, source="TSE", dataset="candidatos", status="success",
                finished_at="2026-09-13",
            ))
            assert refresh() == []  # Empty latest success does not fall back.
            with patch.object(module, "op", operations):
                module.downgrade()
                module.upgrade()
            assert refresh() == []
            assert conn.scalar(sa.text("SELECT count(*) FROM raw.tse_candidate")) == row_id
            transaction.rollback()
    finally:
        engine.dispose()
