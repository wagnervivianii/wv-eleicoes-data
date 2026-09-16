from datetime import datetime
from types import MappingProxyType

from sqlalchemy import (
    BigInteger,
    DateTime,
    ForeignKey,
    Index,
    String,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from wv_eleicoes_data.db.base import Base
from wv_eleicoes_data.ingestion.tse.contracts import TSE_ASSETS_2026_HEADERS

# Attribute -> official CSV header. RAW values are preserved exactly as published by TSE.
TSE_ASSET_SOURCE_HEADERS = MappingProxyType(
    {header.lower(): header for header in TSE_ASSETS_2026_HEADERS}
)


class TseCandidateAsset(Base):
    """Temporal, source-faithful TSE declared-asset row.

    The natural item key is election year + election code + candidacy sequence +
    asset order. Monetary values remain source text in RAW, including negative values.
    Empty descriptions are preserved as empty strings rather than synthesized.
    """

    __tablename__ = "tse_candidate_asset"
    __table_args__ = (
        UniqueConstraint("ingestion_run_id", "source_file", "source_row_number"),
        Index(
            "uq_tse_candidate_asset_active",
            "ano_eleicao",
            "cd_eleicao",
            "sq_candidato",
            "nr_ordem_bem_candidato",
            unique=True,
            postgresql_where=text("valid_to_run_id IS NULL"),
            sqlite_where=text("valid_to_run_id IS NULL"),
        ),
        Index(
            "ix_tse_candidate_asset_active_candidacy",
            "ano_eleicao",
            "cd_eleicao",
            "sq_candidato",
            postgresql_where=text("valid_to_run_id IS NULL"),
            sqlite_where=text("valid_to_run_id IS NULL"),
        ),
        Index(
            "ix_tse_candidate_asset_history",
            "ano_eleicao",
            "cd_eleicao",
            "sq_candidato",
            "nr_ordem_bem_candidato",
            "valid_from_run_id",
        ),
        {"schema": "raw"},
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    ingestion_run_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("audit.ingestion_run.id"), nullable=False
    )
    valid_from_run_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("audit.ingestion_run.id"), nullable=False
    )
    valid_to_run_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("audit.ingestion_run.id")
    )
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    source_file: Mapped[str] = mapped_column(Text, nullable=False)
    source_row_number: Mapped[int] = mapped_column(BigInteger, nullable=False)
    ingested_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    dt_geracao: Mapped[str] = mapped_column(Text, nullable=False)
    hh_geracao: Mapped[str] = mapped_column(Text, nullable=False)
    ano_eleicao: Mapped[str] = mapped_column(Text, nullable=False)
    cd_tipo_eleicao: Mapped[str] = mapped_column(Text, nullable=False)
    nm_tipo_eleicao: Mapped[str] = mapped_column(Text, nullable=False)
    cd_eleicao: Mapped[str] = mapped_column(Text, nullable=False)
    ds_eleicao: Mapped[str] = mapped_column(Text, nullable=False)
    dt_eleicao: Mapped[str] = mapped_column(Text, nullable=False)
    sg_uf: Mapped[str] = mapped_column(Text, nullable=False)
    sg_ue: Mapped[str] = mapped_column(Text, nullable=False)
    nm_ue: Mapped[str] = mapped_column(Text, nullable=False)
    sq_candidato: Mapped[str] = mapped_column(Text, nullable=False)
    nr_ordem_bem_candidato: Mapped[str] = mapped_column(Text, nullable=False)
    cd_tipo_bem_candidato: Mapped[str] = mapped_column(Text, nullable=False)
    ds_tipo_bem_candidato: Mapped[str] = mapped_column(Text, nullable=False)
    ds_bem_candidato: Mapped[str] = mapped_column(Text, nullable=False)
    vr_bem_candidato: Mapped[str] = mapped_column(Text, nullable=False)
    dt_ult_atual_bem_candidato: Mapped[str] = mapped_column(Text, nullable=False)
    hh_ult_atual_bem_candidato: Mapped[str] = mapped_column(Text, nullable=False)
