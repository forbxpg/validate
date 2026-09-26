"""Redis stores of auth: revocation and the grace cache of issued pairs."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from redis.asyncio import Redis
from redis.exceptions import ConnectionError as RedisConnectionError

from vld.auth.application import RevocationCheckUnavailableError
from vld.auth.infrastructure import RedisRefreshedPairCache, RedisRevocationStore

if TYPE_CHECKING:
    from collections.abc import AsyncIterator


@pytest.fixture
async def unreachable_redis() -> AsyncIterator[Redis]:
    """Give a real client with nowhere to connect."""
    client = Redis.from_url("unix:///nonexistent/validate-revocation.sock")
    yield client
    await client.aclose()


# ── Revocation ──────────────────────────────────────────────────────────────


@pytest.mark.integration
async def test_revoked_token_is_reported(redis_client: Redis) -> None:
    """A revoked jti is reported; an unknown one is not."""
    store = RedisRevocationStore(redis_client)
    assert not await store.is_revoked("jti-1")

    await store.revoke("jti-1", ttl_seconds=60)

    assert await store.is_revoked("jti-1")


@pytest.mark.integration
async def test_revocation_expires_with_the_token(redis_client: Redis) -> None:
    """The key lives exactly the given lifetime."""
    await RedisRevocationStore(redis_client).revoke("jti-ttl", ttl_seconds=42)

    ttl = await redis_client.ttl("auth:revoked:jti-ttl")
    assert 40 < ttl <= 42, f"the key must live about 42 seconds, it lives {ttl}"


@pytest.mark.integration
async def test_rotation_mark_distinguishes_a_rotated_jti_from_a_revoked_one(
    redis_client: Redis,
) -> None:
    """A rotation mark differs from a plain revocation and never revives a key."""
    store = RedisRevocationStore(redis_client)
    assert not await store.was_rotated("jti-rot")

    _ = await store.revoke_if_new("jti-rot", ttl_seconds=60)
    assert not await store.was_rotated("jti-rot"), (
        "a revoked but unrotated jti is a logout, not a theft"
    )

    await store.mark_rotated("jti-rot")
    assert await store.was_rotated("jti-rot")
    assert await store.is_revoked("jti-rot"), "the mark keeps the revocation"

    await store.mark_rotated("jti-never-revoked")
    assert not await redis_client.exists("auth:revoked:jti-never-revoked"), (
        "the mark lands only on an existing key (XX)"
    )


@pytest.mark.integration
async def test_rotation_mark_keeps_the_revocation_ttl(redis_client: Redis) -> None:
    """`KEEPTTL`: the mark does not reset the lifetime of the key."""
    store = RedisRevocationStore(redis_client)
    _ = await store.revoke_if_new("jti-ttl-keep", ttl_seconds=42)

    await store.mark_rotated("jti-ttl-keep")

    ttl = await redis_client.ttl("auth:revoked:jti-ttl-keep")
    assert 40 < ttl <= 42, f"the lifetime must survive the mark, it is {ttl}"


@pytest.mark.integration
async def test_revoke_if_new_answers_once(redis_client: Redis) -> None:
    """Only the first of two revocations of one jti wins."""
    store = RedisRevocationStore(redis_client)

    assert await store.revoke_if_new("jti-once", ttl_seconds=60)
    assert not await store.revoke_if_new("jti-once", ttl_seconds=60)


async def test_is_revoked_fails_closed_when_redis_is_down(
    unreachable_redis: Redis,
) -> None:
    """A store that is down is its own error, neither revoked nor clean."""
    with pytest.raises(RevocationCheckUnavailableError):
        _ = await RedisRevocationStore(unreachable_redis).is_revoked("jti-any")


async def test_rotation_check_fails_distinguishably_when_redis_is_down(
    unreachable_redis: Redis,
) -> None:
    """A rotation check against a store that is down raises, not `True`."""
    with pytest.raises(RevocationCheckUnavailableError):
        _ = await RedisRevocationStore(unreachable_redis).was_rotated("jti-any")


async def test_rotation_mark_is_best_effort_when_redis_is_down(
    unreachable_redis: Redis,
) -> None:
    """A failed mark is swallowed: the pair is already issued."""
    await RedisRevocationStore(unreachable_redis).mark_rotated("jti-any")


async def test_revoke_fails_loudly_when_redis_is_down(
    unreachable_redis: Redis,
) -> None:
    """An unwritten revocation is an error, not a quiet success."""
    with pytest.raises(RedisConnectionError):
        await RedisRevocationStore(unreachable_redis).revoke("jti-any", ttl_seconds=60)


# ── Grace cache of issued pairs ─────────────────────────────────────────────


@pytest.mark.integration
async def test_refreshed_pair_round_trips_and_expires(redis_client: Redis) -> None:
    """The pair comes back whole; the key lives the given lifetime."""
    cache = RedisRefreshedPairCache(redis_client)
    assert await cache.save("jti-grace", "a-token", "r-token", ttl_seconds=30)

    assert await cache.load("jti-grace") == ("a-token", "r-token")
    assert await cache.load("jti-unknown") is None
    ttl = await redis_client.ttl("auth:refreshed:jti-grace")
    assert 28 < ttl <= 30, f"the key must live about 30 seconds, it lives {ttl}"


@pytest.mark.integration
async def test_a_malformed_grace_value_reads_as_a_miss(redis_client: Redis) -> None:
    """A value of a foreign shape is a miss, not a 500."""
    cache = RedisRefreshedPairCache(redis_client)
    _ = await redis_client.set("auth:refreshed:jti-junk", "not json at all", ex=30)
    _ = await redis_client.set("auth:refreshed:jti-shape", '{"access": 1}', ex=30)

    assert await cache.load("jti-junk") is None
    assert await cache.load("jti-shape") is None


@pytest.mark.integration
async def test_a_non_positive_grace_ttl_is_a_failed_write(redis_client: Redis) -> None:
    """A zero lifetime is a failed write, not a silent one-second key."""
    cache = RedisRefreshedPairCache(redis_client)

    assert not await cache.save("jti-zero", "a", "r", ttl_seconds=0)
    assert not await redis_client.exists("auth:refreshed:jti-zero")


async def test_refreshed_load_fails_distinguishably_when_redis_is_down(
    unreachable_redis: Redis,
) -> None:
    """A read against a store that is down raises, not a miss."""
    with pytest.raises(RevocationCheckUnavailableError):
        _ = await RedisRefreshedPairCache(unreachable_redis).load("jti-any")


async def test_refreshed_save_is_best_effort_when_redis_is_down(
    unreachable_redis: Redis,
) -> None:
    """A failed grace write is swallowed: the pair is issued, the jti revoked."""
    assert not await RedisRefreshedPairCache(unreachable_redis).save(
        "jti-any",
        "a",
        "r",
        ttl_seconds=30,
    )
