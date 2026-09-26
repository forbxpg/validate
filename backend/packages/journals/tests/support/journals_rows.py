"""Rows of the journals schema built by hand, as a test needs them."""

from __future__ import annotations

import hashlib
from datetime import UTC, date, datetime
from typing import TYPE_CHECKING

from sqlalchemy import insert, select, update

from vld.journals.domain import Channel, DocumentSource, IssnSource, PublicationKind
from vld.journals.infrastructure.models import (
    JournalIssnModel,
    JournalModel,
    SpecialityModel,
    VakCurrentModel,
    VakDocumentModel,
    VakGroupModel,
    VakGroupSpecialityModel,
    VakListingIssnModel,
    VakListingModel,
    VakPublicationModel,
    VakSnapshotModel,
)

if TYPE_CHECKING:
    import uuid

    from sqlalchemy.ext.asyncio import AsyncConnection

    from vld.vak.models import ScienceBranch

OPERATOR = "deploy@validate"


async def journal(connection: AsyncConnection, *issns: str) -> uuid.UUID:
    """Add a journal and give it the ISSNs.

    Args:
        connection: AsyncConnection - Where.
        *issns: str - Its ISSNs.

    Returns:
        uuid.UUID - The journal.

    """
    journal_id = await connection.scalar(
        insert(JournalModel).returning(JournalModel.id),
    )
    assert journal_id is not None
    for issn in issns:
        _ = await connection.execute(
            insert(JournalIssnModel).values(
                issn=issn,
                journal_id=journal_id,
                source=IssnSource.IMPORT,
                assigned_by=OPERATOR,
            ),
        )
    return journal_id


async def speciality(
    connection: AsyncConnection,
    code: str,
    branch: ScienceBranch | None,
) -> uuid.UUID:
    """Add a speciality.

    Args:
        connection: AsyncConnection - Where.
        code: str - Its code.
        branch: ScienceBranch | None - Its branch.

    Returns:
        uuid.UUID - The speciality.

    """
    speciality_id = await connection.scalar(
        insert(SpecialityModel)
        .values(code=code, branch=branch)
        .returning(SpecialityModel.id),
    )
    assert speciality_id is not None
    return speciality_id


async def snapshot(connection: AsyncConnection, edition: date, name: str) -> uuid.UUID:
    """Add a document and a draft snapshot of it.

    Args:
        connection: AsyncConnection - Where.
        edition: date - The edition date.
        name: str - Makes the document unique.

    Returns:
        uuid.UUID - The snapshot.

    """
    document_id = await connection.scalar(
        insert(VakDocumentModel)
        .values(
            sha256=hashlib.sha256(name.encode()).digest(),
            size=10_607_798,
            source=DocumentSource.FILE,
            file_name=f"{name}.pdf",
            fetched_at=datetime.now(UTC),
        )
        .returning(VakDocumentModel.id),
    )
    snapshot_id = await connection.scalar(
        insert(VakSnapshotModel)
        .values(
            document_id=document_id,
            parser_version="0.1.1",
            edition_date=edition,
            channel=Channel.CLI,
            operator=OPERATOR,
        )
        .returning(VakSnapshotModel.id),
    )
    assert snapshot_id is not None
    return snapshot_id


async def listing(  # ruff: ignore[too-many-arguments] -- one entry, every part named
    connection: AsyncConnection,
    *,
    snapshot_id: uuid.UUID,
    journal_id: uuid.UUID,
    number: int,
    title: str,
    issns: tuple[str, ...],
    groups: tuple[
        tuple[date | None, date | None, tuple[tuple[uuid.UUID, str], ...]],
        ...,
    ],
) -> int:
    """Add an entry of an edition with its ISSNs and speciality groups.

    Args:
        connection: AsyncConnection - Where.
        snapshot_id: uuid.UUID - The edition.
        journal_id: uuid.UUID - The journal.
        number: int - «№ п/п».
        title: str - The title.
        issns: tuple[str, ...] - ISSNs as printed.
        groups: tuple[...] - Per group: «с», «по» and the specialities with the
            name this row prints for each.

    Returns:
        int - The entry.

    """
    listing_id = await connection.scalar(
        insert(VakListingModel)
        .values(
            snapshot_id=snapshot_id,
            journal_id=journal_id,
            number=number,
            first_page=number,
            last_page=number,
            title_printed=title,
            title_main=title,
            issn_printed=" ".join(issns),
        )
        .returning(VakListingModel.id),
    )
    assert listing_id is not None
    for position, issn in enumerate(issns, start=1):
        _ = await connection.execute(
            insert(VakListingIssnModel).values(
                listing_id=listing_id,
                position=position,
                issn=issn,
            ),
        )
    for position, (included, excluded, specialities) in enumerate(groups, start=1):
        group_id = await connection.scalar(
            insert(VakGroupModel)
            .values(
                listing_id=listing_id,
                position=position,
                dates_printed="as printed",
                included=included,
                excluded=excluded,
            )
            .returning(VakGroupModel.id),
        )
        for place, (speciality_id, name) in enumerate(specialities, start=1):
            _ = await connection.execute(
                insert(VakGroupSpecialityModel).values(
                    group_id=group_id,
                    position=place,
                    speciality_id=speciality_id,
                    name_printed=name,
                    printed=f"printed {name}",
                ),
            )
    return listing_id


async def publish(connection: AsyncConnection, snapshot_id: uuid.UUID) -> None:
    """Publish a snapshot: a log row and the pointer, as the importer will.

    Args:
        connection: AsyncConnection - Where.
        snapshot_id: uuid.UUID - The snapshot.

    """
    current = await connection.scalar(
        select(VakCurrentModel.snapshot_id).with_for_update(),
    )
    _ = await connection.execute(
        insert(VakPublicationModel).values(
            kind=PublicationKind.PUBLISH,
            from_snapshot_id=current,
            to_snapshot_id=snapshot_id,
            forced=False,
            channel=Channel.CLI,
            operator=OPERATOR,
        ),
    )
    if current is None:
        _ = await connection.execute(
            insert(VakCurrentModel).values(snapshot_id=snapshot_id),
        )
    else:
        _ = await connection.execute(
            update(VakCurrentModel).values(snapshot_id=snapshot_id),
        )
