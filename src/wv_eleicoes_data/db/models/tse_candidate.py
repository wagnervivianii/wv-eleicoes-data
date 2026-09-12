from datetime import datetime
from types import MappingProxyType

from sqlalchemy import BigInteger, DateTime, ForeignKey, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from wv_eleicoes_data.db.base import Base
from wv_eleicoes_data.ingestion.tse.contracts import TSE_CANDIDATES_2026_HEADERS

# Attribute -> official CSV header; values are never normalized.
TSE_CANDIDATE_SOURCE_HEADERS = MappingProxyType(
    {header.lower(): header for header in TSE_CANDIDATES_2026_HEADERS}
)


class TseCandidate(Base):
    """Internal, source-faithful rows from consulta_cand_2026_BRASIL.csv.

    SQ_CANDIDATO is an election candidacy identifier, not a person identity.
    CPF, voter registration and email must remain internal.
    Source row numbers are physical CSV starting lines (first data row = 2).
    """

    __tablename__ = "tse_candidate"
    __table_args__ = (
        UniqueConstraint("ingestion_run_id", "source_file", "source_row_number"),
        {"schema": "raw"},
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    ingestion_run_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("audit.ingestion_run.id"), nullable=False
    )
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
    nr_turno: Mapped[str] = mapped_column(Text, nullable=False)
    cd_eleicao: Mapped[str] = mapped_column(Text, nullable=False)
    ds_eleicao: Mapped[str] = mapped_column(Text, nullable=False)
    dt_eleicao: Mapped[str] = mapped_column(Text, nullable=False)
    tp_abrangencia: Mapped[str] = mapped_column(Text, nullable=False)
    sg_uf: Mapped[str] = mapped_column(Text, nullable=False)
    sg_ue: Mapped[str] = mapped_column(Text, nullable=False)
    nm_ue: Mapped[str] = mapped_column(Text, nullable=False)
    cd_cargo: Mapped[str] = mapped_column(Text, nullable=False)
    ds_cargo: Mapped[str] = mapped_column(Text, nullable=False)
    sq_candidato: Mapped[str] = mapped_column(Text, nullable=False)
    nr_candidato: Mapped[str] = mapped_column(Text, nullable=False)
    nm_candidato: Mapped[str] = mapped_column(Text, nullable=False)
    nm_urna_candidato: Mapped[str] = mapped_column(Text, nullable=False)
    nm_social_candidato: Mapped[str] = mapped_column(Text, nullable=False)
    nr_cpf_candidato: Mapped[str] = mapped_column(Text, nullable=False)
    ds_email: Mapped[str] = mapped_column(Text, nullable=False)
    cd_situacao_candidatura: Mapped[str] = mapped_column(Text, nullable=False)
    ds_situacao_candidatura: Mapped[str] = mapped_column(Text, nullable=False)
    tp_agremiacao: Mapped[str] = mapped_column(Text, nullable=False)
    nr_partido: Mapped[str] = mapped_column(Text, nullable=False)
    sg_partido: Mapped[str] = mapped_column(Text, nullable=False)
    nm_partido: Mapped[str] = mapped_column(Text, nullable=False)
    nr_federacao: Mapped[str] = mapped_column(Text, nullable=False)
    nm_federacao: Mapped[str] = mapped_column(Text, nullable=False)
    sg_federacao: Mapped[str] = mapped_column(Text, nullable=False)
    ds_composicao_federacao: Mapped[str] = mapped_column(Text, nullable=False)
    sq_coligacao: Mapped[str] = mapped_column(Text, nullable=False)
    nm_coligacao: Mapped[str] = mapped_column(Text, nullable=False)
    ds_composicao_coligacao: Mapped[str] = mapped_column(Text, nullable=False)
    sg_uf_nascimento: Mapped[str] = mapped_column(Text, nullable=False)
    dt_nascimento: Mapped[str] = mapped_column(Text, nullable=False)
    nr_titulo_eleitoral_candidato: Mapped[str] = mapped_column(Text, nullable=False)
    cd_genero: Mapped[str] = mapped_column(Text, nullable=False)
    ds_genero: Mapped[str] = mapped_column(Text, nullable=False)
    cd_grau_instrucao: Mapped[str] = mapped_column(Text, nullable=False)
    ds_grau_instrucao: Mapped[str] = mapped_column(Text, nullable=False)
    cd_estado_civil: Mapped[str] = mapped_column(Text, nullable=False)
    ds_estado_civil: Mapped[str] = mapped_column(Text, nullable=False)
    cd_cor_raca: Mapped[str] = mapped_column(Text, nullable=False)
    ds_cor_raca: Mapped[str] = mapped_column(Text, nullable=False)
    cd_ocupacao: Mapped[str] = mapped_column(Text, nullable=False)
    ds_ocupacao: Mapped[str] = mapped_column(Text, nullable=False)
    cd_sit_tot_turno: Mapped[str] = mapped_column(Text, nullable=False)
    ds_sit_tot_turno: Mapped[str] = mapped_column(Text, nullable=False)
