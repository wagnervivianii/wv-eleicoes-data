"""Internal per-run logical declared-asset deltas."""

from datetime import datetime

from sqlalchemy import (
    JSON,
    BigInteger,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from wv_eleicoes_data.db.base import Base


class AssetChange(Base):
    """Audit one logical declared-asset addition, modification or removal."""

    __tablename__ = "asset_change"
    __table_args__ = (
        UniqueConstraint(
            "run_id",
            "ano_eleicao",
            "cd_eleicao",
            "sq_candidato",
            "nr_ordem_bem_candidato",
        ),
        CheckConstraint(
            "(change_type = 'A' AND old_raw_asset_id IS NULL "
            "AND new_raw_asset_id IS NOT NULL AND changed_fields IS NULL) OR "
            "(change_type = 'M' AND old_raw_asset_id IS NOT NULL "
            "AND new_raw_asset_id IS NOT NULL "
            "AND old_raw_asset_id <> new_raw_asset_id "
            "AND changed_fields IS NOT NULL) OR "
            "(change_type = 'D' AND old_raw_asset_id IS NOT NULL "
            "AND new_raw_asset_id IS NULL AND changed_fields IS NULL)",
            name="change_shape",
        ),
        Index("ix_audit_asset_change_election_run", "ano_eleicao", "run_id"),
        Index(
            "ix_audit_asset_change_candidacy_history",
            "ano_eleicao",
            "cd_eleicao",
            "sq_candidato",
            "nr_ordem_bem_candidato",
            "detected_at",
            "id",
        ),
        {"schema": "audit"},
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    run_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("audit.ingestion_run.id"), nullable=False, index=True
    )
    change_type: Mapped[str] = mapped_column(String(1), nullable=False)
    ano_eleicao: Mapped[str] = mapped_column(Text, nullable=False)
    cd_eleicao: Mapped[str] = mapped_column(Text, nullable=False)
    sq_candidato: Mapped[str] = mapped_column(Text, nullable=False)
    nr_ordem_bem_candidato: Mapped[str] = mapped_column(Text, nullable=False)
    old_raw_asset_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("raw.tse_candidate_asset.id")
    )
    new_raw_asset_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("raw.tse_candidate_asset.id")
    )
    source_snapshot_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    detected_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    changed_fields: Mapped[list[str] | None] = mapped_column(
        JSON(none_as_null=True).with_variant(JSONB(none_as_null=True), "postgresql")
    )
