"""Declarative base and naming conventions for the ORM metadata."""

from sqlalchemy import MetaData
from sqlalchemy.orm import DeclarativeBase

NAMING_CONVENTION = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_N_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_N_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(DeclarativeBase):
    """Declarative base shared by every ORM model.

    All model metadata is bound to a single ``MetaData`` instance that
    enforces a deterministic naming convention for constraints and
    indexes, so Alembic autogenerates stable, predictable migration
    diffs instead of dialect-assigned names.
    """

    metadata = MetaData(naming_convention=NAMING_CONVENTION)
