"""The auth HTTP layer on fakes: the wiring of production with fake ports."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from auth_fakes import (
    GOOD_PASSWORD,
    NOW,
    PASSWORD_SETTINGS,
    REQUIRE_VERIFIED,
    AllowAllLimiter,
    CountingLimiter,
    FakeAuditLog,
    FakeAuditQuery,
    FakeEmailSender,
    FakeHasher,
    FakeOutbox,
    FakeRefreshedPairCache,
    FakeRevocationStore,
    FakeTokenIssuer,
    FakeTokenRepository,
    FakeUnitOfWork,
    FakeUserRepository,
    FrozenClock,
    deliver_pending_password_resets,
    deliver_pending_verifications,
)
from dishka import Provider, Scope, make_async_container, provide
from dishka.integrations.fastapi import setup_dishka
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from pydantic import SecretStr

from vld.auth.api import AUTH_DOMAIN, AuthErrorResponse
from vld.auth.api.routers import ERROR_RESPONSES
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
from vld.auth.config import JwtSettings, PasswordSettings, VerificationSettings
from vld.auth.di import (
    AuthAccountUseCaseProvider,
    AuthAdministrationUseCaseProvider,
    AuthOnboardingUseCaseProvider,
    AuthPasswordUseCaseProvider,
    AuthSessionUseCaseProvider,
)
from vld.auth.domain import Profile, Role, User
from vld.auth.infrastructure import AuthIdentityProvider
from vld.core.audit import AuditLog, AuditQuery
from vld.core.config import CorsSettings
from vld.core.database import UnitOfWork
from vld.web.access import IdentityProvider
from vld.web.errors import COMMON_ERROR_RESPONSES, RequestIdMiddleware
from vld.web.mounting import mount

if TYPE_CHECKING:
    from httpx import Response

    from vld.web.mounting import DomainDescriptor

API_PREFIX = "/api/v1"
FRONTEND_ORIGIN = "http://localhost:5173"
REGISTRATION = {"email": "flow@b.co", "password": GOOD_PASSWORD, "role": "student"}
CREDENTIALS = {"email": "flow@b.co", "password": GOOD_PASSWORD}


@dataclass
class Deps:
    """Fakes a test reaches after the application is built."""

    clock: FrozenClock = field(default_factory=FrozenClock)
    users: FakeUserRepository = field(default_factory=FakeUserRepository)
    tokens: FakeTokenRepository = field(default_factory=FakeTokenRepository)
    hasher: FakeHasher = field(default_factory=FakeHasher)
    email: FakeEmailSender = field(default_factory=FakeEmailSender)
    outbox: FakeOutbox = field(default_factory=FakeOutbox)
    revocation: FakeRevocationStore = field(default_factory=FakeRevocationStore)
    refreshed: FakeRefreshedPairCache = field(default_factory=FakeRefreshedPairCache)
    limiter: CountingLimiter = field(default_factory=AllowAllLimiter)
    audit: FakeAuditLog = field(default_factory=FakeAuditLog)
    verification: VerificationSettings = REQUIRE_VERIFIED
    issuer: FakeTokenIssuer = field(init=False)

    def __post_init__(self) -> None:
        """Share the clock with the issuer."""
        self.issuer = FakeTokenIssuer(clock=self.clock)


class _FakeAdapters(Provider):
    """Fakes in place of the adapters; the use cases are built as in production."""

    def __init__(self, deps: Deps) -> None:
        super().__init__()
        self.deps: Deps = deps

    @provide(scope=Scope.APP)
    def users(self) -> UserRepository:
        """Give the account store."""
        return self.deps.users

    @provide(scope=Scope.APP)
    def tokens(self) -> TokenRepository:
        """Give the token store."""
        return self.deps.tokens

    @provide(scope=Scope.APP)
    def hasher(self) -> PasswordHasher:
        """Give the hasher."""
        return self.deps.hasher

    @provide(scope=Scope.APP)
    def email(self) -> EmailSender:
        """Give the sender."""
        return self.deps.email

    @provide(scope=Scope.APP)
    def clock(self) -> Clock:
        """Give the clock."""
        return self.deps.clock

    @provide(scope=Scope.APP)
    def outbox(self) -> Outbox:
        """Give the outbox."""
        return self.deps.outbox

    @provide(scope=Scope.APP)
    def issuer(self) -> TokenIssuer:
        """Give the issuer."""
        return self.deps.issuer

    @provide(scope=Scope.APP)
    def revocation(self) -> RevocationStore:
        """Give the revocation list."""
        return self.deps.revocation

    @provide(scope=Scope.APP)
    def refreshed(self) -> RefreshedPairCache:
        """Give the grace cache."""
        return self.deps.refreshed

    @provide(scope=Scope.APP)
    def limiter(self) -> RateLimiter:
        """Give the limiter."""
        return self.deps.limiter

    @provide(scope=Scope.APP)
    def audit(self) -> AuditLog:
        """Give the audit log."""
        return self.deps.audit

    @provide(scope=Scope.APP)
    def audit_query(self) -> AuditQuery:
        """Read the same entries the log writes."""
        return FakeAuditQuery(self.deps.audit)

    @provide(scope=Scope.APP)
    def jwt(self) -> JwtSettings:
        """Give token lifetimes for the cookies."""
        return JwtSettings(secret_key=SecretStr("s" * 64))

    @provide(scope=Scope.APP)
    def password(self) -> PasswordSettings:
        """Give the password rules."""
        return PASSWORD_SETTINGS

    @provide(scope=Scope.APP)
    def verification(self) -> VerificationSettings:
        """Give the confirmation rule."""
        return self.deps.verification

    @provide(scope=Scope.APP)
    def cors(self) -> CorsSettings:
        """Trust the frontend origin, as the Origin check reads it."""
        return CorsSettings(allowed_origins=[FRONTEND_ORIGIN])

    @provide(scope=Scope.APP)
    def identity(self) -> IdentityProvider:
        """Check access tokens with the production provider."""
        return AuthIdentityProvider(
            self.deps.issuer,
            self.deps.revocation,
            self.deps.users,
            self.deps.verification,
        )

    @provide(scope=Scope.REQUEST)
    def uow(self) -> UnitOfWork:
        """Give a fresh boundary per request."""
        return FakeUnitOfWork()


def build(
    deps: Deps | None = None,
    *extra: DomainDescriptor,
    prefix: str = "",
) -> tuple[FastAPI, Deps]:
    """Build the application with auth, and any extra domains, on fakes."""
    deps = deps or Deps()
    container = make_async_container(
        _FakeAdapters(deps),
        AuthOnboardingUseCaseProvider(),
        AuthSessionUseCaseProvider(),
        AuthPasswordUseCaseProvider(),
        AuthAccountUseCaseProvider(),
        AuthAdministrationUseCaseProvider(),
    )
    app = FastAPI()
    app.add_middleware(RequestIdMiddleware)
    mount(app, AUTH_DOMAIN, *extra, prefix=prefix)
    setup_dishka(container, app)
    return app, deps


def client_for(app: FastAPI, host: str = "testclient") -> AsyncClient:
    """Build a client over the ASGI application, from a given address."""
    return AsyncClient(
        transport=ASGITransport(app=app, client=(host, 12345)),
        base_url="http://test",
    )


def assert_error_contract(response: Response) -> None:
    """Check an error body against what OpenAPI declares."""
    declared = {**COMMON_ERROR_RESPONSES, **ERROR_RESPONSES}
    assert response.status_code in declared, (
        f"status {response.status_code} is declared neither by the router nor the platform"
    )
    _ = AuthErrorResponse.model_validate(response.json())
    assert response.headers["Cache-Control"] == "no-store"


async def deliver_outbox(deps: Deps) -> None:
    """Run the collected outbox through the handlers, as the worker would."""
    await deliver_pending_verifications(
        deps.outbox,
        deps.users,
        deps.tokens,
        deps.email,
        deps.clock,
    )
    await deliver_pending_password_resets(
        deps.outbox,
        deps.users,
        deps.tokens,
        deps.email,
        deps.clock,
    )


async def register_and_verify(client: AsyncClient, deps: Deps) -> None:
    """Register `flow@b.co` and follow the confirmation link."""
    response = await client.post("/auth/register", json=REGISTRATION)
    assert response.status_code == 201
    await deliver_outbox(deps)
    _, token = deps.email.sent[-1]
    confirmed = await client.post("/auth/verify-email", json={"token": token})
    assert confirmed.status_code == 204


async def seed(
    deps: Deps,
    email: str,
    *,
    role: Role = Role.STUDENT,
    is_admin: bool = False,
    is_active: bool = True,
) -> User:
    """Store a confirmed account whose password is `GOOD_PASSWORD`."""
    user = User(
        id=uuid.uuid4(),
        email=email,
        email_verified_at=NOW,
        password_hash=f"hashed:{GOOD_PASSWORD}",
        role=role,
        is_admin=is_admin,
        is_active=is_active,
        profile=Profile(),
    )
    await deps.users.add(user)
    return user


async def bearer(client: AsyncClient, email: str) -> dict[str, str]:
    """Log in by password and return the authorization header."""
    response = await client.post(
        "/auth/login",
        json={"email": email, "password": GOOD_PASSWORD},
    )
    assert response.status_code == 200, response.text
    client.cookies.clear()
    return {"Authorization": f"Bearer {response.json()['access']}"}
