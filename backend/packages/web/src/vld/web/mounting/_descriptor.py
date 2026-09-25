"""Descriptor of the domain: everything that the root must mount, as one object."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

    from dishka import AsyncContainer, Provider
    from fastapi import APIRouter

    from vld.web.errors import ErrorRegistry


@dataclass(frozen=True, slots=True)
class DomainDescriptor:
    """HTTP representation of the domain as a whole.

    Attributes:
        router: APIRouter - Domain router.
        errors: ErrorRegistry - Table «domain error -> how it looks outside».
        providers: tuple[Provider...] - DI providers of the domain for the container
            of the composite root.
        on_startup: Callable[[AsyncContainer], Awaitable[None]] | None - Startup
            procedure of the domain.

    """

    router: APIRouter
    errors: ErrorRegistry
    providers: tuple[Provider, ...]
    on_startup: Callable[[AsyncContainer], Awaitable[None]] | None = None
