"""Refresh rotation under concurrency, on a live Redis."""

from __future__ import annotations

import asyncio
import uuid
from typing import TYPE_CHECKING

import pytest
import structlog
from auth_fakes import (
    NOW,
    REQUIRE_VERIFIED,
    FakeAuditLog,
    FakeUnitOfWork,
    FakeUserRepository,
)
from pydantic import SecretStr

from vld.auth.application import Logout, RefreshTokens, TokenRevokedError
from vld.auth.config import JwtSettings
from vld.auth.domain import Role, User
from vld.auth.infrastructure import (
    JwtTokenIssuer,
    RedisRefreshedPairCache,
    RedisRevocationStore,
)

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence

    from redis.asyncio import Redis

    from vld.auth.application import TokenPair

pytestmark = pytest.mark.integration


def _reuse_alerts(logs: Sequence[Mapping[str, object]]) -> list[Mapping[str, object]]:
    """Pick the reuse alerts out of the captured log."""
    return [r for r in logs if r.get("event") == "refresh_token_reuse_detected"]


def _active_user() -> User:
    return User(
        id=uuid.uuid4(),
        email="race@b.co",
        email_verified_at=NOW,
        password_hash="hashed:whatever",
        role=Role.STUDENT,
        is_admin=False,
        is_active=True,
    )


async def test_two_concurrent_refreshes_yield_exactly_one_pair(
    redis_client: Redis,
) -> None:
    """Two concurrent refreshes of one token yield exactly one pair."""
    issuer = JwtTokenIssuer(
        JwtSettings(secret_key=SecretStr(uuid.uuid4().hex * 2)),
    )
    store = RedisRevocationStore(redis_client)
    user = _active_user()
    users = FakeUserRepository()
    await users.add(user)

    _access, refresh = issuer.issue_pair(user.id)
    use_case = RefreshTokens(
        issuer=issuer,
        revocation=store,
        refreshed=RedisRefreshedPairCache(redis_client),
        users=users,
        uow=FakeUnitOfWork(),
        verification=REQUIRE_VERIFIED,
    )

    with structlog.testing.capture_logs() as logs:
        outcomes = await asyncio.gather(
            use_case(refresh),
            use_case(refresh),
            return_exceptions=True,
        )

    pairs = [r for r in outcomes if not isinstance(r, BaseException)]
    errors = [r for r in outcomes if isinstance(r, BaseException)]
    assert pairs, f"at least one refresh must pass: {outcomes}"
    assert len({(p.access, p.refresh) for p in pairs}) == 1, (
        f"two different pairs for one refresh: {outcomes}"
    )
    assert all(isinstance(e, TokenRevokedError) for e in errors), (
        f"the loser must get the rotation refusal, not another error: {outcomes}"
    )
    # An honest race is not reuse; the gap shows only on a live Redis.
    assert not _reuse_alerts(logs), f"an honest race counted as reuse: {outcomes}"


async def test_reuse_after_the_grace_window_is_refused_and_alerted(
    redis_client: Redis,
) -> None:
    """A retry within the window gets the same pair; after it, a refusal and an alert."""
    issuer = JwtTokenIssuer(
        JwtSettings(secret_key=SecretStr(uuid.uuid4().hex * 2)),
    )
    store = RedisRevocationStore(redis_client)
    user = _active_user()
    users = FakeUserRepository()
    await users.add(user)

    _access, refresh = issuer.issue_pair(user.id)
    use_case = RefreshTokens(
        issuer=issuer,
        revocation=store,
        refreshed=RedisRefreshedPairCache(redis_client),
        users=users,
        uow=FakeUnitOfWork(),
        verification=REQUIRE_VERIFIED,
    )

    first: TokenPair = await use_case(refresh)
    retried = await use_case(refresh)
    assert (retried.access, retried.refresh) == (first.access, first.refresh)

    old_jti = issuer.parse_refresh(refresh).jti
    _ = await redis_client.delete(f"auth:refreshed:{old_jti}")

    with structlog.testing.capture_logs() as logs, pytest.raises(TokenRevokedError):
        _ = await use_case(refresh)
    assert _reuse_alerts(logs), "the detector is silent on real reuse"
    assert user.tokens_invalidated_after is None, (
        "the detector alerts but must not void the account"
    )


async def test_logout_after_rotation_does_not_disarm_the_detector(
    redis_client: Redis,
) -> None:
    """A logout with a rotated jti does not downgrade its key."""
    issuer = JwtTokenIssuer(
        JwtSettings(secret_key=SecretStr(uuid.uuid4().hex * 2)),
    )
    store = RedisRevocationStore(redis_client)
    user = _active_user()
    users = FakeUserRepository()
    await users.add(user)

    access, refresh = issuer.issue_pair(user.id)
    use_case = RefreshTokens(
        issuer=issuer,
        revocation=store,
        refreshed=RedisRefreshedPairCache(redis_client),
        users=users,
        uow=FakeUnitOfWork(),
        verification=REQUIRE_VERIFIED,
    )

    _ = await use_case(refresh)
    await Logout(issuer, store, FakeUnitOfWork(), FakeAuditLog())(refresh, access)

    old_jti = issuer.parse_refresh(refresh).jti
    assert await redis_client.get(f"auth:revoked:{old_jti}") == "rotated", (
        "the logout downgraded the key to revoked"
    )
    _ = await redis_client.delete(f"auth:refreshed:{old_jti}")  # the window is over

    with structlog.testing.capture_logs() as logs, pytest.raises(TokenRevokedError):
        _ = await use_case(refresh)
    assert _reuse_alerts(logs), "a logout with a rotated token erased the signal"


async def test_logout_still_revokes_a_token_that_was_never_rotated(
    redis_client: Redis,
) -> None:
    """`NX` did not break a plain logout."""
    issuer = JwtTokenIssuer(
        JwtSettings(secret_key=SecretStr(uuid.uuid4().hex * 2)),
    )
    store = RedisRevocationStore(redis_client)
    user = _active_user()
    users = FakeUserRepository()
    await users.add(user)

    access, refresh = issuer.issue_pair(user.id)
    await Logout(issuer, store, FakeUnitOfWork(), FakeAuditLog())(refresh, access)

    assert await store.is_revoked(issuer.parse_refresh(refresh).jti)
    assert await store.is_revoked(issuer.parse_access(access).jti)
