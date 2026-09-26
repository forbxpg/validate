"""Base of every Crossref model: frozen, by alias or name, unknown fields ignored."""

from __future__ import annotations

from typing import ClassVar

from pydantic import BaseModel, ConfigDict


class CrossrefModel(BaseModel):
    """A value read from Crossref.

    Unknown fields are ignored: a field Crossref adds tomorrow breaks nothing.
    """

    model_config: ClassVar[ConfigDict] = ConfigDict(
        frozen=True,
        extra="ignore",
        validate_by_alias=True,
        validate_by_name=True,
    )
