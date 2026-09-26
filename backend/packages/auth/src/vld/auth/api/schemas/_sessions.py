"""Schemas of a session: login, refresh, logout."""

from __future__ import annotations

from pydantic import BaseModel, EmailStr, Field

from ._limits import MAX_EMAIL, MAX_JWT, MAX_PASSWORD


class LoginRequest(BaseModel):
    """Body of a login.

    Attributes:
        email: EmailStr - Address.
        password: str - Password.

    """

    email: EmailStr = Field(max_length=MAX_EMAIL)
    password: str = Field(min_length=1, max_length=MAX_PASSWORD)


class RefreshRequest(BaseModel):
    """Body of a refresh or a logout from a programmatic client.

    Attributes:
        refresh: str - Refresh token.

    """

    refresh: str = Field(min_length=1, max_length=MAX_JWT)


class TokenPairResponse(BaseModel):
    """Issued pair of tokens: the answer to a login, a refresh and a password change.

    Attributes:
        access: str - Access token.
        refresh: str - Refresh token.

    """

    access: str
    refresh: str


class SessionRefreshedResponse(BaseModel):
    """Answer to a refresh by cookie: the pair left as cookies, the body is empty."""
