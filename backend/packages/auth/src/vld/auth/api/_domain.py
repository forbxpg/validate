"""Descriptor of auth: router, error registry and providers as one object."""

from __future__ import annotations

from vld.auth.api.routers import router
from vld.auth.di import AUTH_PROVIDERS
from vld.web.mounting import DomainDescriptor

from ._errors import AUTH_ERRORS
from ._startup import startup

AUTH_DOMAIN = DomainDescriptor(
    router=router,
    errors=AUTH_ERRORS,
    providers=AUTH_PROVIDERS,
    on_startup=startup,
)
