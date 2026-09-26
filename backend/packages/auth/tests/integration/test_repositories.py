"""Repositories and mappers of auth against a live PostgreSQL."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from vld.auth.domain import (
    DomainEvent,
    EmailAlreadyTakenError,
    EntityNotFoundError,
    Profile,
    Role,
    TokenAlreadyUsedError,
    TokenPurpose,
    User,
    VerificationToken,
)
from vld.auth.infrastructure import (
    OutboxModel,
    OutboxStatus,
    SqlAlchemyOutbox,
    SqlAlchemyTokenRepository,
    SqlAlchemyUserRepository,
)

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncEngine

    from vld.auth.application import TokenRepository, UserRepository

_HASH = "h"
NOW = datetime(2026, 7, 19, 12, 0, tzinfo=UTC)


def _user(email: str = "rt@b.co") -> User:
    return User.register(email, _HASH, Role.STUDENT)


@pytest.mark.integration
async def test_roundtrip_preserves_entity(db_session: AsyncSession) -> None:
    """An account survives the trip to the database and back."""
    repo: UserRepository = SqlAlchemyUserRepository(db_session)
    user = User.register(
        "Round@Trip.co",
        _HASH,
        Role.TEACHER,
        Profile(group_number="Б21-505"),
    )
    await repo.add(user)
    user_id = user.id
    db_session.expire_all()

    loaded = await repo.get_by_id(user_id)
    assert loaded is not None
    assert loaded.id == user_id
    assert loaded.email == "round@trip.co"
    assert loaded.role is Role.TEACHER
    assert loaded.profile == Profile(group_number="Б21-505")
    assert loaded.is_active is True
    assert loaded.is_admin is False
    assert loaded.password_hash == _HASH
    assert loaded.email_verified is False
    assert loaded.tokens_invalidated_after is None


@pytest.mark.integration
async def test_search_filters_orders_and_pages_on_a_live_db(
    db_session: AsyncSession,
) -> None:
    """Paged search against a live database: filters, stable pages, the total."""
    repo = SqlAlchemyUserRepository(db_session)
    for i in range(3):
        await repo.add(_user(f"user{i}@s.co"))
    teacher = User.register("t@s.co", _HASH, Role.TEACHER)
    teacher.deactivate(NOW)
    await repo.add(teacher)
    db_session.expire_all()

    everyone = await repo.search(role=Role.STUDENT, is_active=None, limit=10, offset=0)
    assert everyone.total == 3
    assert len(everyone.users) == 3

    page = await repo.search(role=Role.STUDENT, is_active=None, limit=2, offset=1)
    assert page.total == 3
    assert [u.id for u in page.users] == [u.id for u in everyone.users][1:]

    by_state = await repo.search(
        role=Role.TEACHER,
        is_active=False,
        limit=10,
        offset=0,
    )
    assert [u.id for u in by_state.users] == [teacher.id]
    assert by_state.total == 1

    none_match = await repo.search(
        role=Role.TEACHER,
        is_active=True,
        limit=10,
        offset=0,
    )
    assert none_match.users == []
    assert none_match.total == 0


@pytest.mark.integration
async def test_get_by_email_is_case_insensitive(db_session: AsyncSession) -> None:
    """The address is stored lower-cased: Ivan@b.co and ivan@b.co are one account."""
    repo = SqlAlchemyUserRepository(db_session)
    await repo.add(_user("Ivan@b.co"))
    db_session.expire_all()

    assert await repo.get_by_email("IVAN@b.co") is not None


@pytest.mark.integration
async def test_add_duplicate_email_raises_domain_error(
    db_session: AsyncSession,
) -> None:
    """The unique index turns into a domain error."""
    repo = SqlAlchemyUserRepository(db_session)
    await repo.add(_user("dup-index@b.co"))

    # Inside a SAVEPOINT: the violation aborts the transaction.
    savepoint = await db_session.begin_nested()
    with pytest.raises(EmailAlreadyTakenError):
        await repo.add(_user("dup-index@b.co"))

    # An explicit rollback: a failed savepoint leaves the session unusable.
    await savepoint.rollback()


@pytest.mark.integration
async def test_duplicate_email_conflicts_ignoring_case(
    db_session: AsyncSession,
) -> None:
    """Uniqueness ignores the case of the address too."""
    repo = SqlAlchemyUserRepository(db_session)
    await repo.add(_user("Dup-Case@b.co"))

    savepoint = await db_session.begin_nested()
    with pytest.raises(EmailAlreadyTakenError):
        await repo.add(_user("dup-case@b.co"))

    await savepoint.rollback()


@pytest.mark.integration
async def test_missing_user_returns_none(db_session: AsyncSession) -> None:
    """A missing account is None, not an error."""
    repo = SqlAlchemyUserRepository(db_session)
    assert await repo.get_by_id(uuid.uuid4()) is None
    assert await repo.get_by_email("nobody@b.co") is None


@pytest.mark.integration
async def test_update_persists_the_state(db_session: AsyncSession) -> None:
    """Changes of the account reach its row."""
    repo = SqlAlchemyUserRepository(db_session)
    user = _user("upd@b.co")
    await repo.add(user)
    user_id = user.id

    user.verify_email(NOW)
    user.deactivate(NOW)
    user.change_role(Role.TEACHER)
    user.grant_admin()
    user.update_profile(Profile(last_name_en="Ivanov"))
    await repo.update(user)
    await db_session.flush()
    db_session.expire_all()

    loaded = await repo.get_by_id(user_id)
    assert loaded is not None
    assert loaded.email_verified is True
    assert loaded.is_active is False
    assert loaded.role is Role.TEACHER
    assert loaded.is_admin is True
    assert loaded.profile == Profile(last_name_en="Ivanov")


@pytest.mark.integration
async def test_add_user_before_token_orders_inserts(db_session: AsyncSession) -> None:
    """A token is inserted after its owner, though no relationship() links them."""
    users = SqlAlchemyUserRepository(db_session)
    tokens = SqlAlchemyTokenRepository(db_session)
    user = _user("order@b.co")

    await users.add(user)
    await tokens.add(
        VerificationToken.issue(
            user_id=user.id,
            token_hash="order-token-hash",
            purpose=TokenPurpose.EMAIL_VERIFY,
            now=datetime.now(UTC),
            ttl=timedelta(hours=1),
        ),
    )


@pytest.mark.integration
async def test_token_roundtrip_preserves_tz_aware_expiry(
    db_session: AsyncSession,
) -> None:
    """A token survives the round trip with its zone and its assigned id."""
    users: UserRepository = SqlAlchemyUserRepository(db_session)
    tokens: TokenRepository = SqlAlchemyTokenRepository(db_session)
    user = _user("tok@b.co")
    await users.add(user)

    expires_at = datetime(2026, 7, 20, 12, 0, tzinfo=UTC)
    token = VerificationToken(
        id=None,
        user_id=user.id,
        token_hash="tok-hash",
        purpose=TokenPurpose.EMAIL_VERIFY,
        expires_at=expires_at,
        used_at=None,
    )
    await tokens.add(token)
    assert token.id is not None
    db_session.expire_all()

    loaded = await tokens.get_by_hash("tok-hash", TokenPurpose.EMAIL_VERIFY)
    assert loaded is not None
    assert loaded.id == token.id
    assert loaded.user_id == user.id
    assert loaded.purpose is TokenPurpose.EMAIL_VERIFY
    assert loaded.expires_at.tzinfo is not None
    assert loaded.expires_at == expires_at
    assert loaded.used_at is None


@pytest.mark.integration
async def test_token_update_persists_consumption(db_session: AsyncSession) -> None:
    """Consuming a token reaches its row."""
    users = SqlAlchemyUserRepository(db_session)
    tokens = SqlAlchemyTokenRepository(db_session)
    user = _user("used@b.co")
    await users.add(user)

    now = datetime(2026, 7, 19, 12, 0, tzinfo=UTC)
    token = VerificationToken.issue(
        user_id=user.id,
        token_hash="used-hash",
        purpose=TokenPurpose.PASSWORD_RESET,
        now=now,
        ttl=timedelta(hours=1),
    )
    await tokens.add(token)

    token.consume(now)
    await tokens.update(token)
    await db_session.flush()
    db_session.expire_all()

    loaded = await tokens.get_by_hash("used-hash", TokenPurpose.PASSWORD_RESET)
    assert loaded is not None
    assert loaded.used_at == now


@pytest.mark.integration
async def test_consume_outstanding_kills_only_live_tokens_of_that_purpose(
    db_session: AsyncSession,
) -> None:
    """Consuming the outstanding hits only live tokens of that account and purpose."""
    users = SqlAlchemyUserRepository(db_session)
    tokens: TokenRepository = SqlAlchemyTokenRepository(db_session)
    owner, stranger = _user("rotate@b.co"), _user("bystander@b.co")
    await users.add(owner)
    await users.add(stranger)

    issued = datetime(2026, 7, 19, 12, 0, tzinfo=UTC)
    spent_at = datetime(2026, 7, 19, 12, 30, tzinfo=UTC)
    rotated_at = datetime(2026, 7, 19, 13, 0, tzinfo=UTC)

    def _token(
        user_id: uuid.UUID,
        token_hash: str,
        purpose: TokenPurpose,
    ) -> VerificationToken:
        return VerificationToken.issue(
            user_id=user_id,
            token_hash=token_hash,
            purpose=purpose,
            now=issued,
            ttl=timedelta(hours=2),
        )

    live = _token(owner.id, "live-reset", TokenPurpose.PASSWORD_RESET)
    spent = _token(owner.id, "spent-reset", TokenPurpose.PASSWORD_RESET)
    verify = _token(owner.id, "owner-verify", TokenPurpose.EMAIL_VERIFY)
    foreign = _token(stranger.id, "foreign-reset", TokenPurpose.PASSWORD_RESET)
    for token in (live, spent, verify, foreign):
        await tokens.add(token)
    spent.consume(spent_at)
    await tokens.update(spent)
    await db_session.flush()

    await tokens.consume_outstanding(
        owner.id,
        TokenPurpose.PASSWORD_RESET,
        now=rotated_at,
    )
    await db_session.flush()
    db_session.expire_all()

    async def _used_at(
        token_hash: str,
        purpose: TokenPurpose,
    ) -> datetime | None:
        loaded = await tokens.get_by_hash(token_hash, purpose)
        assert loaded is not None
        return loaded.used_at

    assert await _used_at("live-reset", TokenPurpose.PASSWORD_RESET) == rotated_at
    assert await _used_at("spent-reset", TokenPurpose.PASSWORD_RESET) == spent_at
    assert await _used_at("owner-verify", TokenPurpose.EMAIL_VERIFY) is None
    assert await _used_at("foreign-reset", TokenPurpose.PASSWORD_RESET) is None


@pytest.mark.integration
async def test_consume_outstanding_with_nothing_to_kill_is_not_an_error(
    db_session: AsyncSession,
) -> None:
    """Zero rows touched is a normal outcome."""
    users = SqlAlchemyUserRepository(db_session)
    tokens: TokenRepository = SqlAlchemyTokenRepository(db_session)
    fresh = _user("first-reset@b.co")
    await users.add(fresh)

    await tokens.consume_outstanding(
        fresh.id,
        TokenPurpose.PASSWORD_RESET,
        now=datetime(2026, 7, 19, 12, 0, tzinfo=UTC),
    )


@pytest.mark.integration
async def test_missing_token_returns_none(db_session: AsyncSession) -> None:
    """A missing token is None, not an error."""
    tokens = SqlAlchemyTokenRepository(db_session)
    assert await tokens.get_by_hash("nothing", TokenPurpose.EMAIL_VERIFY) is None


@pytest.mark.integration
async def test_update_missing_user_raises(db_session: AsyncSession) -> None:
    """Updating an unsaved account is an error, not a silent no-op."""
    repo = SqlAlchemyUserRepository(db_session)
    never_stored = _user("ghost@b.co")

    with pytest.raises(EntityNotFoundError):
        await repo.update(never_stored)


@pytest.mark.integration
async def test_update_missing_token_row_raises(db_session: AsyncSession) -> None:
    """Updating a token whose id has no row is an error."""
    tokens = SqlAlchemyTokenRepository(db_session)
    detached = VerificationToken(
        id=2**40,  # an id the table surely lacks
        user_id=uuid.uuid4(),
        token_hash="ghost-hash",
        purpose=TokenPurpose.EMAIL_VERIFY,
        expires_at=datetime(2026, 7, 20, 12, 0, tzinfo=UTC),
        used_at=None,
    )

    with pytest.raises(EntityNotFoundError):
        await tokens.update(detached)


@pytest.mark.integration
async def test_update_unsaved_token_raises(db_session: AsyncSession) -> None:
    """Updating a token that was never stored is an error."""
    tokens = SqlAlchemyTokenRepository(db_session)
    unsaved = VerificationToken.issue(
        user_id=uuid.uuid4(),
        token_hash="unsaved-hash",
        purpose=TokenPurpose.EMAIL_VERIFY,
        now=datetime(2026, 7, 19, 12, 0, tzinfo=UTC),
        ttl=timedelta(hours=1),
    )
    assert unsaved.id is None

    with pytest.raises(EntityNotFoundError):
        await tokens.update(unsaved)


@pytest.mark.integration
async def test_token_is_not_found_under_another_purpose(
    db_session: AsyncSession,
) -> None:
    """A token of one purpose is not found under another."""
    users = SqlAlchemyUserRepository(db_session)
    tokens = SqlAlchemyTokenRepository(db_session)
    user = _user("purpose@b.co")
    await users.add(user)
    await tokens.add(
        VerificationToken.issue(
            user_id=user.id,
            token_hash="purpose-hash",
            purpose=TokenPurpose.EMAIL_VERIFY,
            now=datetime(2026, 7, 19, 12, 0, tzinfo=UTC),
            ttl=timedelta(hours=1),
        ),
    )
    db_session.expire_all()

    found = await tokens.get_by_hash("purpose-hash", TokenPurpose.EMAIL_VERIFY)
    assert found is not None
    assert await tokens.get_by_hash("purpose-hash", TokenPurpose.PASSWORD_RESET) is None


@pytest.mark.integration
async def test_second_consume_of_the_same_row_is_rejected(
    db_session: AsyncSession,
) -> None:
    """The `used_at IS NULL` condition of the UPDATE refuses a second consumption."""
    users = SqlAlchemyUserRepository(db_session)
    tokens = SqlAlchemyTokenRepository(db_session)
    user = _user("race@b.co")
    await users.add(user)

    now = datetime(2026, 7, 19, 12, 0, tzinfo=UTC)
    token = VerificationToken.issue(
        user_id=user.id,
        token_hash="race-hash",
        purpose=TokenPurpose.EMAIL_VERIFY,
        now=now,
        ttl=timedelta(hours=1),
    )
    await tokens.add(token)
    assert token.id is not None

    winner = VerificationToken(
        id=token.id,
        user_id=user.id,
        token_hash="race-hash",
        purpose=TokenPurpose.EMAIL_VERIFY,
        expires_at=token.expires_at,
        used_at=None,
    )
    loser = VerificationToken(
        id=token.id,
        user_id=user.id,
        token_hash="race-hash",
        purpose=TokenPurpose.EMAIL_VERIFY,
        expires_at=token.expires_at,
        used_at=None,
    )

    winner.consume(now)
    await tokens.update(winner)

    later = now + timedelta(minutes=5)
    loser.consume(later)
    with pytest.raises(TokenAlreadyUsedError):
        await tokens.update(loser)

    await db_session.flush()
    db_session.expire_all()
    stored = await tokens.get_by_hash("race-hash", TokenPurpose.EMAIL_VERIFY)
    assert stored is not None
    assert stored.used_at == now, (
        "the consumption of the winner must not be overwritten"
    )


@pytest.mark.integration
async def test_password_hash_update_is_conditional(db_session: AsyncSession) -> None:
    """The hash is replaced only if it is still the one read."""
    users = SqlAlchemyUserRepository(db_session)
    user = _user("rehash@b.co")
    await users.add(user)

    changed = await users.update_password_hash(
        user.id,
        user.password_hash,
        "hashed:upgraded",
    )
    assert changed is True

    # The second caller holds a stale hash: nothing must be written.
    stale = await users.update_password_hash(
        user.id,
        user.password_hash,
        "hashed:from a stale read",
    )
    assert stale is False

    await db_session.flush()
    db_session.expire_all()
    reloaded = await users.get_by_id(user.id)
    assert reloaded is not None
    assert reloaded.password_hash == "hashed:upgraded"


@pytest.mark.integration
async def test_get_by_email_ignores_surrounding_whitespace(
    db_session: AsyncSession,
) -> None:
    """The repository strips surrounding whitespace."""
    repo: UserRepository = SqlAlchemyUserRepository(db_session)
    user = _user("spaced@b.co")
    await repo.add(user)
    db_session.expire_all()

    found = await repo.get_by_email("  spaced@b.co\t")
    assert found is not None
    assert found.id == user.id


@pytest.mark.integration
async def test_tokens_invalidated_after_round_trips(db_session: AsyncSession) -> None:
    """The kill-switch mark reaches its column and comes back."""
    repo: UserRepository = SqlAlchemyUserRepository(db_session)
    user = _user("kill@b.co")
    await repo.add(user)
    user_id = user.id
    mark = datetime(2026, 7, 19, 12, 0, tzinfo=UTC)
    user.invalidate_tokens(mark)
    await repo.update(user)
    # Flush before expire_all(), or the UPDATE never reaches the database.
    await db_session.flush()
    db_session.expire_all()

    reloaded = await repo.get_by_id(user_id)
    assert reloaded is not None
    assert reloaded.tokens_invalidated_after == mark


@pytest.mark.integration
async def test_outbox_add_writes_event_row(db_session: AsyncSession) -> None:
    """`outbox.add` writes the name and payload as a readable row."""
    outbox = SqlAlchemyOutbox(db_session)
    payload = {"user_id": str(uuid.uuid4())}
    # A unique name: registration writes auth.user_registered to the same table.
    event = DomainEvent(name=f"test.outbox.{uuid.uuid4()}", payload=payload)
    await outbox.add([event])
    db_session.expire_all()

    rows = (
        await db_session.scalars(
            select(OutboxModel).where(OutboxModel.event_name == event.name),
        )
    ).all()
    assert len(rows) == 1
    row = rows[0]
    assert row.payload == payload
    assert row.status is OutboxStatus.PENDING
    assert row.created_at is not None
    assert row.published_at is None


@pytest.mark.integration
async def test_outbox_add_shares_the_transaction(db_engine: AsyncEngine) -> None:
    """The event is written in the same transaction and leaves with its rollback."""
    event = DomainEvent(
        name=f"test.outbox.{uuid.uuid4()}",
        payload={"user_id": str(uuid.uuid4())},
    )
    async with db_engine.connect() as conn:
        session = AsyncSession(bind=conn, expire_on_commit=False)
        outbox = SqlAlchemyOutbox(session)
        await outbox.add([event])
        await session.rollback()
        await session.close()

    async with db_engine.connect() as verifier:
        survived = await verifier.scalar(
            select(func.count())
            .select_from(OutboxModel)
            .where(OutboxModel.event_name == event.name),
        )
    assert survived == 0


@pytest.mark.integration
async def test_delete_removes_the_account_and_its_tokens(
    db_session: AsyncSession,
) -> None:
    """The tokens leave with the account through the foreign key."""
    users = SqlAlchemyUserRepository(db_session)
    tokens = SqlAlchemyTokenRepository(db_session)
    user = _user("gone@b.co")
    await users.add(user)
    token = VerificationToken.issue(
        user_id=user.id,
        token_hash="gone-hash",
        purpose=TokenPurpose.EMAIL_VERIFY,
        now=NOW,
        ttl=timedelta(hours=1),
    )
    await tokens.add(token)

    assert await users.delete(user.id) is True
    assert await users.delete(user.id) is False
    db_session.expire_all()
    assert await users.get_by_id(user.id) is None
    assert await tokens.get_by_hash("gone-hash", TokenPurpose.EMAIL_VERIFY) is None
