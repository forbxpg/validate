"""The error table of auth: complete and meaningful."""

from __future__ import annotations

import importlib
import pkgutil

import vld.auth
from vld.auth.api import AUTH_DOMAIN, AuthErrorCode, AuthErrorResponse
from vld.auth.application import RevocationCheckUnavailableError
from vld.auth.domain import (
    AccountDeactivatedError,
    AccountGoneError,
    AuthDomainError,
    EntityNotFoundError,
)
from vld.web.errors import ErrorResponse

# The table of the descriptor is exactly the one the application mounts.
AUTH_ERRORS = AUTH_DOMAIN.errors


def _import_every_module() -> None:
    """Import every module of the domain."""
    for module in pkgutil.walk_packages(vld.auth.__path__, "vld.auth."):
        if ".migrations" in module.name:
            continue
        _ = importlib.import_module(module.name)


def _descendants(base: type[Exception]) -> set[type[Exception]]:
    """Collect every descendant."""
    found: set[type[Exception]] = set()
    for child in base.__subclasses__():
        found.add(child)
        found |= _descendants(child)
    return found


def test_every_domain_error_is_mapped() -> None:
    """Every domain error has an entry."""
    _import_every_module()
    unmapped = _descendants(AuthDomainError) - set(AUTH_ERRORS.mapping)

    assert unmapped == set()


def test_the_walk_actually_finds_something() -> None:
    """The walk is not vacuous."""
    _import_every_module()
    assert len(_descendants(AuthDomainError)) > 10


def test_every_code_belongs_to_the_enum() -> None:
    """A code outside the enum would miss the OpenAPI enum."""
    codes = {spec.code for spec in AUTH_ERRORS.mapping.values()}

    assert codes <= set(AuthErrorCode)


def test_the_refresh_outcomes_have_different_codes() -> None:
    """Deactivated and deleted are different screens for the client."""
    codes = {
        AUTH_ERRORS.mapping[error].code
        for error in (AccountGoneError, AccountDeactivatedError)
    }

    assert len(codes) == 2


def test_unavailable_revocation_store_is_503_with_retry_after() -> None:
    """A 401 here would log everyone out during a Redis flap."""
    spec = AUTH_ERRORS.mapping[RevocationCheckUnavailableError]

    assert spec.status == 503
    assert spec.retry_after is not None


def test_entity_not_found_is_500_not_404() -> None:
    """A missing row behind a valid reference is a defect, not a 404."""
    assert AUTH_ERRORS.mapping[EntityNotFoundError].status == 500


def test_auth_error_response_keeps_the_shape_of_the_common_one() -> None:
    """The narrowed response keeps the common shape; only a test can hold that."""
    assert set(AuthErrorResponse.model_fields) == set(ErrorResponse.model_fields)


def test_no_orphan_codes_in_the_enum() -> None:
    """No code of the enum is left unused."""
    used = {spec.code for spec in AUTH_ERRORS.mapping.values()}

    assert set(AuthErrorCode) - used == set()
