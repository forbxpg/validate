"""The auth router assembled from the process routers."""

from __future__ import annotations

from fastapi import APIRouter

from ._account import router as account_router
from ._administration import router as administration_router
from ._audit import router as audit_router
from ._common import ERROR_RESPONSES
from ._password import router as password_router
from ._registration import router as registration_router
from ._sessions import router as sessions_router

# The root adds the API version when mounting; here are only the paths of the domain.
_auth_router = APIRouter(prefix="/auth", tags=["auth"], responses=ERROR_RESPONSES)
_auth_router.include_router(registration_router)
_auth_router.include_router(sessions_router)
_auth_router.include_router(password_router)
_auth_router.include_router(account_router)

router = APIRouter()
router.include_router(_auth_router)
router.include_router(administration_router)
router.include_router(audit_router)
