"""Password over HTTP: reset through a letter and change while logged in."""

from __future__ import annotations

from datetime import timedelta
from http import HTTPStatus

from auth_app import (
    API_PREFIX,
    CREDENTIALS,
    FRONTEND_ORIGIN,
    REGISTRATION,
    Deps,
    assert_error_contract,
    bearer,
    build,
    client_for,
    deliver_outbox,
    register_and_verify,
    seed,
)
from auth_fakes import GOOD_PASSWORD, DenyAllLimiter, deliver_pending_password_resets
from httpx import ASGITransport, AsyncClient

_NEW_PASSWORD = "Totally New Passphrase"
_RESET_REQUEST = "/auth/password/reset-request"
_RESET = "/auth/password/reset"


async def _reset_link_token(deps: Deps) -> str:
    """Run the reset letters of the outbox and return the token of the link."""
    await deliver_pending_password_resets(
        deps.outbox,
        deps.users,
        deps.tokens,
        deps.email,
        deps.clock,
    )
    return deps.email.reset_sent[-1][1]


async def test_request_answers_the_same_for_any_address() -> None:
    """A known and an unknown address get the same answer."""
    app, deps = build()
    async with client_for(app) as client:
        await register_and_verify(client, deps)

        known = await client.post(_RESET_REQUEST, json={"email": REGISTRATION["email"]})
        unknown = await client.post(_RESET_REQUEST, json={"email": "nobody@b.co"})

    assert known.status_code == HTTPStatus.ACCEPTED
    assert unknown.status_code == HTTPStatus.ACCEPTED
    assert known.text == unknown.text


async def test_only_a_real_address_gets_a_letter() -> None:
    """Only a known address gets a letter."""
    app, deps = build()
    async with client_for(app) as client:
        await register_and_verify(client, deps)

        _ = await client.post(_RESET_REQUEST, json={"email": REGISTRATION["email"]})
        _ = await client.post(_RESET_REQUEST, json={"email": "nobody@b.co"})

    await deliver_pending_password_resets(
        deps.outbox,
        deps.users,
        deps.tokens,
        deps.email,
        deps.clock,
    )

    assert [recipient for recipient, _ in deps.email.reset_sent] == [
        REGISTRATION["email"],
    ]


async def test_request_is_throttled_by_ip() -> None:
    """A spent limit is a 429, not a letter."""
    app, _ = build(Deps(limiter=DenyAllLimiter()))
    async with client_for(app) as client:
        response = await client.post(_RESET_REQUEST, json={"email": "probe@b.co"})

    assert response.status_code == HTTPStatus.TOO_MANY_REQUESTS
    assert response.json()["error"] == "core.rate_limit_exceeded"
    assert_error_contract(response)


async def test_reset_is_throttled_by_ip() -> None:
    """The reset by link is limited too."""
    app, _ = build(Deps(limiter=DenyAllLimiter()))
    async with client_for(app) as client:
        response = await client.post(
            _RESET,
            json={"token": "whatever", "password": _NEW_PASSWORD},
        )

    assert response.status_code == HTTPStatus.TOO_MANY_REQUESTS
    assert response.json()["error"] == "core.rate_limit_exceeded"
    assert_error_contract(response)


async def test_the_link_from_the_letter_replaces_the_password() -> None:
    """Letter, link, and the new password logs in while the old one does not."""
    app, deps = build()
    async with client_for(app) as client:
        await register_and_verify(client, deps)
        _ = await client.post(_RESET_REQUEST, json={"email": REGISTRATION["email"]})
        token = await _reset_link_token(deps)

        response = await client.post(
            _RESET,
            json={"token": token, "password": _NEW_PASSWORD},
        )

        assert response.status_code == HTTPStatus.NO_CONTENT

        with_new = await client.post(
            "/auth/login",
            json={"email": REGISTRATION["email"], "password": _NEW_PASSWORD},
        )
        with_old = await client.post("/auth/login", json=CREDENTIALS)

    assert with_new.status_code == HTTPStatus.OK
    assert with_old.status_code == HTTPStatus.UNAUTHORIZED


async def test_a_spent_link_is_rejected_on_the_second_visit() -> None:
    """A second use of a worked link is a 400, not a quiet success."""
    app, deps = build()
    async with client_for(app) as client:
        await register_and_verify(client, deps)
        _ = await client.post(_RESET_REQUEST, json={"email": REGISTRATION["email"]})
        token = await _reset_link_token(deps)
        _ = await client.post(_RESET, json={"token": token, "password": _NEW_PASSWORD})

        again = await client.post(
            _RESET,
            json={"token": token, "password": "Second Passphrase Entirely"},
        )

    assert again.status_code == HTTPStatus.BAD_REQUEST
    assert again.json()["error"] == "auth.token_already_used"
    assert_error_contract(again)


async def test_a_verification_token_is_not_accepted_here() -> None:
    """A confirmation link does not reset a password."""
    app, deps = build()
    async with client_for(app) as client:
        _ = await client.post("/auth/register", json=REGISTRATION)
        await deliver_outbox(deps)
        _, verification_token = deps.email.sent[-1]

        response = await client.post(
            _RESET,
            json={"token": verification_token, "password": _NEW_PASSWORD},
        )

    assert response.status_code == HTTPStatus.BAD_REQUEST
    assert response.json()["error"] == "auth.invalid_token"
    assert_error_contract(response)


async def test_a_weak_password_is_rejected_without_spending_the_link() -> None:
    """A weak password is a 422 and the link keeps working."""
    app, deps = build()
    async with client_for(app) as client:
        await register_and_verify(client, deps)
        _ = await client.post(_RESET_REQUEST, json={"email": REGISTRATION["email"]})
        token = await _reset_link_token(deps)

        weak = await client.post(_RESET, json={"token": token, "password": "123456"})
        retry = await client.post(
            _RESET,
            json={"token": token, "password": GOOD_PASSWORD},
        )

    assert weak.status_code == HTTPStatus.UNPROCESSABLE_ENTITY
    assert weak.json()["error"] == "auth.weak_password"
    assert_error_contract(weak)
    assert retry.status_code == HTTPStatus.NO_CONTENT


async def test_a_change_keeps_this_browser_logged_in_and_ends_the_others() -> None:
    """The browser gets fresh cookies; an older token of another device is void."""
    # The cookies live on the path `/api`, so the app is mounted as in production.
    app, deps = build(prefix=API_PREFIX)
    transport = ASGITransport(app=app, client=("7.7.7.7", 12345))
    async with (
        AsyncClient(
            transport=transport,
            base_url=f"http://test{API_PREFIX}",
        ) as other_device,
        AsyncClient(
            transport=transport,
            base_url=f"https://test{API_PREFIX}",
            headers={"Origin": FRONTEND_ORIGIN},
        ) as browser,
    ):
        _ = await seed(deps, "u@b.co")
        other = await bearer(other_device, "u@b.co")
        login = await browser.post(
            "/auth/login",
            json={"email": "u@b.co", "password": GOOD_PASSWORD},
        )
        assert login.status_code == HTTPStatus.OK
        deps.clock.advance(timedelta(seconds=5))

        changed = await browser.post(
            "/auth/password/change",
            json={"current_password": GOOD_PASSWORD, "new_password": _NEW_PASSWORD},
        )
        me = await browser.get("/auth/me")
        stale = await other_device.get("/auth/me", headers=other)

    assert changed.status_code == HTTPStatus.OK
    assert browser.cookies["validate_access"] == changed.json()["access"]
    assert me.status_code == HTTPStatus.OK
    assert stale.status_code == HTTPStatus.UNAUTHORIZED
    assert stale.json()["error"] == "auth.token_revoked"


async def test_a_change_with_a_wrong_current_password_is_401() -> None:
    """The current password must match."""
    app, deps = build()
    async with client_for(app) as client:
        _ = await seed(deps, "u@b.co")
        headers = await bearer(client, "u@b.co")

        response = await client.post(
            "/auth/password/change",
            json={"current_password": "Not The One1", "new_password": _NEW_PASSWORD},
            headers=headers,
        )

    assert response.status_code == HTTPStatus.UNAUTHORIZED
    assert response.json()["error"] == "auth.invalid_credentials"
    assert_error_contract(response)


async def test_a_change_needs_a_session() -> None:
    """An anonymous change is a 401."""
    app, _ = build()
    async with client_for(app) as client:
        response = await client.post(
            "/auth/password/change",
            json={"current_password": GOOD_PASSWORD, "new_password": _NEW_PASSWORD},
        )

    assert response.status_code == HTTPStatus.UNAUTHORIZED


async def test_the_profile_is_replaced_over_http() -> None:
    """The profile is replaced whole, blank strings read as not given."""
    app, deps = build()
    async with client_for(app) as client:
        _ = await seed(deps, "u@b.co")
        headers = await bearer(client, "u@b.co")

        response = await client.put(
            "/auth/me/profile",
            json={"first_name_ru": " Иван ", "group_number": ""},
            headers=headers,
        )
        me = await client.get("/auth/me", headers=headers)

    assert response.status_code == HTTPStatus.OK
    assert response.json()["first_name_ru"] == "Иван"
    assert response.json()["group_number"] is None
    assert me.json()["profile"] == response.json()
