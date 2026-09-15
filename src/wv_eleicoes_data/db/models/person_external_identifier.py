from datetime import datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
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


class PersonExternalIdentifier(Base):
    """Source identifier linked to a stable person, with explicit semantic scope."""

    __tablename__ = "person_external_identifier"
    __table_args__ = (
        UniqueConstraint(
            "source_system",
            "identifier_type",
            "identifier_value",
            "scope_key",
            name="uq_person_external_identifier_natural_key",
        ),
        CheckConstraint("btrim(source_system) <> ''", name="source_system_not_blank"),
        CheckConstraint("btrim(identifier_type) <> ''", name="identifier_type_not_blank"),
        CheckConstraint("btrim(identifier_value) <> ''", name="identifier_value_not_blank"),
        CheckConstraint("btrim(scope_key) <> ''", name="scope_key_not_blank"),
        Index(
            "ix_core_person_external_identifier_person_source",
            "person_id",
            "source_system",
            "identifier_type",
        ),
        {"schema": "core"},
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    person_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("core.person.id", ondelete="CASCADE"),
        nullable=False,
    )
    source_system: Mapped[str] = mapped_column(String(32), nullable=False)
    identifier_type: Mapped[str] = mapped_column(String(64), nullable=False)
    identifier_value: Mapped[str] = mapped_column(Text, nullable=False)
    scope_key: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        server_default=text("'global'"),
    )
    is_public: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        server_default=text("true"),
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
