"""Tribunal Superior Eleitoral (TSE) ingestion support."""

from wv_eleicoes_data.ingestion.tse.connector import (
    TseArtifact,
    TseCandidatesConnector,
    TseIngestionError,
)
from wv_eleicoes_data.ingestion.tse.contracts import (
    CANDIDATES_2022,
    CANDIDATES_2026,
    SUPPORTED_CANDIDATE_YEARS,
    TseResourceContract,
    candidates_contract_for_year,
)

__all__ = [
    "CANDIDATES_2022",
    "CANDIDATES_2026",
    "SUPPORTED_CANDIDATE_YEARS",
    "TseArtifact",
    "TseCandidatesConnector",
    "TseIngestionError",
    "TseResourceContract",
    "candidates_contract_for_year",
]
