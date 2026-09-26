"""In-memory fakes of the auth ports for use-case tests."""

from __future__ import annotations

import copy
import itertools
import uuid
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING, Self, override

from pydantic import SecretStr

from vld.auth.application import (
    AccessClaims,
    DeviceClaims,
    RefreshClaims,
    SendPasswordResetEmail,
    SendVerificationEmail,
    UsersPage,
)
from vld.auth.config import JwtSettings, PasswordSettings, VerificationSettings
from vld.auth.domain import (
    EmailAlreadyTakenError,
    EntityNotFoundError,
    TokenAlreadyUsedError,
    VerificationToken,
    normalize_email,
)
from vld.core.audit import AuditLog, AuditPage, AuditQuery, AuditRecord
from vld.core.database import UnitOfWork
from vld.core.ratelimit import RateLimitExceededError

if TYPE_CHECKING:
    from collections.abc import Sequence
    from types import TracebackType

    from vld.auth.application import (
        Clock,
        EmailSender,
        Outbox,
        PasswordHasher,
        RateLimiter,
        RefreshedPairCache,
        RevocationStore,
        TokenIssuer,
        TokenRepository,
        UserRepository,
    )
    from vld.auth.domain import (
        DomainEvent,
        Role,
        TokenPurpose,
        User,
    )
    from vld.core.audit import AuditEntry

NOW = datetime(2026, 7, 19, 12, 0, tzinfo=UTC)
PASSWORD_SETTINGS = PasswordSettings()
REQUIRE_VERIFIED = VerificationSettings()
ALLOW_UNVERIFIED = VerificationSettings(require_email_verification=False)
GOOD_PASSWORD = "Correct Horse Battery"


class FakeUserRepository:
    """Accounts in memory."""

    add_attempts: int

    def __init__(self) -> None:
        self.items: dict[uuid.UUID, User] = {}
        self.add_attempts = 0
        self.password_hashes: dict[uuid.UUID, str] = {}

    async def add(self, user: User) -> None:
        """Store an account, refusing a taken address."""
        self.add_attempts += 1
        if await self.get_by_email(user.email) is not None:
            msg = "email already taken"
            raise EmailAlreadyTakenError(msg)
        self.items[user.id] = copy.deepcopy(user)
        self.password_hashes[user.id] = user.password_hash

    async def get_by_id(self, user_id: uuid.UUID) -> User | None:
        """Return a copy of the account, or None."""
        stored = self.items.get(user_id)
        return None if stored is None else copy.deepcopy(stored)

    async def get_by_email(self, email: str) -> User | None:
        """Find an account by its normalized address."""
        return next(
            (u for u in self.items.values() if u.email == normalize_email(email)),
            None,
        )

    async def search(
        self,
        *,
        role: Role | None,
        is_active: bool | None,
        limit: int,
        offset: int,
    ) -> UsersPage:
        """Filter accounts by role and access state."""
        # Real filters, in insertion order like ORDER BY created_at.
        matched = [
            user
            for user in self.items.values()
            if (role is None or user.role is role)
            and (is_active is None or user.is_active is is_active)
        ]
        return UsersPage(users=matched[offset : offset + limit], total=len(matched))

    async def update_password_hash(
        self,
        user_id: uuid.UUID,
        expected_hash: str,
        new_hash: str,
    ) -> bool:
        """Replace the hash only if it still matches."""
        # The condition of the live `WHERE password_hash = :expected`.
        if self.password_hashes.get(user_id) != expected_hash:
            return False
        self.password_hashes[user_id] = new_hash
        return True

    async def update(self, user: User) -> None:
        """Overwrite a stored account."""
        if user.id not in self.items:
            msg = f"user {user.id} was never stored"
            raise EntityNotFoundError(msg)
        self.items[user.id] = copy.deepcopy(user)

    async def delete(self, user_id: uuid.UUID) -> bool:
        """Remove an account."""
        _ = self.password_hashes.pop(user_id, None)
        return self.items.pop(user_id, None) is not None


class FakeTokenRepository:
    """One-time tokens in memory."""

    def __init__(self) -> None:
        self.items: list[VerificationToken] = []
        self.consumed: dict[int, datetime] = {}

    async def add(self, token: VerificationToken) -> None:
        """Store a token, assigning its id."""
        token.id = len(self.items) + 1
        self.items.append(token)

    async def get_by_hash(
        self,
        token_hash: str,
        purpose: TokenPurpose,
    ) -> VerificationToken | None:
        """Find a token by hash and purpose."""
        stored = next(
            (
                t
                for t in self.items
                if t.token_hash == token_hash and t.purpose is purpose
            ),
            None,
        )
        return None if stored is None else self._load(stored)

    async def consume_outstanding(
        self,
        user_id: uuid.UUID,
        purpose: TokenPurpose,
        *,
        now: datetime,
    ) -> None:
        """Consume every live token of the account with this purpose."""
        for stored in self.items:
            assert stored.id is not None
            if (
                stored.user_id == user_id
                and stored.purpose is purpose
                and stored.id not in self.consumed
            ):
                self.consumed[stored.id] = now

    async def update(self, token: VerificationToken) -> None:
        """Record the consumption, refusing a second one."""
        if token.id is None:
            msg = "token was never stored"
            raise EntityNotFoundError(msg)
        if token.id in self.consumed:
            msg = f"token {token.id} was already consumed"
            raise TokenAlreadyUsedError(msg)
        if token.used_at is None:
            msg = f"token {token.id} has nothing to persist"
            raise EntityNotFoundError(msg)
        self.consumed[token.id] = token.used_at

    def _load(self, stored: VerificationToken) -> VerificationToken:
        """Build the entity from a "row", as the mapper does."""
        assert stored.id is not None
        return VerificationToken(
            id=stored.id,
            user_id=stored.user_id,
            token_hash=stored.token_hash,
            purpose=stored.purpose,
            expires_at=stored.expires_at,
            used_at=self.consumed.get(stored.id),
        )


class StaleReadTokenRepository(FakeTokenRepository):
    """A store that always returns the token unconsumed."""

    @override
    def _load(self, stored: VerificationToken) -> VerificationToken:
        assert stored.id is not None
        return VerificationToken(
            id=stored.id,
            user_id=stored.user_id,
            token_hash=stored.token_hash,
            purpose=stored.purpose,
            expires_at=stored.expires_at,
            used_at=None,
        )


class FakeHasher:
    """A reversible "hash"."""

    _stale_prefix: str
    _generation: str

    def __init__(self, stale_prefix: str = "hashed:", generation: str = "") -> None:
        self.verified: list[tuple[str, str]] = []
        self.hashed: list[str] = []
        self._stale_prefix = stale_prefix
        self._generation = generation

    async def hash(self, password: str) -> str:
        """Return a reversible hash."""
        self.hashed.append(password)
        return f"hashed{self._generation}:{password}"

    async def verify(self, password: str, password_hash: str) -> bool:
        """Check a password against its hash."""
        self.verified.append((password, password_hash))
        # The generation is ignored, the prefix is not: otherwise any junk would match.
        prefix, separator, candidate = password_hash.partition(":")
        return bool(separator) and prefix.startswith("hashed") and candidate == password

    def needs_rehash(self, password_hash: str) -> bool:
        """Tell whether a hash is of an older generation."""
        return not password_hash.startswith(self._stale_prefix)


class FakeEmailSender:
    """Collects sent letters, one list per kind."""

    def __init__(self) -> None:
        self.sent: list[tuple[str, str]] = []
        self.reset_sent: list[tuple[str, str]] = []

    async def send_verification(self, email: str, token: str) -> None:
        """Record a confirmation letter."""
        self.sent.append((email, token))

    async def send_password_reset(self, email: str, token: str) -> None:
        """Record a reset letter."""
        self.reset_sent.append((email, token))


class FakeOutbox:
    """Collects domain events instead of writing them."""

    def __init__(self) -> None:
        self.events: list[DomainEvent] = []

    async def add(self, events: Sequence[DomainEvent]) -> None:
        """Collect events."""
        self.events.extend(events)


class FrozenClock:
    """A clock that stands still until moved."""

    _now: datetime

    def __init__(self, now: datetime = NOW) -> None:
        self._now = now

    def now(self) -> datetime:
        """Return the frozen moment."""
        return self._now

    def advance(self, delta: timedelta) -> None:
        """Move the clock forward."""
        self._now += delta


class FakeUnitOfWork(UnitOfWork):
    """A transaction boundary that records commits."""

    committed: bool
    rolled_back: bool

    def __init__(self) -> None:
        self.committed = False
        self.rolled_back = False

    @override
    async def __aenter__(self) -> Self:
        return self

    @override
    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        del exc_type, exc, tb
        if not self.committed:
            self.rolled_back = True

    @override
    async def commit(self) -> None:
        self.committed = True

    @override
    async def rollback(self) -> None:
        self.rolled_back = True

    @override
    async def flush(self) -> None:
        return None


class FakeAuditLog(AuditLog):
    """Audit log in memory."""

    def __init__(self) -> None:
        self.entries: list[AuditEntry] = []

    @override
    async def record(self, entry: AuditEntry) -> None:
        self.entries.append(entry)


class FakeAuditQuery(AuditQuery):
    """Reads the entries of a `FakeAuditLog`."""

    _log: FakeAuditLog
    _now: datetime

    def __init__(self, log: FakeAuditLog, now: datetime = NOW) -> None:
        self._log = log
        self._now = now

    @override
    async def search(
        self,
        *,
        actor_id: uuid.UUID | None,
        target_id: uuid.UUID | None,
        occurred_from: datetime | None,
        occurred_to: datetime | None,
        limit: int,
        offset: int,
    ) -> AuditPage:
        matching = [
            AuditRecord(
                id=number,
                occurred_at=self._now,
                action=str(entry.action),
                actor_id=entry.actor_id,
                target_id=entry.target_id,
                payload=entry.payload,
            )
            for number, entry in enumerate(self._log.entries, start=1)
            if (actor_id is None or entry.actor_id == actor_id)
            and (target_id is None or entry.target_id == target_id)
            and (occurred_from is None or self._now >= occurred_from)
            and (occurred_to is None or self._now < occurred_to)
        ]
        matching.reverse()
        return AuditPage(records=matching[offset : offset + limit], total=len(matching))


class AuditWriteFailedError(Exception):
    """The audit log refused."""


class FailingAuditLog(AuditLog):
    """An audit log that cannot write."""

    attempts: int

    def __init__(self) -> None:
        self.attempts = 0

    @override
    async def record(self, entry: AuditEntry) -> None:
        del entry
        self.attempts += 1
        msg = "audit write failed"
        raise AuditWriteFailedError(msg)


class FakeRevocationStore:
    """Revocation list in memory."""

    def __init__(self) -> None:
        self.revoked: dict[str, int] = {}
        self.values: dict[str, str] = {}

    async def revoke(self, jti: str, ttl_seconds: int) -> None:
        """Revoke a token id unless it is already revoked."""
        if ttl_seconds <= 0:
            msg = f"SETEX with non-positive ttl: {ttl_seconds}"
            raise ValueError(msg)
        # NX of the live SET: a taken key is not overwritten.
        if jti in self.revoked:
            return
        self.revoked[jti] = ttl_seconds
        self.values[jti] = "revoked"

    async def revoke_if_new(self, jti: str, ttl_seconds: int) -> bool:
        """Revoke a token id once, telling whether this call did it."""
        # Check and write with no await between them, like SET NX.
        if jti in self.revoked:
            return False
        await self.revoke(jti, ttl_seconds)
        return True

    async def mark_rotated(self, jti: str) -> None:
        """Mark a revoked token id as rotated."""
        # XX of the live SET: the mark lands only on an existing key.
        if jti in self.revoked:
            self.values[jti] = "rotated"

    async def was_rotated(self, jti: str) -> bool:
        """Tell whether the token id was rotated."""
        return self.values.get(jti) == "rotated"

    async def is_revoked(self, jti: str) -> bool:
        """Tell whether the token id is revoked."""
        return jti in self.revoked


class FakeRefreshedPairCache:
    """Cache of issued pairs in memory."""

    def __init__(self) -> None:
        self.pairs: dict[str, tuple[str, str]] = {}
        self.ttls: dict[str, int] = {}

    async def save(
        self,
        jti: str,
        access: str,
        refresh: str,
        ttl_seconds: int,
    ) -> bool:
        """Remember the pair issued for a token id."""
        if ttl_seconds <= 0:
            msg = f"SET EX with non-positive ttl: {ttl_seconds}"
            raise ValueError(msg)
        self.pairs[jti] = (access, refresh)
        self.ttls[jti] = ttl_seconds
        return True

    async def load(self, jti: str) -> tuple[str, str] | None:
        """Return the pair issued for a token id."""
        return self.pairs.get(jti)


class FakeTokenIssuer:
    """Issues tokens without cryptography."""

    _default_ttl: int
    _session_ttl: int
    _clock: FrozenClock
    _issued: int

    def __init__(
        self,
        ttl_seconds: int = 3600,
        # The default of JwtSettings as a literal, to stay off the environment.
        session_ttl_seconds: int = 90 * 24 * 3600,
        clock: FrozenClock | None = None,
    ) -> None:
        self.exp: dict[str, datetime] = {}
        self.iat: dict[str, datetime] = {}
        self.session_exps: dict[str, datetime] = {}
        self._default_ttl = ttl_seconds
        self._session_ttl = session_ttl_seconds
        self._clock = clock or FrozenClock()
        self._issued = 0

    def issue_pair(
        self,
        user_id: uuid.UUID,
        session_exp: datetime | None = None,
        *,
        not_before: datetime | None = None,
    ) -> tuple[str, str]:
        """Issue a readable pair of tokens."""
        now = self._clock.now()
        if not_before is not None:
            now = max(now, not_before)
        if session_exp is None:
            session_exp = now + timedelta(seconds=self._session_ttl)
        self._issued += 1
        access = f"access:{user_id}:a{self._issued}"
        refresh = f"refresh:{user_id}:r{self._issued}"
        self.iat[access] = self.iat[refresh] = now.replace(microsecond=0)
        self.exp[access] = now + timedelta(seconds=self._default_ttl)
        self.exp[refresh] = min(
            now + timedelta(seconds=self._default_ttl),
            session_exp,
        )
        self.session_exps[refresh] = session_exp
        return access, refresh

    def parse_refresh(self, token: str) -> RefreshClaims:
        """Parse a refresh token."""
        user_id, jti = self._parse(token, "refresh")
        return RefreshClaims(
            user_id=user_id,
            jti=jti,
            issued_at=self.iat[token],
            session_exp=self.session_exps[token],
        )

    def parse_access(self, token: str) -> AccessClaims:
        """Parse an access token."""
        user_id, jti = self._parse(token, "access")
        # iat in whole seconds, like the live issuer.
        return AccessClaims(user_id=user_id, jti=jti, issued_at=self.iat[token])

    def issue_device(self, user_id: uuid.UUID) -> str:
        """Issue a device marker."""
        now = self._clock.now()
        self._issued += 1
        token = f"device:{user_id}:d{self._issued}"
        # Whole seconds: PyJWT drops the microseconds.
        self.iat[token] = now.replace(microsecond=0)
        self.exp[token] = now + timedelta(days=365)
        return token

    def parse_device(self, token: str) -> DeviceClaims:
        """Parse a device marker."""
        user_id, _jti = self._parse(token, "device")
        # iat as the live issuer gives it: the kill switch compares it.
        return DeviceClaims(user_id=user_id, issued_at=self.iat[token])

    def remaining_ttl_seconds(self, token: str) -> int:
        """Tell how many seconds a token has left."""
        if token not in self.exp:
            msg = "invalid token"
            raise ValueError(msg)
        return int((self.exp[token] - self._clock.now()).total_seconds())

    def _parse(self, token: str, expected: str) -> tuple[uuid.UUID, str]:
        parts = token.split(":")
        if len(parts) != 3 or parts[0] != expected:
            msg = "invalid token"
            raise ValueError(msg)
        # Strictly >: a token with zero TTL still parses, so the Logout guard is reachable.
        if token in self.exp and self._clock.now() > self.exp[token]:
            msg = "invalid token"
            raise ValueError(msg)
        return uuid.UUID(parts[1]), parts[2]


class CountingLimiter:
    """A limiter that really counts per bucket."""

    limit: int | None

    def __init__(self, limit: int | None = None) -> None:
        self.limit = limit
        self.keys: list[str] = []
        self.counts: dict[str, int] = {}
        self.windows: dict[str, int] = {}

    async def hit(self, key: str, limit: int, window_ms: int) -> None:
        """Count an attempt, refusing one over the limit."""
        threshold = limit if self.limit is None else self.limit
        self.keys.append(key)
        # The window is recorded so tests can observe it.
        self.windows[key] = window_ms
        self.counts[key] = self.counts.get(key, 0) + 1
        if self.counts[key] > threshold:
            raise RateLimitExceededError(retry_after=max(1, window_ms // 1000))

    async def reset(self, key: str) -> None:
        """Forget the count of a bucket."""
        _ = self.counts.pop(key, None)


class AllowAllLimiter(CountingLimiter):
    """A limiter that limits nothing but remembers the keys."""

    def __init__(self) -> None:
        super().__init__(limit=10**9)


class DenyAllLimiter(CountingLimiter):
    """A limiter that refuses everything."""

    def __init__(self) -> None:
        super().__init__(limit=0)


# One counter per process, like an identity column: two events never share a token.
_DELIVERY_IDS = itertools.count(1)

# The value is not observable, but the settings demand a usable length.
_DRAIN_SETTINGS = JwtSettings(secret_key=SecretStr("f" * 32))


async def deliver_pending_verifications(
    outbox: FakeOutbox,
    users: FakeUserRepository,
    tokens: FakeTokenRepository,
    email: FakeEmailSender,
    clock: FrozenClock | None = None,
) -> None:
    """Run the collected `user_registered` events through the real handler."""
    handler = SendVerificationEmail(
        users,
        tokens,
        email,
        clock or FrozenClock(NOW),
        _DRAIN_SETTINGS,
    )
    pending = [e for e in outbox.events if e.name == "auth.user_registered"]
    outbox.events = [e for e in outbox.events if e.name != "auth.user_registered"]
    for event in pending:
        recipient, raw_token = await handler.prepare(event, next(_DELIVERY_IDS))
        await handler.deliver(recipient, raw_token)


async def deliver_pending_password_resets(
    outbox: FakeOutbox,
    users: FakeUserRepository,
    tokens: FakeTokenRepository,
    email: FakeEmailSender,
    clock: FrozenClock | None = None,
) -> None:
    """Run the collected `password_reset_requested` events through the real handler."""
    handler = SendPasswordResetEmail(
        users,
        tokens,
        email,
        clock or FrozenClock(NOW),
        _DRAIN_SETTINGS,
    )
    name = "auth.password_reset_requested"
    pending = [e for e in outbox.events if e.name == name]
    outbox.events = [e for e in outbox.events if e.name != name]
    for event in pending:
        recipient, raw_token = await handler.prepare(event, next(_DELIVERY_IDS))
        await handler.deliver(recipient, raw_token)


if TYPE_CHECKING:
    # Assigning to a typed name catches a fake drifting from its port.
    _users: UserRepository = FakeUserRepository()
    _tokens: TokenRepository = FakeTokenRepository()
    _hasher: PasswordHasher = FakeHasher()
    _email: EmailSender = FakeEmailSender()
    _outbox: Outbox = FakeOutbox()
    _clock: Clock = FrozenClock()
    _uow: UnitOfWork = FakeUnitOfWork()
    _revocation: RevocationStore = FakeRevocationStore()
    _refreshed: RefreshedPairCache = FakeRefreshedPairCache()
    _issuer: TokenIssuer = FakeTokenIssuer()
    _allow: RateLimiter = AllowAllLimiter()
    _deny: RateLimiter = DenyAllLimiter()
    _counting: RateLimiter = CountingLimiter()
    _audit: AuditLog = FakeAuditLog()
    _failing_audit: AuditLog = FailingAuditLog()
    _audit_query: AuditQuery = FakeAuditQuery(FakeAuditLog())
