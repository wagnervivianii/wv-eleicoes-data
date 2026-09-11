from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

import wv_eleicoes_data.db.models  # noqa: F401
from wv_eleicoes_data.config import get_settings
from wv_eleicoes_data.db.base import Base

config = context.config

settings = get_settings()

config.set_main_option(
    "sqlalchemy.url",
    settings.database_url.get_secret_value(),
)

if config.config_file_name is not None:
    fileConfig(config.config_file_name)


target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """Executa migrations sem criar uma conexão ativa com o banco."""

    url = config.get_main_option("sqlalchemy.url")

    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Executa migrations utilizando uma conexão ativa com o banco."""

    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
