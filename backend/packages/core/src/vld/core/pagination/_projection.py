"""What the caller wants to see in the page."""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, TypeVar

if TYPE_CHECKING:
    from collections.abc import Awaitable, Sequence


DomainT_contra = TypeVar("DomainT_contra", contravariant=True)
OutT_co = TypeVar("OutT_co", covariant=True)

OutT = TypeVar("OutT")


class Projection(Protocol[DomainT_contra, OutT_co]):
    """What the caller wants to see in the page."""

    def __call__(
        self,
        items: Sequence[DomainT_contra],
        /,
    ) -> Sequence[OutT_co] | Awaitable[Sequence[OutT_co]]: ...
