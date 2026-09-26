"""Outbox tables the relay reads."""

from __future__ import annotations

from dataclasses import dataclass

from vld.auth.infrastructure.models import CLAIMABLE_PREDICATE as AUTH_CLAIMABLE
from vld.auth.infrastructure.models import QUALIFIED_OUTBOX as AUTH_OUTBOX_NAME
from vld.auth.infrastructure.models import OutboxModel as AuthOutboxModel
from vld.auth.infrastructure.models import OutboxStatus as AuthOutboxStatus

# Every domain keeps its outbox in its own schema; a union of their models goes here.
type OutboxTable = type[AuthOutboxModel]


@dataclass(frozen=True, slots=True)
class OutboxSource:
    """One outbox table: where its rows are and how their outcome is marked.

    Attributes:
        name: str - Table with its schema, for the logs.
        model: OutboxTable - ORM model of a row.
        claimable: str - Predicate of a row ready to be claimed.
        pending: str - Status "waits to be published".
        sending: str - Status "claimed, being published".
        sent: str - Status "published", not "delivered".
        failed: str - Status "cannot be published".

    """

    name: str
    model: OutboxTable
    claimable: str
    pending: str
    sending: str
    sent: str
    failed: str


AUTH_OUTBOX = OutboxSource(
    name=AUTH_OUTBOX_NAME,
    model=AuthOutboxModel,
    claimable=AUTH_CLAIMABLE,
    pending=AuthOutboxStatus.PENDING,
    sending=AuthOutboxStatus.SENDING,
    sent=AuthOutboxStatus.SENT,
    failed=AuthOutboxStatus.FAILED,
)

SOURCES: tuple[OutboxSource, ...] = (AUTH_OUTBOX,)
