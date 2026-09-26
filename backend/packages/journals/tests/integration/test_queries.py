"""The four questions the prototype answered about the VAK list, asked of the schema."""

from __future__ import annotations

from datetime import date
from typing import TYPE_CHECKING

import pytest
from journals_rows import journal, listing, publish, snapshot, speciality
from sqlalchemy import Select, and_, exists, func, or_, select

from vld.journals.infrastructure.models import (
    JournalIssnModel,
    SpecialityModel,
    VakCurrentModel,
    VakGroupModel,
    VakGroupSpecialityModel,
    VakListingIssnModel,
    VakListingModel,
)
from vld.vak.models import ScienceBranch

if TYPE_CHECKING:
    import uuid

    from sqlalchemy.ext.asyncio import AsyncConnection

pytestmark = pytest.mark.integration

_CURRENT = select(VakCurrentModel.snapshot_id).scalar_subquery()


class _Registry:
    """Two editions of three journals.

    A is in both. B, a series of «Вестник МГУ», only in the old one. C, another
    series, only in the current one; it prints the shared ISSN `0201-7385`, which the
    moderator gave to A. The old edition prints «5.9.5» under an old name twice, the
    current one under the new name once, and prints «5.9.5» once with no branch.
    """

    def __init__(self) -> None:
        self.philology: uuid.UUID
        self.philology_unread: uuid.UUID
        self.history: uuid.UUID
        self.a: uuid.UUID
        self.b: uuid.UUID
        self.c: uuid.UUID


async def _registry(connection: AsyncConnection) -> _Registry:
    registry = _Registry()
    registry.philology = await speciality(connection, "5.9.5", ScienceBranch.PHILOLOGY)
    registry.philology_unread = await speciality(connection, "5.9.5", None)
    registry.history = await speciality(connection, "5.6.1", ScienceBranch.HISTORY)
    registry.a = await journal(connection, "2587-7534", "0201-7385")
    registry.b = await journal(connection, "0130-0113")
    registry.c = await journal(connection, "0320-8095")
    old = await snapshot(connection, date(2026, 3, 30), "old")
    new = await snapshot(connection, date(2026, 9, 15), "new")
    old_name = (registry.philology, "Русский язык и литература")
    new_name = (registry.philology, "Русский язык. Языки народов России")
    history = (registry.history, "Отечественная история")
    _ = await listing(
        connection,
        snapshot_id=old,
        journal_id=registry.a,
        number=1,
        title="Abyss",
        issns=("2587-7534",),
        groups=((date(2022, 2, 1), None, (old_name, history)),),
    )
    _ = await listing(
        connection,
        snapshot_id=old,
        journal_id=registry.b,
        number=2,
        title="Вестник МГУ. Серия 11. Право",
        issns=("0201-7385", "0130-0113"),
        groups=((date(2019, 3, 26), None, (old_name, history)),),
    )
    _ = await listing(
        connection,
        snapshot_id=new,
        journal_id=registry.a,
        number=1,
        title="Abyss",
        issns=("2587-7534", "0201-7385"),
        groups=(
            (date(2018, 12, 28), date(2022, 10, 16), (history,)),
            (date(2022, 2, 1), None, (new_name,)),
        ),
    )
    _ = await listing(
        connection,
        snapshot_id=new,
        journal_id=registry.c,
        number=2,
        title="Вестник МГУ. Серия 13. Востоковедение",
        issns=("0201-7385", "0320-8095"),
        groups=(
            (date(2022, 2, 1), None, ((registry.philology_unread, "Языки"), history)),
        ),
    )
    await publish(connection, old)
    await publish(connection, new)
    return registry


def _listings(
    title: str | None = None,
    issn: str | None = None,
) -> Select[int, str]:
    query = (
        select(VakListingModel.number, VakListingModel.title_main)
        .where(VakListingModel.snapshot_id == _CURRENT)
        .order_by(VakListingModel.number)
    )
    if title is not None:
        query = query.where(VakListingModel.title_main.ilike(f"%{title}%"))
    if issn is not None:
        query = query.where(
            exists().where(
                VakListingIssnModel.listing_id == VakListingModel.id,
                VakListingIssnModel.issn == issn,
            ),
        )
    return query


async def test_the_list_is_the_current_edition(owner: AsyncConnection) -> None:
    """Question 1: journals of the current snapshot by number; B left the list."""
    _ = await _registry(owner)
    series = (2, "Вестник МГУ. Серия 13. Востоковедение")

    assert (await owner.execute(_listings())).all() == [(1, "Abyss"), series]
    assert (await owner.execute(_listings(title="aby"))).all() == [(1, "Abyss")]
    assert (await owner.execute(_listings(issn="0201-7385"))).all() == [
        (1, "Abyss"),
        series,
    ]
    assert (await owner.execute(_listings(issn="0130-0113"))).all() == []


async def test_a_journal_by_issn_with_its_specialities(owner: AsyncConnection) -> None:
    """Question 2: the journal a moderator gave a shared ISSN to, not every printer."""
    registry = await _registry(owner)
    query = (
        select(
            VakListingModel.journal_id,
            VakGroupModel.included,
            VakGroupModel.excluded,
            SpecialityModel.code,
        )
        .join(
            JournalIssnModel,
            JournalIssnModel.journal_id == VakListingModel.journal_id,
        )
        .join(VakGroupModel, VakGroupModel.listing_id == VakListingModel.id)
        .join(
            VakGroupSpecialityModel,
            VakGroupSpecialityModel.group_id == VakGroupModel.id,
        )
        .join(
            SpecialityModel,
            SpecialityModel.id == VakGroupSpecialityModel.speciality_id,
        )
        .where(
            JournalIssnModel.issn == "0201-7385",
            VakListingModel.snapshot_id == _CURRENT,
        )
        .order_by(VakGroupModel.position)
    )

    assert (await owner.execute(query)).all() == [
        (registry.a, date(2018, 12, 28), date(2022, 10, 16), "5.6.1"),
        (registry.a, date(2022, 2, 1), None, "5.9.5"),
    ]


async def test_specialities_take_their_name_from_the_current_edition(
    owner: AsyncConnection,
) -> None:
    """Question 3: per speciality, the name printed most often in the current snapshot."""
    _ = await _registry(owner)
    names = (
        select(
            SpecialityModel.code,
            SpecialityModel.branch,
            func.mode().within_group(VakGroupSpecialityModel.name_printed),
        )
        .join(
            VakGroupSpecialityModel,
            VakGroupSpecialityModel.speciality_id == SpecialityModel.id,
        )
        .join(VakGroupModel, VakGroupModel.id == VakGroupSpecialityModel.group_id)
        .join(VakListingModel, VakListingModel.id == VakGroupModel.listing_id)
        .where(VakListingModel.snapshot_id == _CURRENT)
        .group_by(SpecialityModel.id)
        .order_by(SpecialityModel.code, SpecialityModel.branch)
    )

    assert (await owner.execute(names)).all() == [
        ("5.6.1", ScienceBranch.HISTORY, "Отечественная история"),
        ("5.9.5", ScienceBranch.PHILOLOGY, "Русский язык. Языки народов России"),
        ("5.9.5", None, "Языки"),
    ]


async def _listed_on(
    connection: AsyncConnection,
    journal_id: uuid.UUID,
    speciality_id: uuid.UUID,
    day: date,
) -> bool | None:
    query = select(
        exists().where(
            VakListingModel.snapshot_id == _CURRENT,
            VakListingModel.journal_id == journal_id,
            VakGroupModel.listing_id == VakListingModel.id,
            VakGroupSpecialityModel.group_id == VakGroupModel.id,
            VakGroupSpecialityModel.speciality_id == speciality_id,
            and_(
                VakGroupModel.included <= day,
                or_(VakGroupModel.excluded.is_(None), VakGroupModel.excluded >= day),
            ),
        ),
    )
    return await connection.scalar(query)


async def test_was_a_journal_listed_for_a_speciality_on_a_day(
    owner: AsyncConnection,
) -> None:
    """Question 4: the dates of the group decide, in the current snapshot."""
    registry = await _registry(owner)

    assert await _listed_on(owner, registry.a, registry.philology, date(2023, 5, 10))
    assert not await _listed_on(
        owner,
        registry.a,
        registry.philology,
        date(2021, 5, 10),
    )
    assert await _listed_on(owner, registry.a, registry.history, date(2020, 5, 10))
    assert not await _listed_on(owner, registry.a, registry.history, date(2023, 5, 10))
    assert not await _listed_on(owner, registry.b, registry.history, date(2023, 5, 10))
