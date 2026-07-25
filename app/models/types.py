"""
Portable column types.

`GUID` is a database-agnostic UUID type. On PostgreSQL it maps to the native
`uuid` column (identical DDL and storage to the previous
``postgresql.UUID(as_uuid=True)``), so production schema and data are
unchanged. On other backends (e.g. SQLite used by the test suite) it stores a
36-char hyphenated string. Values are always read back as ``uuid.UUID`` and
accept either ``uuid.UUID`` or ``str`` on the way in.

This lets the app run its test suite on SQLite without a live PostgreSQL,
while remaining byte-for-byte compatible with the existing PostgreSQL database.
"""
import uuid

from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.types import CHAR, TypeDecorator


class GUID(TypeDecorator):
    """Platform-independent UUID type (native uuid on PostgreSQL, CHAR(36) elsewhere)."""

    impl = CHAR
    cache_ok = True

    def load_dialect_impl(self, dialect):
        if dialect.name == "postgresql":
            return dialect.type_descriptor(PG_UUID(as_uuid=True))
        return dialect.type_descriptor(CHAR(36))

    def process_bind_param(self, value, dialect):
        if value is None:
            return value
        if not isinstance(value, uuid.UUID):
            value = uuid.UUID(str(value))
        if dialect.name == "postgresql":
            return value  # native UUID type handles uuid.UUID directly
        return str(value)

    def process_result_value(self, value, dialect):
        if value is None:
            return value
        if isinstance(value, uuid.UUID):
            return value
        return uuid.UUID(str(value))
