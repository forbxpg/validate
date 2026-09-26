"""Endpoints of a session: login, refresh, logout."""

from __future__ import annotations

from dataclasses import dataclass
from http import HTTPStatus
from typing import TYPE_CHECKING

from dishka.integrations.fastapi import DishkaRoute, FromDishka
from fastapi import APIRouter, Request, Response

from vld.auth.api.schemas import (
    LoginRequest,
    RefreshRequest,
    SessionRefreshedResponse,
    TokenPairResponse,
)
from vld.auth.application import (
    InvalidateSessions,
    LoginCommand,
    LoginWithPassword,
    Logout,
    RateLimiter,
    RefreshTokens,
)
from vld.auth.config import JwtSettings
from vld.web.access import (
    REFRESH_COOKIE,
    NotAuthenticatedError,
    authenticated,
    clear_session_cookies,
    current_identity,
    presented_access_token,
    public,
    self_authenticated,
)
from vld.web.throttling import throttle_by_ip

from ._common import DEVICE_COOKIE, set_device_cookie, set_pair_cookies
from ._throttle import LOGIN_IP_LIMIT, LOGIN_IP_WINDOW_MS

if TYPE_CHECKING:
    from vld.auth.application import TokenPair


router = APIRouter(route_class=DishkaRoute, tags=["sessions"])


# Explicit `response_model`: dishka wraps the endpoint, the annotation won't resolve.
@router.post("/login", response_model=TokenPairResponse, dependencies=[public()])
async def login(  # ruff: ignore[too-many-arguments, too-many-positional-arguments] -- FastAPI parameters
    body: LoginRequest,
    request: Request,
    response: Response,
    use_case: FromDishka[LoginWithPassword],
    limiter: FromDishka[RateLimiter],
    settings: FromDishka[JwtSettings],
) -> TokenPairResponse:
    """Log in by address and password.

    Args:
        body: LoginRequest - Login data.
        request: Request - Request: the client address and the device cookie.
        response: Response - Response the cookies are set on.
        use_case: LoginWithPassword - The use case.
        limiter: RateLimiter - Attempt limiter.
        settings: JwtSettings - Lifetimes of the cookies.

    Returns:
        TokenPairResponse - The pair.

    """
    await throttle_by_ip(limiter, request, "login", LOGIN_IP_LIMIT, LOGIN_IP_WINDOW_MS)
    result = await use_case(
        LoginCommand(
            email=body.email,
            password=body.password,
            device_token=request.cookies.get(DEVICE_COOKIE),
        ),
    )
    set_device_cookie(response, result.device)
    set_pair_cookies(response, result.pair, settings)
    return TokenPairResponse(access=result.pair.access, refresh=result.pair.refresh)


@router.post(
    "/refresh",
    response_model=TokenPairResponse | SessionRefreshedResponse,
    dependencies=[self_authenticated()],
)
async def refresh(
    request: Request,
    response: Response,
    use_case: FromDishka[RefreshTokens],
    settings: FromDishka[JwtSettings],
    body: RefreshRequest | None = None,
) -> TokenPairResponse | SessionRefreshedResponse:
    """Extend the session, revoking the presented token.

    Args:
        request: Request - Request, the refresh cookie of a browser comes from it.
        response: Response - Response the new cookies are set on.
        use_case: RefreshTokens - The use case.
        settings: JwtSettings - Lifetimes of the cookies.
        body: RefreshRequest | None - Refresh token of a programmatic client.

    Returns:
        TokenPairResponse | SessionRefreshedResponse - The pair in the body for a
            programmatic client, an empty body for a browser: it got the cookies.

    """
    presented = _presented_refresh(request, body)
    pair = await use_case(presented.token)
    set_pair_cookies(response, pair, settings)
    return presented.rotated(pair)


@router.post(
    "/logout",
    status_code=HTTPStatus.NO_CONTENT,
    dependencies=[self_authenticated()],
)
async def logout(
    request: Request,
    response: Response,
    use_case: FromDishka[Logout],
    body: RefreshRequest | None = None,
) -> None:
    """End the session.

    Args:
        request: Request - Request: refresh and access cookies of a browser.
        response: Response - Response the session cookies are cleared on.
        use_case: Logout - The use case.
        body: RefreshRequest | None - Refresh token of a programmatic client.

    """
    await use_case(
        _presented_refresh(request, body).token,
        presented_access_token(request),
    )
    clear_session_cookies(response)


@router.post(
    "/logout-all",
    status_code=HTTPStatus.NO_CONTENT,
    dependencies=[authenticated()],
)
async def invalidate_sessions(
    request: Request,
    response: Response,
    use_case: FromDishka[InvalidateSessions],
) -> None:
    """Log out everywhere: void every token of the own account.

    Args:
        request: Request - Request, the identity comes from it.
        response: Response - Response the session cookies are cleared on.
        use_case: InvalidateSessions - The use case.

    """
    actor = current_identity(request)
    await use_case(actor.user_id, actor_id=actor.user_id)
    clear_session_cookies(response)


@dataclass(frozen=True, slots=True)
class _PresentedRefresh:
    """A presented refresh token and the transport it came by.

    Attributes:
        token: str - The token.
        from_cookie: bool - It came as an httpOnly cookie, so the client is a browser.

    """

    token: str
    from_cookie: bool

    def rotated(self, pair: TokenPair) -> TokenPairResponse | SessionRefreshedResponse:
        """Build the refresh answer for the transport the token came by.

        Args:
            pair: TokenPair - Pair issued by the use case.

        Returns:
            TokenPairResponse | SessionRefreshedResponse - The pair in the body for a
                programmatic client; an empty body for a browser, which cannot read it.

        """
        if self.from_cookie:
            return SessionRefreshedResponse()
        return TokenPairResponse(access=pair.access, refresh=pair.refresh)


def _presented_refresh(
    request: Request,
    body: RefreshRequest | None,
) -> _PresentedRefresh:
    """Take the refresh token: the cookie first, then the body.

    Args:
        request: Request - Request of a browser.
        body: RefreshRequest | None - Body of a programmatic client.

    Returns:
        _PresentedRefresh - The token and where it came from.

    Raises:
        NotAuthenticatedError: If there is no token in the cookie or the body.

    """
    from_cookie = request.cookies.get(REFRESH_COOKIE, "").strip()
    if from_cookie:
        return _PresentedRefresh(token=from_cookie, from_cookie=True)
    if body is not None:
        return _PresentedRefresh(token=body.refresh, from_cookie=False)
    msg = "refresh token is required"
    raise NotAuthenticatedError(msg)
