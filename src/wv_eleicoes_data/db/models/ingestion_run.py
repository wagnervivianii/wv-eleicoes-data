from datetime import datetime

from sqlalchemy import BigInteger, DateTime, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from wv_eleicoes_data.db.base import Base


class IngestionRun(Base):
    """Registra a execução de um pipeline de ingestão."""

    __tablename__ = "ingestion_run"
    __table_args__ = {"schema": "audit"}

    id: Mapped[int] = mapped_column(
        BigInteger,
        primary_key=True,
        autoincrement=True,
    )

    source: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        index=True,
    )

    dataset: Mapped[str] = mapped_column(
        String(120),
        nullable=False,
        index=True,
    )

    status: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        index=True,
    )

    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    finished_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    source_updated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    rows_downloaded: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )

    rows_inserted: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )

    rows_updated: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )

    rows_added: Mapped[int | None] = mapped_column(Integer)
    rows_removed: Mapped[int | None] = mapped_column(Integer)
    rows_unchanged: Mapped[int | None] = mapped_column(Integer)

    rows_rejected: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )

    checksum: Mapped[str | None] = mapped_column(
        String(128),
        nullable=True,
    )

    error_message: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )
