"""Schemas of registration and address confirmation."""

from __future__ import annotations

from pydantic import BaseModel, EmailStr, Field

from vld.auth.domain import Role

from ._limits import MAX_EMAIL, MAX_EMAIL_TOKEN, MAX_PASSWORD
from ._profile import ProfileBody


class RegisterRequest(BaseModel):
    """Body of a registration.

    Attributes:
        email: EmailStr - Address.
        password: str - Plain password.
        role: Role - Role the user picks.
        profile: ProfileBody - Details given at registration.

    """

    email: EmailStr = Field(max_length=MAX_EMAIL)
    password: str = Field(min_length=1, max_length=MAX_PASSWORD)
    role: Role
    profile: ProfileBody = Field(default_factory=ProfileBody)


class RegisterResponse(BaseModel):
    """Answer to a registration.

    Attributes:
        user_id: str - Id of the new account.

    """

    user_id: str


class VerifyEmailRequest(BaseModel):
    """Body of an address confirmation.

    Attributes:
        token: str - Token from the letter.

    """

    token: str = Field(min_length=1, max_length=MAX_EMAIL_TOKEN)


class ResendVerificationRequest(BaseModel):
    """Body of a request for another confirmation letter.

    Attributes:
        email: EmailStr - Address to send it to.

    """

    email: EmailStr = Field(max_length=MAX_EMAIL)
