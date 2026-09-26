"""Tolerance: a bad field reads as empty, a record without identity is dropped."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from contextvars import ContextVar
from typing import TYPE_CHECKING, Annotated, cast

from pydantic import BeforeValidator, ValidationError, WrapValidator
from structlog.stdlib import get_logger as structlog_get_logger

if TYPE_CHECKING:
    from pydantic import BaseModel, ValidationInfo, ValidatorFunctionWrapHandler
    from structlog.stdlib import BoundLogger


_log: BoundLogger = structlog_get_logger("vld.crossref")
current_record: ContextVar[str | None] = ContextVar("crossref.record", default=None)
"""DOI or ISSN of the record being read, for the warnings of its fields."""


def degraded(field: str | None, error: str) -> None:
    """Log that a field was read as empty.

    Args:
        field: str | None - Name of the field.
        error: str - What was wrong with the value.

    """
    _log.warning(
        "crossref_field_degraded",
        field=field,
        record=current_record.get(),
        error=error,
    )


def lenient(empty: object) -> WrapValidator:
    """Make a field fall back to `empty` instead of failing its record.

    Put it last in `Annotated`: it must wrap every other validator of the field.
    `null` reads as `empty` without a warning: Crossref sends it often.

    Args:
        empty: object - Value of the field when its data is malformed.

    Returns:
        WrapValidator - The validator for `Annotated`.

    """

    def _validate(
        value: object,
        handler: ValidatorFunctionWrapHandler,
        info: ValidationInfo,
    ) -> object:
        if value is None:
            return empty
        try:
            return cast("object", handler(value))
        except ValidationError as error:
            degraded(info.field_name, str(error.errors()[0]["msg"]))
            return empty

    return WrapValidator(_validate)


def _one_or_many(value: object) -> object:
    if value is None:
        return ()
    if isinstance(value, str):
        return (value,)
    return value


def _clean(value: object) -> object:
    if isinstance(value, Sequence) and not isinstance(value, str):
        return tuple(item for item in value if isinstance(item, str) and item.strip())
    return value


StrList = Annotated[
    tuple[str, ...],
    BeforeValidator(_one_or_many),
    lenient(()),
]
"""A list of strings; one string is a list of one, null is empty."""


CleanStrList = Annotated[
    tuple[str, ...],
    BeforeValidator(_clean),
    BeforeValidator(_one_or_many),
    lenient(()),
]
"""A list of strings without nulls, blanks and non-strings."""


def parse_item[T: BaseModel](model: type[T], raw: object, *, id_key: str) -> T | None:
    """Read one record; drop it with a warning when its identity is broken.

    Args:
        model: type[T] - Model of the record.
        raw: object - The record as Crossref sent it.
        id_key: str - Key of the identity in the raw record, for the warnings.

    Returns:
        T | None - The record, or None when it cannot be read at all.

    """
    record = (
        cast("Mapping[str, object]", raw).get(id_key)
        if isinstance(raw, Mapping)
        else None
    )
    token = current_record.set(str(record) if record is not None else None)
    try:
        return model.model_validate(raw)
    except ValidationError as exc:
        _log.warning(
            "crossref_item_dropped",
            model=model.__name__,
            record=current_record.get(),
            error=exc.errors()[0]["msg"],
        )
        return None
    finally:
        current_record.reset(token)
