"""Page and page parameters as protocols, so that core never imports the library."""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, TypeVar, runtime_checkable

if TYPE_CHECKING:
    from collections.abc import Sequence

ItemT_co = TypeVar("ItemT_co", covariant=True)


@runtime_checkable
class PageParams(Protocol):
    """The boundaries of the page, coming from the request."""

    def to_raw_params(self) -> object:
        """Reduce the parameters to the boundaries of the selection.

        Returns:
            object - The boundaries in the form understandable by
            the implementation of the pagination.

        """
        ...


@runtime_checkable
class Page(Protocol[ItemT_co]):
    """The collected page of the output."""

    @property
    def items(self) -> Sequence[ItemT_co]:
        """The lines of the page.

        Returns:
            Sequence[ItemT_co] - The elements in the order of selection.

        """
        ...
