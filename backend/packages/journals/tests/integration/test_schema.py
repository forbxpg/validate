"""The journals schema as the migration builds it: enums, grants, constraints."""

from __future__ import annotations

from datetime import UTC, date, datetime
from typing import TYPE_CHECKING

import pytest
from journals_rows import OPERATOR, journal, publish, snapshot, speciality
from sqlalchemy import delete, insert, select, text, update
from sqlalchemy.exc import DBAPIError, IntegrityError

from vld.journals.domain import Channel, DocumentSource, IssnSource, PublicationKind
from vld.journals.infrastructure.models import (
    CHANNEL,
    DOCUMENT_SOURCE,
    ISSN_SOURCE,
    JOURNAL,
    JOURNAL_ISSN,
    PUBLICATION_KIND,
    SCHEMA,
    SCIENCE_BRANCH,
    SPECIALITY,
    VAK_CURRENT,
    VAK_DOCUMENT,
    VAK_DOCUMENT_FILE,
    VAK_FORMER_ISSN,
    VAK_FORMER_TITLE,
    VAK_GROUP,
    VAK_GROUP_SPECIALITY,
    VAK_LISTING,
    VAK_LISTING_ISSN,
    VAK_PARSE,
    VAK_PARSE_WARNING,
    VAK_PUBLICATION,
    VAK_SNAPSHOT,
    VAK_WARNING_CODE,
    JournalIssnModel,
    SpecialityModel,
    VakCurrentModel,
    VakDocumentModel,
    VakListingModel,
    VakPublicationModel,
    VakSnapshotModel,
)
from vld.vak.models import ScienceBranch, WarningCode

if TYPE_CHECKING:
    from enum import StrEnum

    from sqlalchemy.ext.asyncio import AsyncConnection

pytestmark = pytest.mark.integration

APP_ROLE = "vld_test_app"
_PRIVILEGES = ("SELECT", "INSERT", "UPDATE", "DELETE", "TRUNCATE")
_ADD_ONLY = frozenset({"SELECT", "INSERT"})
# What the app role may do on each table; nothing else.
_GRANTED: dict[str, frozenset[str]] = {
    JOURNAL: _ADD_ONLY,
    JOURNAL_ISSN: _ADD_ONLY | {"UPDATE"},
    SPECIALITY: _ADD_ONLY,
    VAK_DOCUMENT: _ADD_ONLY,
    VAK_DOCUMENT_FILE: _ADD_ONLY | {"DELETE"},
    VAK_SNAPSHOT: _ADD_ONLY,
    VAK_PARSE: _ADD_ONLY,
    VAK_PARSE_WARNING: _ADD_ONLY,
    VAK_LISTING: _ADD_ONLY,
    VAK_LISTING_ISSN: _ADD_ONLY,
    VAK_FORMER_TITLE: _ADD_ONLY,
    VAK_FORMER_ISSN: _ADD_ONLY,
    VAK_GROUP: _ADD_ONLY,
    VAK_GROUP_SPECIALITY: _ADD_ONLY,
    VAK_CURRENT: _ADD_ONLY | {"UPDATE"},
    VAK_PUBLICATION: _ADD_ONLY,
}

_ENUM_LABELS = text("""
    select enumlabel from pg_enum e
    join pg_type t on t.oid = e.enumtypid
    join pg_namespace n on n.oid = t.typnamespace
    where n.nspname = :schema and t.typname = :type_name
    order by e.enumsortorder
""")


@pytest.mark.parametrize(
    ("type_name", "enum"),
    [
        (SCIENCE_BRANCH, ScienceBranch),
        (VAK_WARNING_CODE, WarningCode),
        (CHANNEL, Channel),
        (DOCUMENT_SOURCE, DocumentSource),
        (ISSN_SOURCE, IssnSource),
        (PUBLICATION_KIND, PublicationKind),
    ],
)
async def test_enum_labels_are_the_values_of_the_code(
    owner: AsyncConnection,
    type_name: str,
    enum: type[StrEnum],
) -> None:
    """A value added to the parser without a migration turns this red."""
    rows = await owner.execute(_ENUM_LABELS, {"schema": SCHEMA, "type_name": type_name})

    assert [row[0] for row in rows] == [member.value for member in enum]


async def test_the_schema_holds_exactly_these_tables(owner: AsyncConnection) -> None:
    """Every table of the schema is in the grant table below, and back."""
    rows = await owner.execute(
        text("select tablename from pg_tables where schemaname = :schema"),
        {"schema": SCHEMA},
    )

    assert {row[0] for row in rows} == set(_GRANTED)


async def test_the_app_role_has_exactly_its_grants(owner: AsyncConnection) -> None:
    """Facts, snapshots and the log are insert-only; three tables change."""
    granted: dict[str, set[str]] = {}
    for table in _GRANTED:
        for privilege in _PRIVILEGES:
            allowed = await owner.scalar(
                text("select has_table_privilege(:role, :table, :privilege)"),
                {
                    "role": APP_ROLE,
                    "table": f"{SCHEMA}.{table}",
                    "privilege": privilege,
                },
            )
            if allowed:
                granted.setdefault(table, set()).add(privilege)

    assert granted == {table: set(privileges) for table, privileges in _GRANTED.items()}


async def test_the_app_role_cannot_rewrite_a_fact(app: AsyncConnection) -> None:
    """The grant holds in practice: an UPDATE of an entry is refused."""
    with pytest.raises(DBAPIError, match="permission denied"):
        _ = await app.execute(update(VakListingModel).values(number=1))


async def test_the_app_role_cannot_delete_a_publication(app: AsyncConnection) -> None:
    """The log of what we knew is never trimmed."""
    with pytest.raises(DBAPIError, match="permission denied"):
        _ = await app.execute(delete(VakPublicationModel))


async def test_the_app_role_reassigns_an_issn_and_moves_the_pointer(
    app: AsyncConnection,
) -> None:
    """The three changing tables change under the app role."""
    first = await journal(app, "2587-7534")
    second = await journal(app)
    drafts = [await snapshot(app, date(2026, 3, 30), name) for name in ("a", "b")]
    for draft in drafts:
        await publish(app, draft)

    _ = await app.execute(
        update(JournalIssnModel)
        .where(JournalIssnModel.issn == "2587-7534")
        .values(journal_id=second, source=IssnSource.MODERATOR),
    )

    assert (
        await app.scalar(
            select(JournalIssnModel.journal_id),
        )
        == second
    )
    assert first != second
    assert await app.scalar(select(VakCurrentModel.snapshot_id)) == drafts[1]


async def test_an_issn_belongs_to_one_journal(owner: AsyncConnection) -> None:
    """ISSN is the key of `journal_issn`."""
    _ = await journal(owner, "2587-7534")

    with pytest.raises(IntegrityError):
        _ = await journal(owner, "2587-7534")


@pytest.mark.parametrize("issn", ["25877534", "2587-753x", "1234-567"])
async def test_a_malformed_issn_is_refused(owner: AsyncConnection, issn: str) -> None:
    """Only NNNN-NNNC with a capital X reaches the table."""
    with pytest.raises(IntegrityError, match="issn_format"):
        _ = await journal(owner, issn)


async def test_a_speciality_is_one_row_per_code_and_branch(
    owner: AsyncConnection,
) -> None:
    """The same pair twice is refused, an unknown branch included."""
    _ = await speciality(owner, "5.9.5", ScienceBranch.PHILOLOGY)
    _ = await speciality(owner, "5.9.5", None)

    for branch in (ScienceBranch.PHILOLOGY, None):
        with pytest.raises(IntegrityError):
            async with owner.begin_nested():
                _ = await speciality(owner, "5.9.5", branch)


async def test_a_malformed_speciality_code_is_refused(owner: AsyncConnection) -> None:
    """A code is two or three numbers joined by dots."""
    with pytest.raises(IntegrityError, match="code_format"):
        _ = await owner.execute(insert(SpecialityModel).values(code="5.9", branch=None))


async def test_a_document_is_read_once_per_parser_version(
    owner: AsyncConnection,
) -> None:
    """The same document with the same parser is one snapshot."""
    first = await snapshot(owner, date(2026, 9, 15), "edition")
    document_id = await owner.scalar(
        select(VakSnapshotModel.document_id).where(VakSnapshotModel.id == first),
    )
    again = insert(VakSnapshotModel).values(
        document_id=document_id,
        parser_version="0.1.1",
        edition_date=date(2026, 9, 15),
        channel=Channel.CLI,
        operator=OPERATOR,
    )

    with pytest.raises(IntegrityError):
        _ = await owner.execute(again)


async def test_a_document_has_an_origin(owner: AsyncConnection) -> None:
    """Neither a URL nor a file name is refused."""
    nameless = insert(VakDocumentModel).values(
        sha256=b"\x00" * 32,
        size=1,
        source=DocumentSource.FILE,
        fetched_at=datetime.now(UTC),
    )

    with pytest.raises(IntegrityError, match="has_origin"):
        _ = await owner.execute(nameless)


async def test_there_is_one_pointer(owner: AsyncConnection) -> None:
    """A second row of `vak_current` is refused, true or false."""
    draft = await snapshot(owner, date(2026, 9, 15), "edition")
    _ = await owner.execute(insert(VakCurrentModel).values(snapshot_id=draft))

    for singleton in (True, False):
        with pytest.raises(IntegrityError):
            async with owner.begin_nested():
                _ = await owner.execute(
                    insert(VakCurrentModel).values(
                        singleton=singleton,
                        snapshot_id=draft,
                    ),
                )


@pytest.mark.parametrize(
    ("kind", "forced"),
    [(PublicationKind.ROLLBACK, False), (PublicationKind.PUBLISH, True)],
)
async def test_a_rollback_or_a_forced_publication_needs_a_reason(
    owner: AsyncConnection,
    kind: PublicationKind,
    forced: bool,  # ruff: ignore[boolean-type-hint-positional-argument] -- a parametrized case
) -> None:
    """The reason is required by the database, not by the code."""
    first = await snapshot(owner, date(2026, 3, 30), "old")
    second = await snapshot(owner, date(2026, 9, 15), "new")
    reasonless = insert(VakPublicationModel).values(
        kind=kind,
        from_snapshot_id=second,
        to_snapshot_id=first,
        forced=forced,
        channel=Channel.CLI,
        operator=OPERATOR,
    )

    with pytest.raises(IntegrityError, match="reason_when_forced_or_rolled_back"):
        _ = await owner.execute(reasonless)


async def test_a_publication_moves_the_pointer(owner: AsyncConnection) -> None:
    """From a snapshot to itself is no move."""
    draft = await snapshot(owner, date(2026, 9, 15), "edition")
    standstill = insert(VakPublicationModel).values(
        kind=PublicationKind.PUBLISH,
        from_snapshot_id=draft,
        to_snapshot_id=draft,
        forced=False,
        channel=Channel.CLI,
        operator=OPERATOR,
    )

    with pytest.raises(IntegrityError, match="moves"):
        _ = await owner.execute(standstill)
