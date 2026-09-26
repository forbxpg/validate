"""Field types shared by the response models: tolerant scalars and identifiers."""

from __future__ import annotations

from collections.abc import Sequence
from decimal import Decimal
from typing import TYPE_CHECKING, Annotated

from pydantic import BeforeValidator

from vld.crossref.errors import CrossrefQueryError
from vld.crossref.ids import normalize_doi, normalize_issn, normalize_orcid

from ._lenient import degraded, lenient

if TYPE_CHECKING:
    from collections.abc import Callable

    from pydantic import ValidationInfo


def _scalar_text(value: object) -> object:
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return str(value)
    return value


OptStr = Annotated[str | None, BeforeValidator(_scalar_text), lenient(None)]
"""Text; a number is read as text, anything else malformed as None."""

OptInt = Annotated[int | None, lenient(None)]
OptFloat = Annotated[float | None, lenient(None)]
OptBool = Annotated[bool | None, lenient(None)]
OptDecimal = Annotated[Decimal | None, lenient(None)]


def _or_none(
    normalize: Callable[[str], str],
) -> Callable[[object, ValidationInfo], object]:
    def _apply(value: object, info: ValidationInfo) -> object:
        if not isinstance(value, str):
            return value
        try:
            return normalize(value)
        except CrossrefQueryError as error:
            degraded(info.field_name, str(error))
            return None

    return _apply


def _each_valid(
    normalize: Callable[[str], str],
) -> Callable[[object, ValidationInfo], object]:
    def _apply(value: object, info: ValidationInfo) -> object:
        if isinstance(value, str):
            value = [value]
        if not isinstance(value, Sequence):
            return value
        kept: list[str] = []
        for item in value:
            if not isinstance(item, str):
                continue
            try:
                kept.append(normalize(item))
            except CrossrefQueryError as error:
                degraded(info.field_name, str(error))
        return tuple(dict.fromkeys(kept))

    return _apply


def _strict(normalize: Callable[[str], str]) -> Callable[[object], object]:
    def _apply(value: object) -> object:
        if not isinstance(value, str):
            return value
        try:
            return normalize(value)
        except CrossrefQueryError as error:
            raise ValueError(str(error)) from error

    return _apply


Doi = Annotated[str, BeforeValidator(_strict(normalize_doi))]
"""A DOI that must be valid: the identity of a work."""

OptDoi = Annotated[str | None, BeforeValidator(_or_none(normalize_doi)), lenient(None)]
OptIssn = Annotated[
    str | None,
    BeforeValidator(_or_none(normalize_issn)),
    lenient(None),
]
OptOrcid = Annotated[
    str | None,
    BeforeValidator(_or_none(normalize_orcid)),
    lenient(None),
]

IssnList = Annotated[
    tuple[str, ...],
    BeforeValidator(_each_valid(normalize_issn)),
    lenient(()),
]
"""ISSNs, normalized; an invalid one is dropped with a warning."""
