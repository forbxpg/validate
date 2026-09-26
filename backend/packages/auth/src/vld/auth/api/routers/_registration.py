"""Endpoints of registration and address confirmation."""

from __future__ import annotations

from http import HTTPStatus

from dishka.integrations.fastapi import DishkaRoute, FromDishka
from fastapi import APIRouter, Request

from vld.auth.api.schemas import (
    RegisterRequest,
    RegisterResponse,
    ResendVerificationRequest,
    VerifyEmailRequest,
)
from vld.auth.application import (
    RateLimiter,
    RegisterCommand,
    RegisterUser,
    ResendVerification,
    ResendVerificationCommand,
    VerifyEmail,
)
from vld.web.access import public
from vld.web.throttling import throttle_by_ip

from ._throttle import (
    REGISTER_IP_LIMIT,
    REGISTER_IP_WINDOW_MS,
    RESEND_IP_LIMIT,
    RESEND_IP_WINDOW_MS,
)

router = APIRouter(route_class=DishkaRoute, tags=["registration"])


_REGISTER_SUMMARY = (
    "Register a user; the confirmation letter leaves through the outbox."
)
_VERIFY_EMAIL_SUMMARY = "Confirm an address by the token from the letter."
_RESEND_VERIFICATION_SUMMARY = "Send the confirmation letter again."


@router.post(
    "/register",
    status_code=HTTPStatus.CREATED,
    response_model=RegisterResponse,
    dependencies=[public()],
    summary=_REGISTER_SUMMARY,
)
async def register(
    body: RegisterRequest,
    request: Request,
    use_case: FromDishka[RegisterUser],
    limiter: FromDishka[RateLimiter],
) -> RegisterResponse:
    """Register a user; the confirmation letter leaves through the outbox.

    Args:
        body: RegisterRequest - Registration data.
        request: Request - Request, the client address comes from it.
        use_case: RegisterUser - The use case.
        limiter: RateLimiter - Attempt limiter.

    Returns:
        RegisterResponse - Id of the new account.

    """
    await throttle_by_ip(
        limiter,
        request,
        "register",
        REGISTER_IP_LIMIT,
        REGISTER_IP_WINDOW_MS,
    )
    user_id = await use_case(
        RegisterCommand(
            email=body.email,
            password=body.password,
            role=body.role,
            profile=body.profile.to_domain(),
        ),
    )
    return RegisterResponse(user_id=str(user_id))


@router.post(
    "/verify-email",
    status_code=HTTPStatus.NO_CONTENT,
    dependencies=[public()],
    summary=_VERIFY_EMAIL_SUMMARY,
)
async def verify_email(
    body: VerifyEmailRequest,
    use_case: FromDishka[VerifyEmail],
) -> None:
    """Confirm an address by the token from the letter.

    Args:
        body: VerifyEmailRequest - The token.
        use_case: VerifyEmail - The use case.

    """
    await use_case(body.token)


@router.post(
    "/verification/resend",
    status_code=HTTPStatus.ACCEPTED,
    dependencies=[public()],
    summary=_RESEND_VERIFICATION_SUMMARY,
)
async def resend_verification(
    body: ResendVerificationRequest,
    request: Request,
    use_case: FromDishka[ResendVerification],
    limiter: FromDishka[RateLimiter],
) -> None:
    """Send the confirmation letter again.

    Args:
        body: ResendVerificationRequest - Address for the letter.
        request: Request - Request, the client address comes from it.
        use_case: ResendVerification - The use case.
        limiter: RateLimiter - Attempt limiter.

    """
    await throttle_by_ip(
        limiter,
        request,
        "resend_verification",
        RESEND_IP_LIMIT,
        RESEND_IP_WINDOW_MS,
    )
    await use_case(ResendVerificationCommand(email=body.email))
