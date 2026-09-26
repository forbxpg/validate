"""Base of every query: frozen, no unknown fields, one error type for every mistake."""

from __future__ import annotations

import hashlib
import json
from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Annotated, ClassVar, Self

from pydantic import (
    BaseModel,
    BeforeValidator,
    ConfigDict,
    Field,
    ValidationError,
    model_validator,
)

from vld.crossref.errors import CrossrefQueryError

if TYPE_CHECKING:
    from pydantic import ModelWrapValidatorHandler

TEXT_MAX = 1000
"""Longest search text sent to Crossref."""


def _clean_text(value: object) -> object:
    if isinstance(value, str):
        return value.strip() or None
    return value


Text = Annotated[
    Annotated[str, Field(max_length=TEXT_MAX)] | None,
    BeforeValidator(_clean_text),
]
"""Search text: stripped, blank is None, at most 1000 characters."""


class QueryPart(BaseModel):
    """A part of a query: frozen, no unknown fields, mistakes are CrossrefQueryError.

    A typo in a field name or a value of the wrong type is a CrossrefQueryError,
    like every other mistake in a query.
    """

    model_config: ClassVar[ConfigDict] = ConfigDict(frozen=True, extra="forbid")

    @model_validator(mode="wrap")
    @classmethod
    def _as_query_error(
        cls,
        data: object,
        handler: ModelWrapValidatorHandler[Self],
    ) -> Self:
        """Turn a validation failure into a CrossrefQueryError.

        Args:
            data: object - Raw input.
            handler: ModelWrapValidatorHandler[Self] - The inner validation.

        Returns:
            Self - The query.

        Raises:
            CrossrefQueryError: If the input is not a valid query.

        """
        try:
            return handler(data)
        except ValidationError as error:
            raise CrossrefQueryError(str(error)) from error


class QueryModel(QueryPart, ABC):
    """A query: a value that can be stored, compared, logged and used as a key."""

    @abstractmethod
    def params(self) -> dict[str, str]:
        """Render the query into Crossref parameters.

        Returns:
            dict[str, str] - The parameters.

        """

    def fingerprint(self) -> str:
        """A stable key of the query, equal for equal queries.

        Returns:
            str - SHA-256 of the sorted rendered parameters.

        """
        canonical = json.dumps(sorted(self.params().items()), ensure_ascii=False)
        return hashlib.sha256(canonical.encode()).hexdigest()
