"""Endpoints of a password: reset through a letter and change while logged in."""

from __future__ import annotations

from http import HTTPStatus

from dishka.integrations.fastapi import DishkaRoute, FromDishka
from fastapi import APIRouter, Request, Response

from vld.auth.api.schemas import (
    ChangePasswordRequest,
    NewPasswordRequest,
    PasswordResetRequest,
    TokenPairResponse,
)
from vld.auth.application import (
    ChangePassword,
    ChangePasswordCommand,
    RateLimiter,
    RequestPasswordReset,
    ResetPassword,
)
from vld.auth.config import JwtSettings
from vld.web.access import authenticated, current_identity, public
from vld.web.throttling import throttle_by_ip

from ._common import set_pair_cookies
from ._throttle import (
    PASSWORD_RESET_CONFIRM_IP_LIMIT,
    PASSWORD_RESET_CONFIRM_IP_WINDOW_MS,
    PASSWORD_RESET_IP_LIMIT,
    PASSWORD_RESET_IP_WINDOW_MS,
)

router = APIRouter(route_class=DishkaRoute, tags=["password"])


_REQUEST_PASSWORD_RESET_SUMMARY = "Ask for a letter with a reset link."  # ruff: ignore[hardcoded-password-string]
_RESET_PASSWORD_SUMMARY = "Set a password by the token from the letter."  # ruff: ignore[hardcoded-password-string]
_CHANGE_PASSWORD_SUMMARY = (
    "Change the password; every other session ends, this one gets a fresh pair."  # ruff: ignore[hardcoded-password-string]
)


@router.post(
    "/password/reset-request",
    status_code=HTTPStatus.ACCEPTED,
    dependencies=[public()],
    summary=_REQUEST_PASSWORD_RESET_SUMMARY,
)
async def request_password_reset(
    body: PasswordResetRequest,
    request: Request,
    use_case: FromDishka[RequestPasswordReset],
    limiter: FromDishka[RateLimiter],
) -> None:
    """Ask for a letter with a reset link.

    Args:
        body: PasswordResetRequest - Address typed in the form.
        request: Request - Request, the client address comes from it.
        use_case: RequestPasswordReset - The use case.
        limiter: RateLimiter - Attempt limiter.

    """
    await throttle_by_ip(
        limiter,
        request,
        "password_reset_request",
        PASSWORD_RESET_IP_LIMIT,
        PASSWORD_RESET_IP_WINDOW_MS,
    )
    await use_case(body.email)


@router.post(
    "/password/reset",
    status_code=HTTPStatus.NO_CONTENT,
    dependencies=[public()],
    summary=_RESET_PASSWORD_SUMMARY,
)
async def reset_password(
    body: NewPasswordRequest,
    request: Request,
    use_case: FromDishka[ResetPassword],
    limiter: FromDishka[RateLimiter],
) -> None:
    """Set a password by the token from the letter.

    Args:
        body: NewPasswordRequest - Token and new password.
        request: Request - Request, the client address comes from it.
        use_case: ResetPassword - The use case.
        limiter: RateLimiter - Attempt limiter.

    """
    await throttle_by_ip(
        limiter,
        request,
        "password_reset",
        PASSWORD_RESET_CONFIRM_IP_LIMIT,
        PASSWORD_RESET_CONFIRM_IP_WINDOW_MS,
    )
    await use_case(body.token, body.password)


@router.post(
    "/password/change",
    response_model=TokenPairResponse,
    dependencies=[authenticated()],
    summary=_CHANGE_PASSWORD_SUMMARY,
)
async def change_password(
    body: ChangePasswordRequest,
    request: Request,
    response: Response,
    use_case: FromDishka[ChangePassword],
    settings: FromDishka[JwtSettings],
) -> TokenPairResponse:
    """Change the password; every other session ends, this one gets a fresh pair.

    Args:
        body: ChangePasswordRequest - Current and new password.
        request: Request - Request, the identity comes from it.
        response: Response - Response the new cookies are set on.
        use_case: ChangePassword - The use case.
        settings: JwtSettings - Lifetimes of the cookies.

    Returns:
        TokenPairResponse - The fresh pair.

    """
    pair = await use_case(
        ChangePasswordCommand(
            user_id=current_identity(request).user_id,
            current_password=body.current_password,
            new_password=body.new_password,
        ),
    )
    set_pair_cookies(response, pair, settings)
    return TokenPairResponse(access=pair.access, refresh=pair.refresh)
