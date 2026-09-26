"""The auth HTTP layer whole: sessions, registration, throttling, cookies."""

from __future__ import annotations

from http import HTTPStatus
from typing import TYPE_CHECKING, cast, override

import pytest
from auth_app import (
    API_PREFIX,
    CREDENTIALS,
    FRONTEND_ORIGIN,
    REGISTRATION,
    Deps,
    assert_error_contract,
    build,
    client_for,
    deliver_outbox,
    register_and_verify,
)
from auth_fakes import (
    GOOD_PASSWORD,
    NOW,
    AllowAllLimiter,
    CountingLimiter,
    DenyAllLimiter,
    FakeRevocationStore,
)
from httpx import ASGITransport, AsyncClient

from vld.auth.application import RevocationCheckUnavailableError

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

    from fastapi import FastAPI
    from httpx import Response


@pytest.fixture
async def app_and_deps() -> AsyncIterator[tuple[AsyncClient, Deps]]:
    """Give a client and the fakes behind it."""
    app, deps = build()
    async with client_for(app) as client:
        yield client, deps


async def test_full_flow(app_and_deps: tuple[AsyncClient, Deps]) -> None:
    """Register, confirm, log in, refresh, retry within grace, reuse after it."""
    client, deps = app_and_deps
    await register_and_verify(client, deps)

    login = await client.post("/auth/login", json=CREDENTIALS)
    assert login.status_code == 200
    refresh_token = cast("dict[str, str]", login.json())["refresh"]

    refreshed = await client.post("/auth/refresh", json={"refresh": refresh_token})
    assert refreshed.status_code == 200

    # Within the grace window a repeat is a retry: 200 and the very same pair.
    retried = await client.post("/auth/refresh", json={"refresh": refresh_token})
    assert retried.status_code == 200
    assert retried.json() == refreshed.json()

    # Once the window closes a repeat is reuse: 401.
    deps.refreshed.pairs.clear()
    reused = await client.post("/auth/refresh", json={"refresh": refresh_token})
    assert reused.status_code == 401
    assert reused.json()["error"] == "auth.token_revoked"
    assert_error_contract(reused)


async def test_the_email_link_is_not_an_api_route(
    app_and_deps: tuple[AsyncClient, Deps],
) -> None:
    """A GET of the confirmation address does not consume the link."""
    client, deps = app_and_deps
    _ = await client.post("/auth/register", json=REGISTRATION)
    await deliver_outbox(deps)
    _, token = deps.email.sent[-1]

    scanned = await client.get("/auth/verify-email", params={"token": token})

    assert scanned.status_code == 405
    assert deps.tokens.consumed == {}

    # The token is intact: the POST of the frontend page takes it.
    human = await client.post("/auth/verify-email", json={"token": token})
    assert human.status_code == 204


async def test_login_before_verification_is_rejected(
    app_and_deps: tuple[AsyncClient, Deps],
) -> None:
    """An unconfirmed address cannot log in."""
    client, _ = app_and_deps
    _ = await client.post("/auth/register", json=REGISTRATION)

    login = await client.post("/auth/login", json=CREDENTIALS)

    assert login.status_code == 403
    assert login.json()["error"] == "auth.email_not_verified"
    assert_error_contract(login)


async def test_login_of_a_deactivated_account_is_403(
    app_and_deps: tuple[AsyncClient, Deps],
) -> None:
    """A deactivated account hears so after the right password."""
    client, deps = app_and_deps
    await register_and_verify(client, deps)
    for user in deps.users.items.values():
        user.deactivate(NOW)

    response = await client.post("/auth/login", json=CREDENTIALS)

    assert response.status_code == HTTPStatus.FORBIDDEN
    assert response.json()["error"] == "auth.account_deactivated"
    assert_error_contract(response)


async def test_taken_email_is_reported_distinguishably(
    app_and_deps: tuple[AsyncClient, Deps],
) -> None:
    """A taken address is reported; the reset link hands it back to its owner."""
    client, _ = app_and_deps
    _ = await client.post("/auth/register", json=REGISTRATION)

    again = await client.post("/auth/register", json=REGISTRATION)

    assert again.status_code == 409
    assert again.json()["error"] == "auth.email_already_taken"
    assert_error_contract(again)


async def test_unavailable_revocation_store_is_503_not_401() -> None:
    """A 401 would log everyone out during a thirty-second Redis flap."""

    class _Unavailable(FakeRevocationStore):
        @override
        async def is_revoked(self, jti: str) -> bool:
            del jti
            msg = "revocation store is unavailable"
            raise RevocationCheckUnavailableError(msg)

        @override
        async def revoke_if_new(self, jti: str, ttl_seconds: int) -> bool:
            # The refresh path comes here: check and revoke are one operation.
            del jti, ttl_seconds
            msg = "revocation store is unavailable"
            raise RevocationCheckUnavailableError(msg)

    app, deps = build(Deps(revocation=_Unavailable()))
    async with client_for(app) as client:
        await register_and_verify(client, deps)
        login = await client.post("/auth/login", json=CREDENTIALS)

        response = await client.post(
            "/auth/refresh",
            json={"refresh": login.json()["refresh"]},
        )

    assert response.status_code == 503
    assert response.headers["Retry-After"]
    assert response.json()["error"] == "auth.revocation_check_unavailable"
    assert_error_contract(response)


async def test_login_is_throttled_by_ip() -> None:
    """A spent limit on login is a 429, not a 500."""
    app, _ = build(Deps(limiter=DenyAllLimiter()))
    async with client_for(app) as client:
        response = await client.post("/auth/login", json=CREDENTIALS)

    assert response.status_code == 429
    assert response.json()["error"] == "core.rate_limit_exceeded"
    assert_error_contract(response)


async def test_registration_is_throttled_by_ip() -> None:
    """A spent limit on registration is a 429."""
    app, _ = build(Deps(limiter=DenyAllLimiter()))
    async with client_for(app) as client:
        response = await client.post("/auth/register", json=REGISTRATION)

    assert response.status_code == 429
    assert_error_contract(response)


async def test_the_ip_bucket_is_separate_from_the_email_bucket() -> None:
    """One bucket for both would mean the second limit does not exist."""
    app, deps = build(Deps(limiter=AllowAllLimiter()))
    async with client_for(app) as client:
        await register_and_verify(client, deps)
        _ = await client.post("/auth/login", json=CREDENTIALS)

    assert any(key.startswith("login:ip:") for key in deps.limiter.keys)
    assert any(key.startswith("login:email:") for key in deps.limiter.keys)


async def test_the_ip_bucket_is_keyed_by_the_client_address() -> None:
    """Two client addresses get two buckets."""
    app, deps = build(Deps(limiter=AllowAllLimiter()))
    async with client_for(app, host="1.2.3.4") as first:
        _ = await first.post("/auth/login", json=CREDENTIALS)
    async with client_for(app, host="5.6.7.8") as second:
        _ = await second.post("/auth/login", json=CREDENTIALS)

    assert "login:ip:1.2.3.4" in deps.limiter.keys
    assert "login:ip:5.6.7.8" in deps.limiter.keys


async def test_login_ip_bucket_blocks_the_thirty_first_attempt() -> None:
    """The login limit per client address is 30 attempts in 15 minutes."""
    app, deps = build(Deps(limiter=CountingLimiter()))
    async with client_for(app, host="9.9.9.9") as client:
        for attempt in range(30):
            response = await client.post(
                "/auth/login",
                json={"email": f"u{attempt}@b.co", "password": GOOD_PASSWORD},
            )
            assert response.status_code == 401, f"attempt {attempt} must not be a 429"

        blocked = await client.post(
            "/auth/login",
            json={"email": "u30@b.co", "password": GOOD_PASSWORD},
        )

    assert blocked.status_code == 429
    assert deps.limiter.windows["login:ip:9.9.9.9"] == 15 * 60_000
    assert_error_contract(blocked)


async def test_register_ip_bucket_blocks_the_eleventh_attempt() -> None:
    """The registration limit per client address is 10 attempts an hour."""
    app, deps = build(Deps(limiter=CountingLimiter()))
    async with client_for(app, host="8.8.8.8") as client:
        for attempt in range(10):
            response = await client.post(
                "/auth/register",
                json={
                    "email": f"r{attempt}@b.co",
                    "password": GOOD_PASSWORD,
                    "role": "student",
                },
            )
            assert response.status_code == 201, f"attempt {attempt} must not be a 429"

        blocked = await client.post(
            "/auth/register",
            json={"email": "r10@b.co", "password": GOOD_PASSWORD, "role": "student"},
        )

    assert blocked.status_code == 429
    assert deps.limiter.windows["register:ip:8.8.8.8"] == 60 * 60_000
    assert_error_contract(blocked)


async def test_the_submitted_token_never_comes_back_in_the_error_body(
    app_and_deps: tuple[AsyncClient, Deps],
) -> None:
    """Error bodies go to logs and traces; a token has no place there."""
    client, _ = app_and_deps
    token = "s3cret-token-value"

    response = await client.post("/auth/verify-email", json={"token": token})

    assert response.status_code == 400
    assert token not in response.text
    assert_error_contract(response)


async def test_logout_is_idempotent(app_and_deps: tuple[AsyncClient, Deps]) -> None:
    """A second logout is a success too."""
    client, deps = app_and_deps
    await register_and_verify(client, deps)
    login = await client.post("/auth/login", json=CREDENTIALS)
    body = {"refresh": login.json()["refresh"]}
    headers = {"Authorization": f"Bearer {login.json()['access']}"}

    first = await client.post("/auth/logout", json=body, headers=headers)
    second = await client.post("/auth/logout", json=body, headers=headers)

    assert (first.status_code, second.status_code) == (204, 204)


async def test_logout_also_revokes_the_access_token(
    app_and_deps: tuple[AsyncClient, Deps],
) -> None:
    """Otherwise a logged-out access token keeps working for a while."""
    client, deps = app_and_deps
    await register_and_verify(client, deps)
    login = await client.post("/auth/login", json=CREDENTIALS)

    _ = await client.post(
        "/auth/logout",
        json={"refresh": login.json()["refresh"]},
        headers={"Authorization": f"Bearer {login.json()['access']}"},
    )

    access = cast("dict[str, str]", login.json())["access"]

    # The jti through the port: the token format is a detail of the fake.
    jti = deps.issuer.parse_access(access).jti

    assert jti in deps.revocation.revoked


@pytest.mark.parametrize(
    ("outcome", "expected_code", "expected_status"),
    [
        ("deactivated", "auth.account_deactivated", HTTPStatus.FORBIDDEN),
        ("deleted", "auth.account_gone", HTTPStatus.UNAUTHORIZED),
    ],
)
async def test_refresh_tells_a_deactivated_account_from_a_deleted_one(
    app_and_deps: tuple[AsyncClient, Deps],
    outcome: str,
    expected_code: str,
    expected_status: int,
) -> None:
    """One code would draw one screen for two different situations."""
    client, deps = app_and_deps
    await register_and_verify(client, deps)
    login = await client.post("/auth/login", json=CREDENTIALS)
    if outcome == "deleted":
        deps.users.items.clear()
    for user in deps.users.items.values():
        user.deactivate(NOW)

    response = await client.post(
        "/auth/refresh",
        json={"refresh": login.json()["refresh"]},
    )

    assert response.status_code == expected_status
    assert response.json()["error"] == expected_code
    assert_error_contract(response)


async def test_garbage_refresh_token_is_401_not_500(
    app_and_deps: tuple[AsyncClient, Deps],
) -> None:
    """A bare ValueError of the port maps to a 401, not a 500."""
    client, _ = app_and_deps

    response = await client.post("/auth/refresh", json={"refresh": "garbage"})

    assert response.status_code == 401
    assert response.json()["error"] == "auth.invalid_refresh_token"
    assert_error_contract(response)


async def test_validation_error_matches_the_declared_schema(
    app_and_deps: tuple[AsyncClient, Deps],
) -> None:
    """A validation error keeps the declared error shape."""
    client, _ = app_and_deps

    response = await client.post("/auth/register", json={"email": "not-mail"})

    assert response.status_code == 422
    assert_error_contract(response)


async def test_login_sets_a_bound_httponly_device_cookie(
    app_and_deps: tuple[AsyncClient, Deps],
) -> None:
    """Login sets a device cookie bound to the account."""
    client, deps = app_and_deps
    await register_and_verify(client, deps)

    login = await client.post("/auth/login", json=CREDENTIALS)

    cookie = login.cookies["validate_device"]
    user_id = next(iter(deps.users.items))
    assert deps.issuer.parse_device(cookie).user_id == user_id
    set_cookie = login.headers["set-cookie"]
    assert "HttpOnly" in set_cookie
    assert "Secure" in set_cookie
    assert "Max-Age=31536000" in set_cookie


async def test_resend_verification_does_not_reveal_whether_the_address_exists(
    app_and_deps: tuple[AsyncClient, Deps],
) -> None:
    """The 202 is the same for a known and an unknown address."""
    client, deps = app_and_deps
    _ = await client.post(
        "/auth/register",
        json=REGISTRATION,
    )  # unconfirmed, the event is in the outbox
    await deliver_outbox(deps)  # the registration letter
    sent_after_register = len(deps.email.sent)

    existing = await client.post(
        "/auth/verification/resend",
        json={"email": REGISTRATION["email"]},
    )
    missing = await client.post(
        "/auth/verification/resend",
        json={"email": "nobody@b.co"},
    )

    assert existing.status_code == 202
    assert missing.status_code == 202
    # The bodies are identical: no address can be enumerated.
    assert existing.text == missing.text
    # A letter went only to the known unconfirmed address.
    await deliver_outbox(deps)
    assert len(deps.email.sent) == sent_after_register + 1
    assert deps.email.sent[-1][0] == REGISTRATION["email"]


async def test_resend_to_a_verified_address_sends_no_new_email(
    app_and_deps: tuple[AsyncClient, Deps],
) -> None:
    """A confirmed address gets a 202 and no letter."""
    client, deps = app_and_deps
    await register_and_verify(client, deps)
    sent_before = len(deps.email.sent)

    response = await client.post(
        "/auth/verification/resend",
        json={"email": REGISTRATION["email"]},
    )

    assert response.status_code == 202
    # A confirmed address writes no event, so the drain sends nothing.
    await deliver_outbox(deps)
    assert len(deps.email.sent) == sent_before


async def test_resend_verification_is_throttled_by_ip() -> None:
    """Guessing addresses meets the IP limit: a 429, not a mailing."""
    app, _ = build(Deps(limiter=DenyAllLimiter()))
    async with client_for(app) as client:
        response = await client.post(
            "/auth/verification/resend",
            json={"email": "probe@b.co"},
        )

    assert response.status_code == 429
    assert response.json()["error"] == "core.rate_limit_exceeded"
    assert_error_contract(response)


async def test_router_feeds_the_device_cookie_into_the_login_flow() -> None:
    """The router hands the cookie to the use case: the bypass works over HTTP."""
    app, deps = build(Deps(limiter=CountingLimiter()), prefix=API_PREFIX)
    transport = ASGITransport(app=app, client=("7.7.7.7", 12345))

    browser = {"Origin": FRONTEND_ORIGIN}

    async with (
        AsyncClient(
            transport=transport,
            base_url=f"https://test{API_PREFIX}",
            headers=browser,
        ) as known,
        AsyncClient(
            transport=transport,
            base_url=f"https://test{API_PREFIX}",
            headers=browser,
        ) as stranger,
    ):
        await register_and_verify(known, deps)
        login = await known.post("/auth/login", json=CREDENTIALS)
        assert login.status_code == 200
        assert known.cookies["validate_device"], "the cookie must land in the jar"

        for _attempt in range(5):
            bad = await stranger.post(
                "/auth/login",
                json={"email": CREDENTIALS["email"], "password": "Wrong Pass Here"},
            )
            assert bad.status_code == 401
        blocked = await stranger.post("/auth/login", json=CREDENTIALS)
        assert blocked.status_code == 429

        allowed = await known.post("/auth/login", json=CREDENTIALS)
        assert allowed.status_code == 200


def browser_for(app: FastAPI, origin: str) -> AsyncClient:
    """Build a client that behaves like a browser: https, a jar, `Origin`, the path."""
    return AsyncClient(
        transport=ASGITransport(app=app, client=("7.7.7.7", 12345)),
        base_url=f"https://test{API_PREFIX}",
        headers={"Origin": origin},
    )


def _session_cookies(response: Response) -> dict[str, str]:
    """Collect the `Set-Cookie` headers of the session pair by name."""
    return {
        raw.split("=", 1)[0]: raw
        for raw in response.headers.get_list("set-cookie")
        if raw.split("=", 1)[0] in {"validate_access", "validate_refresh"}
    }


async def test_a_mutating_request_from_a_foreign_origin_is_refused(
    app_and_deps: tuple[AsyncClient, Deps],
) -> None:
    """A mutating request from a foreign origin is refused."""
    client, _ = app_and_deps

    response = await client.post(
        "/auth/logout",
        headers={"Origin": "https://evil.example"},
    )

    assert response.status_code == HTTPStatus.FORBIDDEN
    assert_error_contract(response)


async def test_login_hands_the_browser_cookies_and_the_client_a_body() -> None:
    """Login hands the pair by both transports."""
    app, deps = build(prefix=API_PREFIX)
    async with browser_for(app, FRONTEND_ORIGIN) as client:
        await register_and_verify(client, deps)

        login = await client.post("/auth/login", json=CREDENTIALS)

        assert login.status_code == 200
        pair = cast("dict[str, str]", login.json())
        cookies = _session_cookies(login)
        assert set(cookies) == {"validate_access", "validate_refresh"}
        assert all("HttpOnly" in raw for raw in cookies.values())
        assert client.cookies["validate_access"] == pair["access"]
        assert client.cookies["validate_refresh"] == pair["refresh"]


async def test_a_browser_refresh_answers_with_cookies_and_no_token_in_the_body() -> (
    None
):
    """A browser refreshes by cookie and gets nothing in the body."""
    app, deps = build(prefix=API_PREFIX)
    async with browser_for(app, FRONTEND_ORIGIN) as client:
        await register_and_verify(client, deps)
        login = await client.post("/auth/login", json=CREDENTIALS)
        assert login.status_code == 200
        issued = cast("dict[str, str]", login.json())["refresh"]

        refreshed = await client.post("/auth/refresh")

        assert refreshed.status_code == 200
        assert refreshed.json() == {}, "no tokens in the body of a cookie refresh"
        cookies = _session_cookies(refreshed)
        assert set(cookies) == {"validate_access", "validate_refresh"}
        assert all("HttpOnly" in raw for raw in cookies.values())
        rotated = client.cookies["validate_refresh"]
        assert rotated != issued, "a refresh must issue a new token"
        assert issued not in refreshed.text


async def test_logout_takes_the_session_out_of_the_browser_and_the_server() -> None:
    """A cookie logout revokes the token and clears the cookies."""
    app, deps = build(prefix=API_PREFIX)
    async with browser_for(app, FRONTEND_ORIGIN) as client:
        await register_and_verify(client, deps)
        login = await client.post("/auth/login", json=CREDENTIALS)
        assert login.status_code == 200
        refresh_token = cast("dict[str, str]", login.json())["refresh"]

        logout = await client.post("/auth/logout")

        assert logout.status_code == 204
        cleared = _session_cookies(logout)
        assert set(cleared) == {"validate_access", "validate_refresh"}
        assert all("Max-Age=0" in raw for raw in cleared.values())
        assert not client.cookies.get("validate_refresh")
        reused = await client.post("/auth/refresh", json={"refresh": refresh_token})
        assert reused.status_code == 401
        assert reused.json()["error"] == "auth.token_revoked"


async def test_a_programmatic_client_keeps_the_body_contract_on_refresh(
    app_and_deps: tuple[AsyncClient, Deps],
) -> None:
    """A client that sent the token in the body gets the pair in the body."""
    client, deps = app_and_deps
    await register_and_verify(client, deps)
    login = await client.post("/auth/login", json=CREDENTIALS)
    assert login.status_code == 200
    issued = cast("dict[str, str]", login.json())["refresh"]

    refreshed = await client.post("/auth/refresh", json={"refresh": issued})

    assert refreshed.status_code == 200
    pair = cast("dict[str, str]", refreshed.json())
    assert set(pair) == {"access", "refresh"}
    assert pair["refresh"] != issued, "a refresh must issue a new token"
    assert pair["access"], "the access token must come in the body"
    assert pair["refresh"], "the refresh token must come in the body"


async def test_a_refresh_with_neither_cookie_nor_body_is_unauthenticated(
    app_and_deps: tuple[AsyncClient, Deps],
) -> None:
    """Neither a cookie nor a body means no credential, not a bad body."""
    client, _ = app_and_deps

    response = await client.post("/auth/refresh")

    assert response.status_code == 401
    assert_error_contract(response)
