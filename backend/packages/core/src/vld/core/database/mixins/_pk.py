"""Миксины первичных ключей."""

from __future__ import annotations

import uuid

from sqlalchemy import BigInteger, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column


class UUIDPkMixin:
    """PK бизнес-сущности: uuid4, генерится приложением.

    Attributes:
        id: uuid.UUID - Первичный ключ.

    """

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=text("gen_random_uuid()"),
    )


class BigIntPkMixin:
    """PK append-only таблиц: логи, телеметрия, outbox.

    Attributes:
        id: int - Первичный ключ.

    """

    id: Mapped[int] = mapped_column(
        BigInteger,
        primary_key=True,
        autoincrement=True,
    )
