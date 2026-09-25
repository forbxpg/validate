"""What the caller wants to see in the page."""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, TypeVar

if TYPE_CHECKING:
    from collections.abc import Awaitable, Sequence


DomainT_contra = TypeVar("DomainT_contra", contravariant=True)
OutT_co = TypeVar("OutT_co", covariant=True)


class Projection(Protocol[DomainT_contra, OutT_co]):
    """What the caller wants to see in the page."""

    def __call__(
        self,
        items: Sequence[DomainT_contra],
        /,
    ) -> Sequence[OutT_co] | Awaitable[Sequence[OutT_co]]:
        """Project domain objects into what the page returns.

        Args:
            items: Sequence[DomainT_contra] - Domain objects of one page.

        Returns:
            Sequence[OutT_co] | Awaitable[Sequence[OutT_co]] - The projected items,
                directly or after an await.

        """
        ...
