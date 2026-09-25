"""Composition root of the HTTP API: `uvicorn vld.api.main:create_app --factory`."""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import TYPE_CHECKING, cast, final

from dishka import Provider, Scope, from_context, make_async_container
from dishka.integrations.fastapi import setup_dishka
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from vld.core.config import CorsSettings, ObservabilitySettings
from vld.core.di import CONTAINER_VALIDATION, CoreProvider
from vld.core.obs import configure_logging, configure_sentry
from vld.web.errors import REQUEST_ID_HEADER_NAME, RequestIdMiddleware
from vld.web.mounting import DomainDescriptor, mount
from vld.web.throttling.di import ThrottlingProvider

from ._health import router as health_router

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator

    from dishka import AsyncContainer

API_PREFIX = "/api/v1"

DOMAINS: tuple[DomainDescriptor, ...] = ()
"""Every domain the API serves: a new domain is one more descriptor here."""


@final
class _ApiProvider(Provider):
    """Values the API reads before its container exists."""

    cors = from_context(provides=CorsSettings, scope=Scope.APP)


@asynccontextmanager
async def _lifespan(app: FastAPI) -> AsyncGenerator[None]:
    """Run the startup checks of the domains and close the container on shutdown.

    Args:
        app: FastAPI - Application.

    Yields:
        None - While the application serves requests.

    """
    container = cast("AsyncContainer", app.state.dishka_container)
    for domain in DOMAINS:
        if domain.on_startup is not None:
            await domain.on_startup(container)
    try:
        yield
    finally:
        await container.close()


def create_app() -> FastAPI:
    """Build the API application from the environment.

    Returns:
        FastAPI - Application with domains, middleware and the container.

    """
    observability = ObservabilitySettings()
    configure_logging(observability)
    configure_sentry(observability)
    cors = CorsSettings()  # pyright: ignore[reportCallIssue] -- required, read from the environment

    container = make_async_container(
        CoreProvider(),
        ThrottlingProvider(),
        _ApiProvider(),
        *(provider for domain in DOMAINS for provider in domain.providers),
        context={CorsSettings: cors},
        validation_settings=CONTAINER_VALIDATION,
    )
    app = FastAPI(title="validate", lifespan=_lifespan)
    app.include_router(health_router)
    mount(app, *DOMAINS, prefix=API_PREFIX)
    app.add_middleware(RequestIdMiddleware)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=cors.allowed_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
        expose_headers=[REQUEST_ID_HEADER_NAME],
    )
    setup_dishka(container, app)
    return app
