"""Classification of PostgreSQL integrity violations: uniqueness and foreign key."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from sqlalchemy.exc import IntegrityError


_UNIQUE_VIOLATION = "23505"
"""SQLSTATE violation of uniqueness in PostgreSQL."""

_FOREIGN_KEY_VIOLATION = "23503"
"""SQLSTATE violation of foreign key in PostgreSQL."""


def _attr_in_chain(exc: BaseException | None, name: str) -> object | None:
    """Find an attribute in the chain of exception causes.

    Args:
        exc: BaseException | None - Exception, from which to start the traversal.
        name: str - Name of the desired attribute.

    Returns:
        object | None - The first non-empty value or None.

    """
    while exc is not None:
        value: object | None = getattr(exc, name, None)
        if value:
            return value
        exc = exc.__cause__
    return None


def _violates(exc: IntegrityError, sqlstate: str, constraint_name: str) -> bool:
    """Compare the SQLSTATE of the rejection and the name of the constraint that raised it.

    Args:
        exc: IntegrityError - Exception raised on insertion or flush.
        sqlstate: str - Expected PostgreSQL state code.
        constraint_name: str - Name of the expected constraint.

    Returns:
        bool - Whether the code and name matched.

    """
    if _attr_in_chain(exc.orig, "sqlstate") != sqlstate:
        return False
    constraint = _attr_in_chain(exc.orig, "constraint_name")
    return str(constraint) == constraint_name


def is_unique_violation(exc: IntegrityError, constraint_name: str) -> bool:
    """Understand that the insertion was rejected by the named unique index.

    Args:
        exc: IntegrityError - Exception raised on flush.
        constraint_name: str - Name of the expected unique index.

    Returns:
        bool - Whether the named unique index was violated.

    """
    return _violates(exc, _UNIQUE_VIOLATION, constraint_name)


def is_foreign_key_violation(exc: IntegrityError, constraint_name: str) -> bool:
    """Understand that the insertion was rejected by the named foreign key.

    Args:
        exc: IntegrityError - Exception raised on insertion or flush.
        constraint_name: str - Name of the expected foreign key.

    Returns:
        bool - Whether the named foreign key was violated.

    """
    return _violates(exc, _FOREIGN_KEY_VIOLATION, constraint_name)
