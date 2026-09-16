"""Tribunal Superior Eleitoral (TSE) ingestion support."""

from wv_eleicoes_data.ingestion.tse.connector import (
    TseArtifact,
    TseCandidatesConnector,
    TseIngestionError,
)
from wv_eleicoes_data.ingestion.tse.contracts import (
    ASSETS_2022,
    ASSETS_2022_DISCOVERY,
    ASSETS_2026,
    ASSETS_2026_DISCOVERY,
    CANDIDATES_2022,
    CANDIDATES_2026,
    SUPPORTED_ASSET_DISCOVERY_YEARS,
    SUPPORTED_ASSET_YEARS,
    SUPPORTED_CANDIDATE_YEARS,
    TseResourceContract,
    assets_contract_for_year,
    assets_discovery_contract_for_year,
    candidates_contract_for_year,
)

__all__ = [
    "ASSETS_2022",
    "ASSETS_2022_DISCOVERY",
    "ASSETS_2026",
    "ASSETS_2026_DISCOVERY",
    "CANDIDATES_2022",
    "CANDIDATES_2026",
    "SUPPORTED_ASSET_DISCOVERY_YEARS",
    "SUPPORTED_ASSET_YEARS",
    "SUPPORTED_CANDIDATE_YEARS",
    "TseArtifact",
    "TseCandidatesConnector",
    "TseIngestionError",
    "TseResourceContract",
    "assets_contract_for_year",
    "assets_discovery_contract_for_year",
    "candidates_contract_for_year",
]
