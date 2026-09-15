import sqlalchemy as sa

from wv_eleicoes_data.db.base import Base
from wv_eleicoes_data.db.models import Person, PersonExternalIdentifier

PERSON = Person.__table__
IDENTIFIER = PersonExternalIdentifier.__table__


def test_person_is_stable_core_identity() -> None:
    assert PERSON.schema == "core"
    assert PERSON.name == "person"
    assert Base.metadata.tables["core.person"] is PERSON
    assert list(PERSON.primary_key.columns.keys()) == ["id"]
    assert PERSON.c.id.autoincrement is True
    assert not PERSON.c.legal_name.nullable
    assert not PERSON.c.display_name.nullable
    assert isinstance(PERSON.c.birth_date.type, sa.Date)
    assert isinstance(PERSON.c.created_at.type, sa.DateTime)
    assert PERSON.c.created_at.type.timezone
    assert PERSON.c.updated_at.type.timezone
    assert {index.name for index in PERSON.indexes} == {"ix_core_person_display_name"}


def test_external_identifier_has_source_type_value_and_scope() -> None:
    assert IDENTIFIER.schema == "core"
    assert IDENTIFIER.name == "person_external_identifier"
    assert Base.metadata.tables["core.person_external_identifier"] is IDENTIFIER
    (foreign_key,) = IDENTIFIER.c.person_id.foreign_keys
    assert foreign_key.target_fullname == "core.person.id"
    assert foreign_key.ondelete == "CASCADE"

    unique_constraints = [
        constraint
        for constraint in IDENTIFIER.constraints
        if isinstance(constraint, sa.UniqueConstraint)
    ]
    assert len(unique_constraints) == 1
    assert list(unique_constraints[0].columns.keys()) == [
        "source_system",
        "identifier_type",
        "identifier_value",
        "scope_key",
    ]
    assert IDENTIFIER.c.scope_key.server_default is not None
    assert IDENTIFIER.c.is_public.server_default is not None


def test_core_identity_does_not_persist_tse_cpf() -> None:
    all_columns = set(PERSON.columns.keys()) | set(IDENTIFIER.columns.keys())
    assert "cpf" not in all_columns
    assert "nr_cpf_candidato" not in all_columns
    assert "candidacy_sequence" not in PERSON.columns
