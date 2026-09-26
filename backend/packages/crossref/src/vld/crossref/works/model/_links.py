"""Where a work lives: licenses, full-text links and its resource URLs."""

from __future__ import annotations

from typing import Annotated

from pydantic import Field

from vld.crossref.models import (
    CrossrefModel,
    CrossrefTimestamp,
    OptInt,
    OptStr,
    lenient,
)


class License(CrossrefModel):
    """A license of a work.

    Attributes:
        url: str | None - Link to the license.
        start: CrossrefTimestamp | None - When it starts to apply.
        delay_in_days: int | None - Days after publication it applies.
        content_version: str | None - ``vor``, ``am``, ``tdm`` or ``stm-asf``.

    """

    url: OptStr = Field(default=None, alias="URL")
    start: Annotated[CrossrefTimestamp | None, lenient(None)] = None
    delay_in_days: OptInt = Field(default=None, alias="delay-in-days")
    content_version: OptStr = Field(default=None, alias="content-version")


class Link(CrossrefModel):
    """A full-text link.

    Attributes:
        url: str | None - The link.
        content_type: str | None - MIME type.
        content_version: str | None - Version of the content.
        intended_application: str | None - ``text-mining``, ``similarity-checking``
            or ``unspecified``.

    """

    url: OptStr = Field(default=None, alias="URL")
    content_type: OptStr = Field(default=None, alias="content-type")
    content_version: OptStr = Field(default=None, alias="content-version")
    intended_application: OptStr = Field(default=None, alias="intended-application")


class ResourceUrl(CrossrefModel):
    """A URL the DOI resolves to.

    Attributes:
        url: str | None - The URL.
        label: str | None - Label of a secondary URL.

    """

    url: OptStr = Field(default=None, alias="URL")
    label: OptStr = None


class Resources(CrossrefModel):
    """The URLs the DOI resolves to.

    Attributes:
        primary: ResourceUrl | None - The main URL.
        secondary: tuple[ResourceUrl, ...] - Other URLs.

    """

    primary: Annotated[ResourceUrl | None, lenient(None)] = None
    secondary: Annotated[tuple[ResourceUrl, ...], lenient(())] = ()
