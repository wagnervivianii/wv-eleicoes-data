from functools import lru_cache

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Configurações centralizadas do WV Eleições Data."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        env_prefix="WV_ELEICOES_",
        extra="ignore",
    )

    database_url: SecretStr
    ingestion_database_url: SecretStr | None = None


@lru_cache
def get_settings() -> Settings:
    """Retorna uma única instância das configurações da aplicação."""

    return Settings()
