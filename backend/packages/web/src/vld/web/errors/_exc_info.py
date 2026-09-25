"""What can be safely said about an exception in observability."""

from __future__ import annotations

_BOUND_PARAMETER_ATTRS = ("params", "statement")


def carries_bound_parameters(exc: BaseException) -> bool:
    """Can the text of the exception contain values that have gone into the request.

    Args:
        exc: BaseException - Exception that is being logged.

    Returns:
        bool - True, if the exception has a form of a driver error level.

    """
    return all(hasattr(exc, name) for name in _BOUND_PARAMETER_ATTRS)


def safe_exc_info(exc: BaseException) -> BaseException | None:
    """Return the exception for `exc_info` or `None`, if it is dangerous.

    Args:
        exc: BaseException - Exception.

    Returns:
        BaseException | None - Exception or `None`.

    """
    return None if carries_bound_parameters(exc) else exc


def db_error_kind(exc: BaseException) -> str | None:
    """The type of the underlying driver error, if there is one.

    Args:
        exc: BaseException - Exception.

    Returns:
        str | None - The name of the reason type or `None`.

    """
    if not carries_bound_parameters(exc):
        return None
    orig: object = getattr(exc, "orig", None)
    return type(orig).__qualname__ if orig is not None else type(exc).__qualname__
