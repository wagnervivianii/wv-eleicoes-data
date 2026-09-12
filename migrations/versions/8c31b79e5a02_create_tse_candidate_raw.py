"""Create the internal TSE candidates RAW table.

Revision ID: 8c31b79e5a02
Revises: 2ae610ff28cd

The source columns are frozen here so future contract changes cannot alter this revision.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "8c31b79e5a02"
down_revision: str | None = "2ae610ff28cd"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "tse_candidate",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("ingestion_run_id", sa.BigInteger(), nullable=False),
        sa.Column("source_file", sa.Text(), nullable=False),
        sa.Column("source_row_number", sa.BigInteger(), nullable=False),
        sa.Column(
            "ingested_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("dt_geracao", sa.Text(), nullable=False),
        sa.Column("hh_geracao", sa.Text(), nullable=False),
        sa.Column("ano_eleicao", sa.Text(), nullable=False),
        sa.Column("cd_tipo_eleicao", sa.Text(), nullable=False),
        sa.Column("nm_tipo_eleicao", sa.Text(), nullable=False),
        sa.Column("nr_turno", sa.Text(), nullable=False),
        sa.Column("cd_eleicao", sa.Text(), nullable=False),
        sa.Column("ds_eleicao", sa.Text(), nullable=False),
        sa.Column("dt_eleicao", sa.Text(), nullable=False),
        sa.Column("tp_abrangencia", sa.Text(), nullable=False),
        sa.Column("sg_uf", sa.Text(), nullable=False),
        sa.Column("sg_ue", sa.Text(), nullable=False),
        sa.Column("nm_ue", sa.Text(), nullable=False),
        sa.Column("cd_cargo", sa.Text(), nullable=False),
        sa.Column("ds_cargo", sa.Text(), nullable=False),
        sa.Column("sq_candidato", sa.Text(), nullable=False),
        sa.Column("nr_candidato", sa.Text(), nullable=False),
        sa.Column("nm_candidato", sa.Text(), nullable=False),
        sa.Column("nm_urna_candidato", sa.Text(), nullable=False),
        sa.Column("nm_social_candidato", sa.Text(), nullable=False),
        sa.Column("nr_cpf_candidato", sa.Text(), nullable=False),
        sa.Column("ds_email", sa.Text(), nullable=False),
        sa.Column("cd_situacao_candidatura", sa.Text(), nullable=False),
        sa.Column("ds_situacao_candidatura", sa.Text(), nullable=False),
        sa.Column("tp_agremiacao", sa.Text(), nullable=False),
        sa.Column("nr_partido", sa.Text(), nullable=False),
        sa.Column("sg_partido", sa.Text(), nullable=False),
        sa.Column("nm_partido", sa.Text(), nullable=False),
        sa.Column("nr_federacao", sa.Text(), nullable=False),
        sa.Column("nm_federacao", sa.Text(), nullable=False),
        sa.Column("sg_federacao", sa.Text(), nullable=False),
        sa.Column("ds_composicao_federacao", sa.Text(), nullable=False),
        sa.Column("sq_coligacao", sa.Text(), nullable=False),
        sa.Column("nm_coligacao", sa.Text(), nullable=False),
        sa.Column("ds_composicao_coligacao", sa.Text(), nullable=False),
        sa.Column("sg_uf_nascimento", sa.Text(), nullable=False),
        sa.Column("dt_nascimento", sa.Text(), nullable=False),
        sa.Column("nr_titulo_eleitoral_candidato", sa.Text(), nullable=False),
        sa.Column("cd_genero", sa.Text(), nullable=False),
        sa.Column("ds_genero", sa.Text(), nullable=False),
        sa.Column("cd_grau_instrucao", sa.Text(), nullable=False),
        sa.Column("ds_grau_instrucao", sa.Text(), nullable=False),
        sa.Column("cd_estado_civil", sa.Text(), nullable=False),
        sa.Column("ds_estado_civil", sa.Text(), nullable=False),
        sa.Column("cd_cor_raca", sa.Text(), nullable=False),
        sa.Column("ds_cor_raca", sa.Text(), nullable=False),
        sa.Column("cd_ocupacao", sa.Text(), nullable=False),
        sa.Column("ds_ocupacao", sa.Text(), nullable=False),
        sa.Column("cd_sit_tot_turno", sa.Text(), nullable=False),
        sa.Column("ds_sit_tot_turno", sa.Text(), nullable=False),
        sa.ForeignKeyConstraint(
            ["ingestion_run_id"],
            ["audit.ingestion_run.id"],
            name=op.f("fk_tse_candidate_ingestion_run_id_ingestion_run"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_tse_candidate")),
        sa.UniqueConstraint(
            "ingestion_run_id",
            "source_file",
            "source_row_number",
            name=op.f("uq_tse_candidate_ingestion_run_id"),
        ),
        schema="raw",
    )


def downgrade() -> None:
    op.drop_table("tse_candidate", schema="raw")
