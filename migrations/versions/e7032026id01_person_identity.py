"""Stable political-person identity and scoped external identifiers."""

import sqlalchemy as sa
from alembic import op

revision = "e7032026id01"
down_revision = "d6922026ca03"
branch_labels = None
depends_on = None

SYNC_FUNCTION = r"""
CREATE OR REPLACE FUNCTION core.sync_person_identity_from_tse()
RETURNS integer
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = pg_catalog, pg_temp
AS $$
DECLARE
    inserted_identifiers integer := 0;
BEGIN
    DROP TABLE IF EXISTS pg_temp.person_identity_candidates;
    DROP TABLE IF EXISTS pg_temp.person_identity_map;

    CREATE TEMP TABLE person_identity_candidates ON COMMIT DROP AS
    WITH source_rows AS (
        SELECT
            r.id AS raw_candidate_id,
            r.ano_eleicao,
            r.cd_eleicao,
            r.sq_candidato,
            CASE
                WHEN regexp_replace(btrim(r.nr_cpf_candidato), '[^0-9]', '', 'g')
                     ~ '^[0-9]{11}$'
                THEN 'tse:cpf:' ||
                     regexp_replace(btrim(r.nr_cpf_candidato), '[^0-9]', '', 'g')
                ELSE 'tse:candidacy:' || btrim(r.ano_eleicao) || ':' ||
                     btrim(r.cd_eleicao) || ':' || btrim(r.sq_candidato)
            END AS identity_key,
            CASE
                WHEN btrim(r.nm_candidato) NOT IN
                     ('', '#NULO', '#NE', 'NÃO DIVULGÁVEL', '-1', '-3', '-4')
                THEN btrim(r.nm_candidato)
                WHEN btrim(r.nm_urna_candidato) NOT IN
                     ('', '#NULO', '#NE', 'NÃO DIVULGÁVEL', '-1', '-3', '-4')
                THEN btrim(r.nm_urna_candidato)
                ELSE 'Pessoa ' || btrim(r.sq_candidato)
            END AS legal_name,
            CASE
                WHEN btrim(r.nm_social_candidato) NOT IN
                     ('', '#NULO', '#NE', 'NÃO DIVULGÁVEL', '-1', '-3', '-4')
                THEN btrim(r.nm_social_candidato)
            END AS social_name,
            CASE
                WHEN btrim(r.nm_urna_candidato) NOT IN
                     ('', '#NULO', '#NE', 'NÃO DIVULGÁVEL', '-1', '-3', '-4')
                THEN btrim(r.nm_urna_candidato)
            END AS ballot_name,
            CASE
                WHEN btrim(r.dt_nascimento) ~ '^[0-9]{2}/[0-9]{2}/[0-9]{4}$'
                     AND to_char(
                         to_date(btrim(r.dt_nascimento), 'DD/MM/YYYY'),
                         'DD/MM/YYYY'
                     ) = btrim(r.dt_nascimento)
                THEN to_date(btrim(r.dt_nascimento), 'DD/MM/YYYY')
            END AS birth_date,
            CASE
                WHEN btrim(r.sg_uf_nascimento) ~ '^[A-Za-z]{2}$'
                THEN upper(btrim(r.sg_uf_nascimento))
            END AS birth_uf,
            ir.finished_at
        FROM raw.tse_candidate AS r
        JOIN audit.ingestion_run AS ir ON ir.id = r.ingestion_run_id
        WHERE ir.status = 'success'
          AND ir.source = 'TSE'
          AND ir.dataset = 'candidatos'
          AND btrim(r.ano_eleicao) NOT IN
              ('', '#NULO', '#NE', 'NÃO DIVULGÁVEL', '-1', '-3', '-4')
          AND btrim(r.cd_eleicao) NOT IN
              ('', '#NULO', '#NE', 'NÃO DIVULGÁVEL', '-1', '-3', '-4')
          AND btrim(r.sq_candidato) NOT IN
              ('', '#NULO', '#NE', 'NÃO DIVULGÁVEL', '-1', '-3', '-4')
    )
    SELECT
        source_rows.*,
        row_number() OVER (
            PARTITION BY identity_key
            ORDER BY finished_at DESC NULLS LAST, raw_candidate_id DESC
        ) AS profile_rank
    FROM source_rows;

    CREATE TEMP TABLE person_identity_map (
        identity_key text PRIMARY KEY,
        person_id bigint NOT NULL
    ) ON COMMIT DROP;

    INSERT INTO person_identity_map (identity_key, person_id)
    SELECT DISTINCT ON (c.identity_key)
        c.identity_key,
        identifier.person_id
    FROM person_identity_candidates AS c
    JOIN core.person_external_identifier AS identifier
      ON identifier.source_system = 'TSE'
     AND identifier.identifier_type = 'candidacy_sequence'
     AND identifier.identifier_value = btrim(c.sq_candidato)
     AND identifier.scope_key =
         'election:' || btrim(c.ano_eleicao) || ':' || btrim(c.cd_eleicao)
    ORDER BY c.identity_key, identifier.person_id;

    INSERT INTO person_identity_map (identity_key, person_id)
    SELECT
        c.identity_key,
        nextval(pg_get_serial_sequence('core.person', 'id'))
    FROM person_identity_candidates AS c
    WHERE c.profile_rank = 1
      AND NOT EXISTS (
          SELECT 1
          FROM person_identity_map AS existing
          WHERE existing.identity_key = c.identity_key
      );

    INSERT INTO core.person (
        id,
        legal_name,
        display_name,
        social_name,
        birth_date,
        birth_uf
    )
    SELECT
        identity.person_id,
        c.legal_name,
        coalesce(c.social_name, c.ballot_name, c.legal_name),
        c.social_name,
        c.birth_date,
        c.birth_uf
    FROM person_identity_map AS identity
    JOIN person_identity_candidates AS c
      ON c.identity_key = identity.identity_key
     AND c.profile_rank = 1
    LEFT JOIN core.person AS existing ON existing.id = identity.person_id
    WHERE existing.id IS NULL;

    UPDATE core.person AS person
    SET
        legal_name = c.legal_name,
        display_name = coalesce(c.social_name, c.ballot_name, c.legal_name),
        social_name = c.social_name,
        birth_date = c.birth_date,
        birth_uf = c.birth_uf,
        updated_at = now()
    FROM person_identity_map AS identity
    JOIN person_identity_candidates AS c
      ON c.identity_key = identity.identity_key
     AND c.profile_rank = 1
    WHERE person.id = identity.person_id
      AND (
          person.legal_name,
          person.display_name,
          person.social_name,
          person.birth_date,
          person.birth_uf
      ) IS DISTINCT FROM (
          c.legal_name,
          coalesce(c.social_name, c.ballot_name, c.legal_name),
          c.social_name,
          c.birth_date,
          c.birth_uf
      );

    INSERT INTO core.person_external_identifier (
        person_id,
        source_system,
        identifier_type,
        identifier_value,
        scope_key,
        is_public
    )
    SELECT DISTINCT
        identity.person_id,
        'TSE',
        'candidacy_sequence',
        btrim(c.sq_candidato),
        'election:' || btrim(c.ano_eleicao) || ':' || btrim(c.cd_eleicao),
        true
    FROM person_identity_candidates AS c
    JOIN person_identity_map AS identity
      ON identity.identity_key = c.identity_key
    ON CONFLICT (
        source_system,
        identifier_type,
        identifier_value,
        scope_key
    ) DO NOTHING;

    GET DIAGNOSTICS inserted_identifiers = ROW_COUNT;
    RETURN inserted_identifiers;
END;
$$
"""


def upgrade() -> None:
    op.create_table(
        "person",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("legal_name", sa.Text(), nullable=False),
        sa.Column("display_name", sa.Text(), nullable=False),
        sa.Column("social_name", sa.Text(), nullable=True),
        sa.Column("birth_date", sa.Date(), nullable=True),
        sa.Column("birth_uf", sa.String(length=2), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id", name="pk_person"),
        schema="core",
    )
    op.create_index(
        "ix_core_person_display_name",
        "person",
        ["display_name"],
        schema="core",
    )

    op.create_table(
        "person_external_identifier",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("person_id", sa.BigInteger(), nullable=False),
        sa.Column("source_system", sa.String(length=32), nullable=False),
        sa.Column("identifier_type", sa.String(length=64), nullable=False),
        sa.Column("identifier_value", sa.Text(), nullable=False),
        sa.Column(
            "scope_key",
            sa.Text(),
            server_default=sa.text("'global'"),
            nullable=False,
        ),
        sa.Column(
            "is_public",
            sa.Boolean(),
            server_default=sa.text("true"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "btrim(source_system) <> ''",
            name="ck_person_external_identifier_source_system_not_blank",
        ),
        sa.CheckConstraint(
            "btrim(identifier_type) <> ''",
            name="ck_person_external_identifier_identifier_type_not_blank",
        ),
        sa.CheckConstraint(
            "btrim(identifier_value) <> ''",
            name="ck_person_external_identifier_identifier_value_not_blank",
        ),
        sa.CheckConstraint(
            "btrim(scope_key) <> ''",
            name="ck_person_external_identifier_scope_key_not_blank",
        ),
        sa.ForeignKeyConstraint(
            ["person_id"],
            ["core.person.id"],
            name="fk_person_external_identifier_person_id_person",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_person_external_identifier"),
        sa.UniqueConstraint(
            "source_system",
            "identifier_type",
            "identifier_value",
            "scope_key",
            name="uq_person_external_identifier_natural_key",
        ),
        schema="core",
    )
    op.create_index(
        "ix_core_person_external_identifier_person_source",
        "person_external_identifier",
        ["person_id", "source_system", "identifier_type"],
        schema="core",
    )

    for relation in ("core.person", "core.person_external_identifier"):
        op.execute(f"REVOKE ALL ON {relation} FROM PUBLIC, wv_eleicoes_ingestion")
        op.execute(f"GRANT SELECT ON {relation} TO wv_eleicoes_api")

    op.execute(
        "REVOKE ALL ON SEQUENCE core.person_id_seq "
        "FROM PUBLIC, wv_eleicoes_api, wv_eleicoes_ingestion"
    )
    op.execute(
        "REVOKE ALL ON SEQUENCE core.person_external_identifier_id_seq "
        "FROM PUBLIC, wv_eleicoes_api, wv_eleicoes_ingestion"
    )

    op.execute(SYNC_FUNCTION)
    op.execute(
        "REVOKE ALL ON FUNCTION core.sync_person_identity_from_tse() "
        "FROM PUBLIC, wv_eleicoes_api"
    )
    op.execute(
        "GRANT EXECUTE ON FUNCTION core.sync_person_identity_from_tse() "
        "TO wv_eleicoes_ingestion"
    )
    op.execute("SELECT core.sync_person_identity_from_tse()")


def downgrade() -> None:
    op.execute("DROP FUNCTION IF EXISTS core.sync_person_identity_from_tse()")
    op.drop_index(
        "ix_core_person_external_identifier_person_source",
        table_name="person_external_identifier",
        schema="core",
    )
    op.drop_table("person_external_identifier", schema="core")
    op.drop_index(
        "ix_core_person_display_name",
        table_name="person",
        schema="core",
    )
    op.drop_table("person", schema="core")
