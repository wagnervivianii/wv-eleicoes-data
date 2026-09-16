"""Run with python -m wv_eleicoes_data.ingestion.tse.asset_pipeline --year YEAR."""

import argparse
from pathlib import Path
from tempfile import TemporaryDirectory

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy import Engine, create_engine
from sqlalchemy.engine import make_url

from wv_eleicoes_data.ingestion.tse import asset_persistence
from wv_eleicoes_data.ingestion.tse.connector import TseCandidatesConnector
from wv_eleicoes_data.ingestion.tse.contracts import (
    SUPPORTED_ASSET_YEARS,
    assets_contract_for_year,
)


class IngestionSettings(BaseSettings):
    """Only the explicit ingestion URL is accepted; no dotenv or owner fallback."""

    model_config = SettingsConfigDict(env_prefix="WV_ELEICOES_", extra="ignore")
    ingestion_database_url: SecretStr


def ingestion_engine(settings: IngestionSettings) -> Engine:
    url = make_url(settings.ingestion_database_url.get_secret_value())
    if url.get_backend_name() != "postgresql":
        raise ValueError("Ingestion requires PostgreSQL")
    return create_engine(url, isolation_level="READ COMMITTED", hide_parameters=True)


def run_pipeline(
    engine: Engine,
    *,
    connector: TseCandidatesConnector,
    batch_size: int = 1000,
) -> tuple[int, str]:
    """Download and apply one registered election-year assets contract."""

    if not 1 <= batch_size <= 1000:
        raise ValueError("batch_size must be between 1 and 1000")
    run_id = asset_persistence.start_run(engine, connector.contract)
    try:
        with TemporaryDirectory(prefix="wv-tse-assets-") as directory:
            artifact = connector.fetch(Path(directory))
            status = asset_persistence.load_artifact(
                engine,
                artifact,
                connector.contract,
                run_id,
                batch_size,
            )
        return run_id, status
    except BaseException:
        asset_persistence.fail_run(engine, run_id)
        raise


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Ingest official TSE declared assets into temporal RAW storage."
    )
    parser.add_argument(
        "--year",
        type=int,
        choices=SUPPORTED_ASSET_YEARS,
        required=True,
        help="Registered election year to ingest.",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        choices=range(1, 1001),
        default=1000,
        metavar="1..1000",
    )
    args = parser.parse_args(argv)

    try:
        settings = IngestionSettings()
        engine = ingestion_engine(settings)
    except Exception:
        print("Startup failed: a valid WV_ELEICOES_INGESTION_DATABASE_URL is required.")
        return 2

    try:
        connector = TseCandidatesConnector(assets_contract_for_year(args.year))
        run_id, status = run_pipeline(
            engine,
            connector=connector,
            batch_size=args.batch_size,
        )
        print(f"ingestion_run_id={run_id} status={status}")
        return 0
    except BaseException:
        print("Declared-assets ingestion failed; inspect audit.ingestion_run.")
        return 1
    finally:
        engine.dispose()


if __name__ == "__main__":
    raise SystemExit(main())
