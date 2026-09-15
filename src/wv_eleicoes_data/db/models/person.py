from datetime import date, datetime

from sqlalchemy import BigInteger, Date, DateTime, Index, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from wv_eleicoes_data.db.base import Base


class Person(Base):
    """Stable internal identity for a political person across source systems."""

    __tablename__ = "person"
    __table_args__ = (
        Index("ix_core_person_display_name", "display_name"),
        {"schema": "core"},
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    legal_name: Mapped[str] = mapped_column(Text, nullable=False)
    display_name: Mapped[str] = mapped_column(Text, nullable=False)
    social_name: Mapped[str | None] = mapped_column(Text)
    birth_date: Mapped[date | None] = mapped_column(Date)
    birth_uf: Mapped[str | None] = mapped_column(String(2))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
