"""bcrypt hasher: salted hashes, the cost, the byte limit, the thread cap."""

from __future__ import annotations

import anyio
import bcrypt
import pytest
from anyio import CapacityLimiter

from vld.auth.infrastructure import BcryptPasswordHasher

# The cheapest cost bcrypt accepts: these tests check behaviour, not strength.
_FAST = 4


async def test_hash_is_verifiable_and_salted() -> None:
    """Equal passwords give different hashes, and both verify."""
    hasher = BcryptPasswordHasher(rounds=_FAST)

    first = await hasher.hash("Same Password")
    second = await hasher.hash("Same Password")

    assert first != second, "equal passwords must get different salts"
    assert await hasher.verify("Same Password", first)
    assert await hasher.verify("Same Password", second)
    assert not await hasher.verify("Other Password", first)


async def test_the_default_cost_is_the_one_of_doi_arxiv_app() -> None:
    """Cost 12, so hashes carried over by the ETL stay current."""
    stored = await BcryptPasswordHasher().hash("Cost Probe")

    assert stored.startswith("$2b$12$")


async def test_a_hash_of_doi_arxiv_app_verifies() -> None:
    """A hash made by the old service directly with bcrypt is accepted."""
    legacy = bcrypt.hashpw(b"Legacy Pass1", bcrypt.gensalt(rounds=_FAST)).decode()

    assert await BcryptPasswordHasher(rounds=_FAST).verify("Legacy Pass1", legacy)


async def test_a_password_over_72_bytes_never_matches() -> None:
    """Bcrypt would refuse it; the hasher answers no instead of raising."""
    hasher = BcryptPasswordHasher(rounds=_FAST)
    stored = await hasher.hash("A" * 72)

    assert not await hasher.verify("A" * 73, stored)


async def test_a_broken_hash_is_a_data_error_not_a_wrong_password() -> None:
    """A corrupt row raises instead of reading as a failed login."""
    with pytest.raises(ValueError, match="salt"):
        _ = await BcryptPasswordHasher(rounds=_FAST).verify("Any Pass1", "not-a-hash")


async def test_needs_rehash_detects_a_lower_cost() -> None:
    """A hash of a lower cost is marked for rehashing; a current one is not."""
    weak = await BcryptPasswordHasher(rounds=_FAST).hash("Rehash Me1")
    current = BcryptPasswordHasher(rounds=_FAST + 1)

    assert current.needs_rehash(weak)
    assert not current.needs_rehash(await current.hash("Rehash Me1"))
    assert current.needs_rehash("not-a-hash")


async def test_hashing_waits_for_a_free_slot() -> None:
    """A hash waits while the limiter has no free slot."""
    limiter = CapacityLimiter(1)
    hasher = BcryptPasswordHasher(rounds=_FAST, limiter=limiter)
    hashed: list[str] = []

    async def _hash() -> None:
        hashed.append(await hasher.hash("Waiting Pass1"))

    # The slot is released before the group waits for the hash.
    async with anyio.create_task_group() as group, limiter:
        _ = group.start_soon(_hash)
        await anyio.sleep(0.05)
        assert not hashed, "hashing must wait for the slot"
    assert len(hashed) == 1


def test_the_default_limiter_is_shared_across_instances() -> None:
    """The cap guards the CPU of the process, not one instance."""
    assert BcryptPasswordHasher()._limiter is BcryptPasswordHasher()._limiter
