"""JWT issuer: claims, types, expiry, the session ceiling, forgeries."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

import jwt
import pytest
from auth_fakes import FrozenClock
from pydantic import SecretStr, ValidationError

from vld.auth.config import JwtSettings
from vld.auth.infrastructure import JwtTokenIssuer, SystemClock

_SECRET = "s" * 32


def _settings(**overrides: object) -> JwtSettings:
    return JwtSettings(secret_key=SecretStr(_SECRET), **overrides)  # pyright: ignore[reportArgumentType]


def _forge(
    claims: dict[str, object],
    *,
    key: str = _SECRET,
    algorithm: str = "HS256",
) -> str:
    base: dict[str, object] = {
        "sub": str(uuid.uuid4()),
        "jti": uuid.uuid4().hex,
        "iat": datetime.now(UTC),
        "exp": datetime.now(UTC) + timedelta(hours=1),
    }
    return jwt.encode({**base, **claims}, key, algorithm=algorithm)


def test_issued_pair_is_parseable() -> None:
    """A refresh token parses back into its claims."""
    issuer = JwtTokenIssuer(_settings(session_expires_days=7))
    user_id = uuid.uuid4()

    _access, refresh = issuer.issue_pair(user_id)
    claims = issuer.parse_refresh(refresh)

    assert claims.user_id == user_id
    assert claims.jti
    assert claims.session_exp == claims.issued_at + timedelta(days=7)


def test_not_before_moves_the_issue_time_forward() -> None:
    """A pair issued in the second of an invalidation carries the mark as `iat`."""
    # PyJWT checks `iat` against the real clock, so stay near it.
    now = datetime.now(UTC).replace(microsecond=250_000)
    issuer = JwtTokenIssuer(_settings(), clock=FrozenClock(now))
    mark = now.replace(microsecond=0) + timedelta(seconds=1)

    access, refresh = issuer.issue_pair(uuid.uuid4(), not_before=mark)

    assert issuer.parse_access(access).issued_at == mark
    assert issuer.parse_refresh(refresh).issued_at == mark


def test_access_token_is_not_accepted_as_refresh() -> None:
    """An access token lacks `session_exp` and does not pass as refresh."""
    issuer = JwtTokenIssuer(_settings())
    access, _refresh = issuer.issue_pair(uuid.uuid4())

    with pytest.raises(ValueError, match="invalid token") as caught:
        _ = issuer.parse_refresh(access)

    assert isinstance(caught.value.__cause__, jwt.MissingRequiredClaimError)


def test_device_marker_round_trips_and_rejects_a_refresh() -> None:
    """The device marker is bound to its account and checked for its type."""
    issuer = JwtTokenIssuer(_settings())
    user_id = uuid.uuid4()

    marker = issuer.issue_device(user_id)

    claims = issuer.parse_device(marker)
    assert claims.user_id == user_id
    # The kill switch compares whole seconds.
    assert claims.issued_at.timestamp() == int(claims.issued_at.timestamp())
    assert issuer.remaining_ttl_seconds(marker) > 364 * 24 * 3600
    _access, refresh = issuer.issue_pair(user_id)
    with pytest.raises(ValueError, match="unexpected token type"):
        _ = issuer.parse_device(refresh)


def test_refresh_with_wrong_typ_is_rejected() -> None:
    """A token typed `access` with a ceiling in place is refused by its type."""
    issuer = JwtTokenIssuer(_settings())
    ceiling = int((datetime.now(UTC) + timedelta(days=90)).timestamp())
    forged = _forge({"typ": "access", "session_exp": ceiling})

    with pytest.raises(ValueError, match="token type"):
        _ = issuer.parse_refresh(forged)


@pytest.mark.parametrize("missing", ["exp", "session_exp"])
def test_a_refresh_without_a_required_claim_is_rejected(missing: str) -> None:
    """A refresh token without `exp` or `session_exp` is refused."""
    issuer = JwtTokenIssuer(_settings())
    ceiling = int((datetime.now(UTC) + timedelta(days=90)).timestamp())
    claims: dict[str, object] = {"typ": "refresh", "session_exp": ceiling}
    token = jwt.decode(
        _forge(claims),
        _SECRET,
        algorithms=["HS256"],
    )
    del token[missing]
    forged = jwt.encode(token, _SECRET, algorithm="HS256")

    with pytest.raises(ValueError, match="invalid token") as caught:
        _ = issuer.parse_refresh(forged)

    assert isinstance(caught.value.__cause__, jwt.MissingRequiredClaimError)


def test_expired_token_is_rejected() -> None:
    """A token issued a year ago is refused by its `exp`."""
    past = datetime.now(UTC) - timedelta(days=365)
    issuer = JwtTokenIssuer(_settings(), clock=FrozenClock(past))
    _access, refresh = issuer.issue_pair(uuid.uuid4())

    with pytest.raises(ValueError, match="invalid token") as caught:
        _ = JwtTokenIssuer(_settings()).parse_refresh(refresh)

    assert isinstance(caught.value.__cause__, jwt.ExpiredSignatureError)


def test_algorithm_none_is_rejected() -> None:
    """An unsigned token is refused."""
    issuer = JwtTokenIssuer(_settings())
    forged = _forge({"typ": "refresh"}, key="", algorithm="none")

    with pytest.raises(ValueError, match="invalid token"):
        _ = issuer.parse_refresh(forged)


def test_tampered_payload_is_rejected() -> None:
    """A changed payload fails the signature check."""
    issuer = JwtTokenIssuer(_settings())
    _access, refresh = issuer.issue_pair(uuid.uuid4())
    header, payload, signature = refresh.split(".")

    with pytest.raises(ValueError, match="invalid token"):
        _ = issuer.parse_refresh(f"{header}.{payload[:-2]}AA.{signature}")


def test_a_short_secret_is_refused_by_the_settings_and_the_issuer() -> None:
    """A secret under 256 bits never signs a token (RFC 7518, section 3.2)."""
    with pytest.raises(ValidationError, match="at least 32 bytes"):
        _ = JwtSettings(secret_key=SecretStr("short"))
    # Settings built in code skip validation; the issuer checks again.
    unchecked = JwtSettings.model_construct(secret_key=SecretStr("short"))

    with pytest.raises(ValueError, match="256 bits"):
        _ = JwtTokenIssuer(unchecked)


def test_remaining_ttl_comes_from_token_not_settings() -> None:
    """The remaining life is read from the token, not from the current settings."""
    issued = JwtTokenIssuer(_settings(refresh_token_expires_minutes=60))
    _access, refresh = issued.issue_pair(uuid.uuid4())

    shortened = JwtTokenIssuer(_settings(refresh_token_expires_minutes=1))

    assert shortened.remaining_ttl_seconds(refresh) > 3000


def test_session_exp_survives_rotation_unchanged() -> None:
    """Rotation carries `session_exp` over to the second."""
    clock = FrozenClock(datetime.now(UTC) - timedelta(days=29))
    issuer = JwtTokenIssuer(_settings(), clock=clock)
    _access, refresh = issuer.issue_pair(uuid.uuid4())
    first = issuer.parse_refresh(refresh)

    clock.advance(timedelta(days=29))
    _access, rotated = issuer.issue_pair(first.user_id, session_exp=first.session_exp)

    assert issuer.parse_refresh(rotated).session_exp == first.session_exp


def test_refresh_exp_is_capped_by_the_session_ceiling() -> None:
    """The refresh `exp` is `min(now + refresh lifetime, session_exp)`."""
    issuer = JwtTokenIssuer(_settings())
    ceiling = datetime.now(UTC) + timedelta(days=5)

    _access, refresh = issuer.issue_pair(uuid.uuid4(), session_exp=ceiling)

    payload = jwt.decode(refresh, _SECRET, algorithms=["HS256"])
    assert payload["exp"] == payload["session_exp"] == int(ceiling.timestamp())


def test_refresh_beyond_the_session_ceiling_is_rejected() -> None:
    """A refresh past the ceiling fails the usual `exp` check."""
    issuer = JwtTokenIssuer(_settings())
    _access, refresh = issuer.issue_pair(
        uuid.uuid4(),
        session_exp=datetime.now(UTC) - timedelta(hours=1),
    )

    with pytest.raises(ValueError, match="invalid token") as caught:
        _ = issuer.parse_refresh(refresh)

    assert isinstance(caught.value.__cause__, jwt.ExpiredSignatureError)


def test_system_clock_is_utc_aware() -> None:
    """The clock gives aware UTC moments, never naive ones."""
    assert SystemClock.now().tzinfo is UTC
