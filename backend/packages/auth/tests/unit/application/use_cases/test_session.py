"""Refreshing and ending a session."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import timedelta
from typing import TYPE_CHECKING, override

import pytest
import structlog
from auth_fakes import (
    NOW,
    REQUIRE_VERIFIED,
    AuditWriteFailedError,
    FailingAuditLog,
    FakeAuditLog,
    FakeRefreshedPairCache,
    FakeRevocationStore,
    FakeTokenIssuer,
    FakeUnitOfWork,
    FakeUserRepository,
    FrozenClock,
)

from vld.auth.application import (
    InvalidRefreshTokenError,
    Logout,
    RefreshTokens,
    RevocationCheckUnavailableError,
    TokenRevokedError,
)
from vld.auth.domain import (
    AccountDeactivatedError,
    AccountGoneError,
    EmailNotVerifiedError,
    Role,
    User,
)
from vld.core.audit import AuditAction

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence


def _user(*, verified: bool = True) -> User:
    return User(
        id=uuid.uuid4(),
        email="u@b.co",
        email_verified_at=NOW if verified else None,
        password_hash="hashed:whatever",
        role=Role.STUDENT,
        is_admin=False,
        is_active=True,
    )


@dataclass
class _Deps:
    """Fakes and the use cases built on them."""

    issuer: FakeTokenIssuer = field(default_factory=FakeTokenIssuer)
    revocation: FakeRevocationStore = field(default_factory=FakeRevocationStore)
    refreshed: FakeRefreshedPairCache = field(default_factory=FakeRefreshedPairCache)
    users: FakeUserRepository = field(default_factory=FakeUserRepository)
    clock: FrozenClock = field(default_factory=FrozenClock)
    uow: FakeUnitOfWork = field(default_factory=FakeUnitOfWork)
    audit: FakeAuditLog = field(default_factory=FakeAuditLog)

    def refresh(self) -> RefreshTokens:
        """Build the refresh."""
        return RefreshTokens(
            issuer=self.issuer,
            revocation=self.revocation,
            refreshed=self.refreshed,
            users=self.users,
            uow=self.uow,
            verification=REQUIRE_VERIFIED,
        )

    def logout(self) -> Logout:
        """Build the logout."""
        return Logout(
            issuer=self.issuer,
            revocation=self.revocation,
            uow=self.uow,
            audit=self.audit,
        )

    async def session_for(self, user: User) -> tuple[str, str]:
        """Store the account and issue it a pair."""
        await self.users.add(user)
        return self.issuer.issue_pair(user.id)


def _reuse_alerts(logs: Sequence[Mapping[str, object]]) -> list[Mapping[str, object]]:
    """Pick the reuse alerts out of the captured log."""
    return [r for r in logs if r.get("event") == "refresh_token_reuse_detected"]


# ── Refresh ─────────────────────────────────────────────────────────────────


async def test_refresh_rotates_the_pair_and_revokes_the_old_token() -> None:
    """The presented token is void at once."""
    deps = _Deps()
    user = _user()
    _, refresh = await deps.session_for(user)
    old_jti = deps.issuer.parse_refresh(refresh).jti

    pair = await deps.refresh()(refresh)

    assert pair.refresh != refresh
    assert deps.issuer.parse_refresh(pair.refresh).user_id == user.id
    assert old_jti in deps.revocation.revoked


async def test_retry_within_grace_returns_the_identical_pair() -> None:
    """A repeat within the grace window is a retry and gets the very same pair."""
    deps = _Deps()
    _, refresh = await deps.session_for(_user())
    use_case = deps.refresh()

    first = await use_case(refresh)
    second = await use_case(refresh)

    assert second == first


async def test_rotation_caches_the_pair_under_the_old_jti_for_thirty_seconds() -> None:
    """The pair is cached under the presented jti for thirty seconds."""
    deps = _Deps()
    _, refresh = await deps.session_for(_user())
    old_jti = deps.issuer.parse_refresh(refresh).jti

    pair = await deps.refresh()(refresh)

    assert deps.refreshed.pairs[old_jti] == (pair.access, pair.refresh)
    assert deps.refreshed.ttls[old_jti] == 30


async def test_reuse_after_grace_is_refused_and_alerted_but_spares_the_family() -> None:
    """A rotated jti after the grace window is refused and alerted, sparing the family."""
    clock = FrozenClock()
    deps = _Deps(clock=clock, issuer=FakeTokenIssuer(clock=clock))
    user = _user()
    _, refresh = await deps.session_for(user)
    use_case = deps.refresh()
    pair = await use_case(refresh)

    deps.refreshed.pairs.clear()  # the window is over
    clock.advance(timedelta(seconds=31))

    with structlog.testing.capture_logs() as logs, pytest.raises(TokenRevokedError):
        _ = await use_case(refresh)

    alerts = _reuse_alerts(logs)
    assert len(alerts) == 1, f"no reuse alert: {logs}"
    assert alerts[0]["user_id"] == str(user.id)
    assert alerts[0]["log_level"] == "warning"
    assert user.tokens_invalidated_after is None, (
        "the detector must not void the account: its false positive rate is unmeasured"
    )
    assert await use_case(pair.refresh), "the detector killed a live sibling session"


async def test_a_repeat_after_logout_is_not_reuse() -> None:
    """A refresh after logout is a 401 and no alert."""
    deps = _Deps()
    user = _user()
    access, refresh = await deps.session_for(user)
    await deps.logout()(refresh, access)

    with structlog.testing.capture_logs() as logs, pytest.raises(TokenRevokedError):
        _ = await deps.refresh()(refresh)

    assert not _reuse_alerts(logs), "a logout must not look like reuse"


async def test_logout_after_rotation_does_not_disarm_the_detector() -> None:
    """A logout with a rotated token does not disarm the detector."""
    clock = FrozenClock()
    deps = _Deps(clock=clock, issuer=FakeTokenIssuer(clock=clock))
    user = _user()
    access, refresh = await deps.session_for(user)
    use_case = deps.refresh()
    _ = await use_case(refresh)

    await deps.logout()(refresh, access)

    deps.refreshed.pairs.clear()  # the window is over
    clock.advance(timedelta(seconds=31))

    with structlog.testing.capture_logs() as logs, pytest.raises(TokenRevokedError):
        _ = await use_case(refresh)
    assert _reuse_alerts(logs), "a logout with a rotated token erased the signal"


async def test_a_retry_after_a_downstream_refusal_is_not_reuse() -> None:
    """A retry after a downstream refusal is a 401, not a reuse."""
    deps = _Deps()
    user = _user()
    _, refresh = await deps.session_for(user)
    user.deactivate(NOW)
    await deps.users.update(user)
    use_case = deps.refresh()
    with pytest.raises(AccountDeactivatedError):
        _ = await use_case(refresh)

    with structlog.testing.capture_logs() as logs, pytest.raises(TokenRevokedError):
        _ = await use_case(refresh)

    assert not _reuse_alerts(logs), "a downstream refusal must not look like reuse"


async def test_a_lost_grace_write_is_not_reported_as_reuse() -> None:
    """A lost grace write is a 401 on retry, not a reuse."""

    class _WriteLost(FakeRefreshedPairCache):
        """A cache whose write was lost, as with a blinking Redis."""

        @override
        async def save(
            self,
            jti: str,
            access: str,
            refresh: str,
            ttl_seconds: int,
        ) -> bool:
            del jti, access, refresh, ttl_seconds
            return False

    deps = _Deps(refreshed=_WriteLost())
    user = _user()
    _, refresh = await deps.session_for(user)
    use_case = deps.refresh()
    _ = await use_case(refresh)

    with structlog.testing.capture_logs() as logs, pytest.raises(TokenRevokedError):
        _ = await use_case(refresh)

    assert not _reuse_alerts(logs), "a lost grace key must not look like reuse"


async def test_a_racing_loser_is_not_mistaken_for_reuse() -> None:
    """The loser of a race landing between the revocation and the cache write."""

    class _SlowWriter(FakeRefreshedPairCache):
        """A cache that shows the write of the winner only on the second read."""

        misses: int = 0

        @override
        async def load(self, jti: str) -> tuple[str, str] | None:
            self.misses += 1
            if self.misses == 1:
                return None
            return await super().load(jti)

    deps = _Deps(refreshed=_SlowWriter())
    user = _user()
    _, refresh = await deps.session_for(user)
    use_case = deps.refresh()
    first = await use_case(refresh)

    with structlog.testing.capture_logs() as logs:
        second = await use_case(refresh)

    assert second == first
    assert not _reuse_alerts(logs), "a double click must not look like theft"


async def test_unavailable_grace_cache_is_not_reported_as_reuse() -> None:
    """A cache that is down is a 503, not a reuse."""

    class _Down(FakeRefreshedPairCache):
        @override
        async def load(self, jti: str) -> tuple[str, str] | None:
            del jti
            msg = "refreshed pair cache is unavailable"
            raise RevocationCheckUnavailableError(msg)

    deps = _Deps(refreshed=_Down())
    user = _user()
    _, refresh = await deps.session_for(user)
    use_case = deps.refresh()
    _ = await use_case(refresh)

    with (
        structlog.testing.capture_logs() as logs,
        pytest.raises(RevocationCheckUnavailableError),
    ):
        _ = await use_case(refresh)
    assert not _reuse_alerts(logs)


async def test_access_token_cannot_extend_the_session() -> None:
    """An access token does not refresh."""
    deps = _Deps()
    access, _ = await deps.session_for(_user())

    with pytest.raises(ValueError, match="invalid token"):
        _ = await deps.refresh()(access)


async def test_refresh_rechecks_that_the_account_is_active() -> None:
    """A deactivated account cannot extend its session."""
    deps = _Deps()
    user = _user()
    _, refresh = await deps.session_for(user)
    user.deactivate(NOW)
    await deps.users.update(user)

    with pytest.raises(AccountDeactivatedError):
        _ = await deps.refresh()(refresh)


async def test_refresh_of_an_unverified_account_asks_to_confirm_the_email() -> None:
    """An unconfirmed address answers the refresh as it answers the login."""
    deps = _Deps()
    user = _user(verified=False)
    _, refresh = await deps.session_for(user)

    with pytest.raises(EmailNotVerifiedError):
        _ = await deps.refresh()(refresh)


async def test_refresh_of_a_vanished_account_is_rejected() -> None:
    """A deleted account cannot refresh."""
    deps = _Deps()
    user = _user()
    _, refresh = await deps.session_for(user)
    deps.users.items.clear()

    # The row is gone before the domain object is built.
    with pytest.raises(AccountGoneError):
        _ = await deps.refresh()(refresh)


async def test_unavailable_revocation_store_is_not_reported_as_revoked() -> None:
    """A store that is down differs from a revoked token."""

    class _UnavailableStore(FakeRevocationStore):
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

    deps = _Deps(revocation=_UnavailableStore())
    _, refresh = await deps.session_for(_user())

    with pytest.raises(RevocationCheckUnavailableError):
        _ = await deps.refresh()(refresh)


async def test_refresh_revokes_for_the_token_own_lifetime() -> None:
    """The revocation lasts as long as the token itself."""
    deps = _Deps(issuer=FakeTokenIssuer(ttl_seconds=1234))
    _, refresh = await deps.session_for(_user())
    jti = deps.issuer.parse_refresh(refresh).jti

    _ = await deps.refresh()(refresh)

    assert deps.revocation.revoked[jti] == 1234


async def test_session_ceiling_survives_rotation_and_finally_cuts() -> None:
    """Refreshing every 29 days keeps the ceiling, which finally cuts."""
    clock = FrozenClock()
    issuer = FakeTokenIssuer(ttl_seconds=30 * 24 * 3600, clock=clock)
    deps = _Deps(issuer=issuer)
    user = _user()
    _, refresh = await deps.session_for(user)
    ceiling = issuer.session_exps[refresh]

    for _ in range(3):  # days 29, 58, 87 are within the ceiling
        clock.advance(timedelta(days=29))
        pair = await deps.refresh()(refresh)
        refresh = pair.refresh
        assert issuer.session_exps[refresh] == ceiling

    clock.advance(timedelta(days=29))  # day 116 is past the ceiling of 90
    with pytest.raises(InvalidRefreshTokenError):
        _ = await deps.refresh()(refresh)


async def test_kill_switch_cuts_tokens_issued_before_the_mark() -> None:
    """A pair issued before the mark is refused by its `iat`."""
    clock = FrozenClock()
    deps = _Deps(issuer=FakeTokenIssuer(clock=clock))
    user = _user()
    _, refresh = await deps.session_for(user)

    jti = deps.issuer.parse_refresh(refresh).jti

    clock.advance(timedelta(minutes=5))
    user.invalidate_tokens(clock.now())
    await deps.users.update(user)
    clock.advance(timedelta(minutes=5))

    with pytest.raises(TokenRevokedError):
        _ = await deps.refresh()(refresh)

    # A cut token burns its jti: the revocation runs before the database.
    assert jti in deps.revocation.revoked


async def test_kill_switch_spares_tokens_issued_after_the_mark() -> None:
    """A pair issued after the mark passes."""
    clock = FrozenClock()
    deps = _Deps(issuer=FakeTokenIssuer(clock=clock))
    user = _user()
    user.invalidate_tokens(clock.now())
    clock.advance(timedelta(minutes=5))
    _, refresh = await deps.session_for(user)

    pair = await deps.refresh()(refresh)

    assert pair.access


async def test_kill_switch_spares_a_token_issued_exactly_at_the_mark() -> None:
    """At `iat == mark` the token is valid."""
    clock = FrozenClock()
    deps = _Deps(issuer=FakeTokenIssuer(clock=clock))
    user = _user()
    user.invalidate_tokens(clock.now())
    _, refresh = await deps.session_for(user)  # iat exactly at the mark

    pair = await deps.refresh()(refresh)

    assert pair.access


async def test_kill_switch_cuts_a_token_issued_earlier_in_the_marks_second() -> None:
    """A mid-second mark cuts a token issued earlier in that second."""
    clock = FrozenClock()
    deps = _Deps(issuer=FakeTokenIssuer(clock=clock))
    user = _user()

    clock.advance(timedelta(milliseconds=100))
    _, refresh = await deps.session_for(user)  # iat = 12:00:00.000
    clock.advance(timedelta(milliseconds=300))
    user.invalidate_tokens(clock.now())  # the mark from 12:00:00.400
    await deps.users.update(user)

    with pytest.raises(TokenRevokedError):
        _ = await deps.refresh()(refresh)


async def test_kill_switch_spares_a_relogin_after_the_marks_second() -> None:
    """A login in the next second after a mid-second mark passes."""
    clock = FrozenClock()
    deps = _Deps(issuer=FakeTokenIssuer(clock=clock))
    user = _user()

    clock.advance(timedelta(milliseconds=400))
    user.invalidate_tokens(clock.now())  # the mark from 12:00:00.400 is 12:00:01
    clock.advance(timedelta(milliseconds=700))  # 12:00:01.100
    _, refresh = await deps.session_for(user)  # iat = 12:00:01.000

    pair = await deps.refresh()(refresh)

    assert pair.access


# ── Logout ──────────────────────────────────────────────────────────────────


async def test_logout_revokes_both_presented_tokens() -> None:
    """The access token is revoked too, closing the window after logout."""
    deps = _Deps()
    access, refresh = await deps.session_for(_user())
    access_jti = deps.issuer.parse_access(access).jti
    refresh_jti = deps.issuer.parse_refresh(refresh).jti

    await deps.logout()(refresh, access)

    assert refresh_jti in deps.revocation.revoked
    assert access_jti in deps.revocation.revoked


async def test_logout_is_idempotent() -> None:
    """A second logout succeeds."""
    deps = _Deps()
    access, refresh = await deps.session_for(_user())
    logout = deps.logout()
    await logout(refresh, access)

    await logout(refresh, access)  # does not raise

    assert len(deps.revocation.revoked) == 2


async def test_logout_with_a_garbage_token_succeeds() -> None:
    """A garbage token succeeds and writes nothing."""
    deps = _Deps()

    await deps.logout()("not-a-token", "neither-is-this")

    assert deps.revocation.revoked == {}


async def test_logout_skips_a_token_with_no_life_left() -> None:
    """A token with no life left is not written."""
    deps = _Deps(issuer=FakeTokenIssuer(ttl_seconds=0))
    access, refresh = await deps.session_for(_user())

    await deps.logout()(refresh, access)

    assert deps.revocation.revoked == {}


async def test_logout_ignores_tokens_presented_in_the_wrong_slot() -> None:
    """Both arguments are checked for their type."""
    deps = _Deps()
    access, refresh = await deps.session_for(_user())

    await deps.logout()(access, refresh)

    assert deps.revocation.revoked == {}


async def test_logout_is_written_to_the_audit() -> None:
    """A logout goes to the audit like a login."""
    deps = _Deps()
    user = _user()
    _, refresh = await deps.session_for(user)

    await deps.logout()(refresh, None)

    assert [entry.action for entry in deps.audit.entries] == [AuditAction.LOGGED_OUT]
    assert deps.audit.entries[0].actor_id == user.id
    assert deps.uow.committed, "the audit entry was not committed"


async def test_garbage_token_logs_out_without_writing_an_audit_entry() -> None:
    """A garbage token revokes nothing and records nothing."""
    deps = _Deps()

    await deps.logout()("not-a-token", None)

    assert deps.audit.entries == []
    assert not deps.uow.committed


async def test_logout_does_not_happen_when_the_audit_write_fails() -> None:
    """No audit entry, no logout."""
    deps = _Deps()
    user = _user()
    access, refresh = await deps.session_for(user)
    logout = Logout(
        issuer=deps.issuer,
        revocation=deps.revocation,
        uow=deps.uow,
        audit=FailingAuditLog(),
    )

    with pytest.raises(AuditWriteFailedError):
        await logout(refresh, access)

    assert not deps.uow.committed
    assert deps.revocation.revoked == {}, "a token was revoked without an audit entry"


async def test_a_refresh_right_after_a_password_change_gets_a_working_pair() -> None:
    """A pair issued in the second of the mark is not void at birth."""
    clock = FrozenClock(NOW + timedelta(milliseconds=250))
    deps = _Deps(issuer=FakeTokenIssuer(clock=clock))
    user = _user()
    await deps.users.add(user)
    user.invalidate_tokens(clock.now())
    await deps.users.update(user)
    mark = user.tokens_invalidated_after
    assert mark is not None
    # The pair the change hands out carries the mark as its `iat`.
    _, refresh = deps.issuer.issue_pair(user.id, not_before=mark)

    pair = await deps.refresh()(refresh)

    assert deps.issuer.parse_access(pair.access).issued_at >= mark
