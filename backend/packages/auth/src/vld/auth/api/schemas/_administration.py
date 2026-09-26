"""Schemas of the administration of accounts."""

from __future__ import annotations

import uuid

from pydantic import BaseModel

from vld.auth.domain import Role

from ._profile import ProfileBody


class AdminUserResponse(BaseModel):
    """An account as an admin sees it.

    Attributes:
        id: uuid.UUID - Id.
        email: str - Address.
        email_verified: bool - Whether the address is confirmed.
        role: Role - Role.
        is_admin: bool - Admin rights.
        is_active: bool - Whether the account may log in.
        profile: ProfileBody - Personal details.

    """

    id: uuid.UUID
    email: str
    email_verified: bool
    role: Role
    is_admin: bool
    is_active: bool
    profile: ProfileBody


class ChangeRoleRequest(BaseModel):
    """Body of a role change.

    Attributes:
        role: Role - New role.

    """

    role: Role


class SetActiveRequest(BaseModel):
    """Body of turning an account off or on.

    Attributes:
        is_active: bool - Whether the account may log in.

    """

    is_active: bool
