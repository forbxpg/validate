"""Endpoints of the own account: who am I and the profile."""

from __future__ import annotations

from dishka.integrations.fastapi import DishkaRoute, FromDishka
from fastapi import APIRouter, Request, Response

from vld.auth.api.schemas import MeResponse, ProfileBody
from vld.auth.application import DescribeMe, UpdateProfile
from vld.web.access import authenticated, current_identity

router = APIRouter(route_class=DishkaRoute, tags=["account"])

_ME_SUMMARY = "Get the details of the logged-in user."
_UPDATE_PROFILE_SUMMARY = "Replace the personal details of the logged-in user."


@router.get(
    "/me",
    response_model=MeResponse,
    dependencies=[authenticated()],
    summary=_ME_SUMMARY,
)
async def me(
    request: Request,
    response: Response,
    use_case: FromDishka[DescribeMe],
) -> MeResponse:
    """Describe the logged-in user.

    Args:
        request: Request - Request, the identity comes from it.
        response: Response - Response, caching of which is forbidden.
        use_case: DescribeMe - The use case.

    Returns:
        MeResponse - Account, role, rights and profile.

    """
    view = await use_case(current_identity(request).user_id)
    response.headers["Cache-Control"] = "no-store"
    return MeResponse(
        user_id=view.user_id,
        email=view.email,
        email_verified=view.email_verified,
        role=view.role,
        is_admin=view.is_admin,
        profile=ProfileBody.model_validate(view.profile),
    )


@router.put(
    "/me/profile",
    response_model=ProfileBody,
    dependencies=[authenticated()],
    summary=_UPDATE_PROFILE_SUMMARY,
)
async def update_profile(
    body: ProfileBody,
    request: Request,
    use_case: FromDishka[UpdateProfile],
) -> ProfileBody:
    """Replace the personal details of the logged-in user.

    Args:
        body: ProfileBody - New details; an omitted field is cleared.
        request: Request - Request, the identity comes from it.
        use_case: UpdateProfile - The use case.

    Returns:
        ProfileBody - The stored details.

    """
    profile = await use_case(current_identity(request).user_id, body.to_domain())
    return ProfileBody.model_validate(profile)
