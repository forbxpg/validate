"""Schemas of the own account."""

from __future__ import annotations

import uuid

from pydantic import BaseModel

from vld.auth.domain import Role

from ._profile import ProfileBody


class MeResponse(BaseModel):
    """The logged-in user, for the header and the routing of the site.

    Attributes:
        user_id: uuid.UUID - Account.
        email: str - Address.
        email_verified: bool - Whether the address is confirmed.
        role: Role - Role.
        is_admin: bool - Admin rights.
        profile: ProfileBody - Personal details.

    """

    user_id: uuid.UUID
    email: str
    email_verified: bool
    role: Role
    is_admin: bool
    profile: ProfileBody
