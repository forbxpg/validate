"""Row mapper and caller projection combined into a pagination transformer."""

from __future__ import annotations

from collections.abc import Sequence
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

    from ._projection import Projection


def transformer[ModelT, DomainT, OutT](
    mapper: Callable[[ModelT], DomainT],
    project: Projection[DomainT, OutT],
) -> Callable[[Sequence[ModelT]], Awaitable[Sequence[OutT]]]:
    """Collect the transformer: row -> aggregate -> projection.

    Args:
        mapper: Callable - The mapper of the row to the aggregate,
        from `infrastructure/mappers` of your domain.
        project: Projection - The projection of the caller in the domain types.

    Returns:
        Callable - The asynchronous transformer for `apaginate` function.

    """

    async def _transform(rows: Sequence[ModelT]) -> Sequence[OutT]:
        projected = project([mapper(row) for row in rows])
        if isinstance(projected, Sequence):
            return projected
        return await projected

    return _transform
