"""Endpoint of reading the audit log."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Annotated, cast

from dishka.integrations.fastapi import DishkaRoute, FromDishka
from fastapi import APIRouter, Depends
from fastapi_pagination import create_page
from fastapi_pagination.bases import AbstractParams

from vld.auth.api.schemas import AuditRecordResponse
from vld.auth.application import ReadAudit
from vld.core.pagination import Page
from vld.web.access import admin
from vld.web.pagination import TablePage

from ._common import ERROR_RESPONSES

router = APIRouter(
    prefix="/admin/audit",
    tags=["admin"],
    responses=ERROR_RESPONSES,
    route_class=DishkaRoute,
)


_READ_AUDIT_SUMMARY = "Read the audit log."


@router.get(
    "",
    response_model=TablePage[AuditRecordResponse],
    dependencies=[admin()],
    summary=_READ_AUDIT_SUMMARY,
)
async def read_audit(  # ruff: ignore[too-many-arguments, too-many-positional-arguments] -- query filters
    use_case: FromDishka[ReadAudit],
    params: Annotated[
        AbstractParams,
        Depends(
            TablePage.__params_type__,  # pyright: ignore[reportAttributeAccessIssue, reportUnknownArgumentType, reportUnknownMemberType]
        ),
    ],
    actor_id: uuid.UUID | None = None,
    target_id: uuid.UUID | None = None,
    occurred_from: datetime | None = None,
    occurred_to: datetime | None = None,
) -> Page[AuditRecordResponse]:
    """Return a page of the audit log, newest first.

    Args:
        use_case: ReadAudit - The use case.
        params: AbstractParams - Bounds of the page.
        actor_id: uuid.UUID | None - Actor filter; none means any.
        target_id: uuid.UUID | None - Target filter; none means any.
        occurred_from: datetime | None - Lower bound, inclusive.
        occurred_to: datetime | None - Upper bound, exclusive.

    Returns:
        Page[AuditRecordResponse] - The page and the number of matching records.

    """
    raw = params.to_raw_params().as_limit_offset()
    page = await use_case(
        actor_id=actor_id,
        target_id=target_id,
        occurred_from=occurred_from,
        occurred_to=occurred_to,
        limit=cast("int", raw.limit),
        offset=cast("int", raw.offset),
    )
    return create_page(  # pyright: ignore[reportReturnType]
        [
            AuditRecordResponse(
                id=record.id,
                occurred_at=record.occurred_at,
                action=record.action,
                actor_id=record.actor_id,
                target_id=record.target_id,
                payload=record.payload,
            )
            for record in page.records
        ],
        total=page.total,
        params=params,
    )
