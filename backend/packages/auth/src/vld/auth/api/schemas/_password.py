"""Schemas of a password: reset through a letter and change."""

from __future__ import annotations

from pydantic import BaseModel, EmailStr, Field

from ._limits import MAX_EMAIL, MAX_EMAIL_TOKEN, MAX_PASSWORD


class PasswordResetRequest(BaseModel):
    """Body of a request for a reset letter.

    Attributes:
        email: EmailStr - Address typed in the "forgot password" form.

    """

    email: EmailStr = Field(max_length=MAX_EMAIL)


class NewPasswordRequest(BaseModel):
    """Body of a reset through the link from a letter.

    Attributes:
        token: str - Token from the letter.
        password: str - New plain password.

    """

    token: str = Field(min_length=1, max_length=MAX_EMAIL_TOKEN)
    password: str = Field(min_length=1, max_length=MAX_PASSWORD)


class ChangePasswordRequest(BaseModel):
    """Body of a change while logged in.

    Attributes:
        current_password: str - Password the user has now.
        new_password: str - Password to set.

    """

    current_password: str = Field(min_length=1, max_length=MAX_PASSWORD)
    new_password: str = Field(min_length=1, max_length=MAX_PASSWORD)
