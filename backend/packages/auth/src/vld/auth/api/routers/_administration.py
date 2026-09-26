"""Endpoints of the administration of accounts."""

from __future__ import annotations

import uuid
from typing import Annotated, cast

from dishka.integrations.fastapi import DishkaRoute, FromDishka
from fastapi import APIRouter, Depends, Request
from fastapi_pagination import create_page
from fastapi_pagination.bases import AbstractParams

from vld.auth.api.schemas import (
    AdminUserResponse,
    ChangeRoleRequest,
    ProfileBody,
    SetActiveRequest,
)
from vld.auth.application import ChangeUserRole, GetUser, ListUsers, SetUserActive
from vld.auth.domain import Role, User
from vld.core.pagination import Page
from vld.web.access import admin, current_identity
from vld.web.pagination import TablePage

from ._common import ERROR_RESPONSES

router = APIRouter(
    prefix="/admin/users",
    tags=["admin"],
    responses=ERROR_RESPONSES,
    route_class=DishkaRoute,
)


_LIST_USERS_SUMMARY = "List user accounts."
_GET_USER_SUMMARY = "Get the card of an account."
_SET_USER_ACTIVE_SUMMARY = "Turn an account off, ending its sessions, or back on."
_SET_USER_ROLE_SUMMARY = "Change the role of an account."


def _card(user: User) -> AdminUserResponse:
    """Build the admin card of an account.

    Args:
        user: User - The account.

    Returns:
        AdminUserResponse - The card.

    """
    return AdminUserResponse(
        id=user.id,
        email=user.email,
        email_verified=user.email_verified,
        role=user.role,
        is_admin=user.is_admin,
        is_active=user.is_active,
        profile=ProfileBody.model_validate(user.profile),
    )


@router.get(
    "",
    response_model=TablePage[AdminUserResponse],
    dependencies=[admin()],
    summary=_LIST_USERS_SUMMARY,
)
async def list_users(
    use_case: FromDishka[ListUsers],
    params: Annotated[
        AbstractParams,
        Depends(
            TablePage.__params_type__,  # pyright: ignore[reportUnknownMemberType, reportUnknownArgumentType, reportAttributeAccessIssue]
        ),
    ],
    role: Role | None = None,
    is_active: bool | None = None,  # ruff: ignore[boolean-type-hint-positional-argument] -- a query parameter
) -> Page[AdminUserResponse]:
    """Return a page of accounts.

    Args:
        use_case: ListUsers - The use case.
        params: AbstractParams - Bounds of the page.
        role: Role | None - Role filter; none means any.
        is_active: bool | None - Access filter; none means any.

    Returns:
        Page[AdminUserResponse] - The page and the number of matching accounts.

    """
    raw = params.to_raw_params().as_limit_offset()
    page = await use_case(
        role=role,
        is_active=is_active,
        limit=cast("int", raw.limit),
        offset=cast("int", raw.offset),
    )
    return create_page(  # pyright: ignore[reportReturnType]
        [_card(user) for user in page.users],
        total=page.total,
        params=params,
    )


@router.get(
    "/{user_id}",
    response_model=AdminUserResponse,
    dependencies=[admin()],
    summary=_GET_USER_SUMMARY,
)
async def get_user(
    user_id: uuid.UUID,
    use_case: FromDishka[GetUser],
) -> AdminUserResponse:
    """Return the card of an account.

    Args:
        user_id: uuid.UUID - Id of the account.
        use_case: GetUser - The use case.

    Returns:
        AdminUserResponse - The card.

    """
    return _card(await use_case(user_id))


@router.put(
    "/{user_id}/active",
    response_model=AdminUserResponse,
    dependencies=[admin()],
    summary=_SET_USER_ACTIVE_SUMMARY,
)
async def set_user_active(
    user_id: uuid.UUID,
    body: SetActiveRequest,
    request: Request,
    use_case: FromDishka[SetUserActive],
) -> AdminUserResponse:
    """Turn an account off, ending its sessions, or back on.

    Args:
        user_id: uuid.UUID - The account.
        body: SetActiveRequest - Wanted state.
        request: Request - Request, the identity of the admin comes from it.
        use_case: SetUserActive - The use case.

    Returns:
        AdminUserResponse - The card after the change.

    """
    user = await use_case(
        user_id,
        active=body.is_active,
        actor_id=current_identity(request).user_id,
    )
    return _card(user)


@router.put(
    "/{user_id}/role",
    response_model=AdminUserResponse,
    dependencies=[admin()],
    summary=_SET_USER_ROLE_SUMMARY,
)
async def change_role(
    user_id: uuid.UUID,
    body: ChangeRoleRequest,
    request: Request,
    use_case: FromDishka[ChangeUserRole],
) -> AdminUserResponse:
    """Change the role of an account.

    Args:
        user_id: uuid.UUID - The account.
        body: ChangeRoleRequest - New role.
        request: Request - Request, the identity of the admin comes from it.
        use_case: ChangeUserRole - The use case.

    Returns:
        AdminUserResponse - The card after the change.

    """
    return _card(await use_case(current_identity(request).user_id, user_id, body.role))
