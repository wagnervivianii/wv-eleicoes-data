"""Tribunal Superior Eleitoral (TSE) ingestion support."""

from wv_eleicoes_data.ingestion.tse.connector import (
    TseArtifact,
    TseCandidatesConnector,
    TseIngestionError,
)
from wv_eleicoes_data.ingestion.tse.contracts import CANDIDATES_2026, TseResourceContract

__all__ = [
    "CANDIDATES_2026",
    "TseArtifact",
    "TseCandidatesConnector",
    "TseIngestionError",
    "TseResourceContract",
]
