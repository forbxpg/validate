"""The ORM models: the tables of the schema and the enums they borrow from the parser."""

from __future__ import annotations

from typing import TYPE_CHECKING, cast

from vld.journals.infrastructure.models import (
    METADATA,
    SCHEMA,
    SpecialityModel,
    VakParseWarningModel,
)
from vld.vak.models import ScienceBranch, WarningCode

if TYPE_CHECKING:
    from sqlalchemy import Enum

_TABLES = {
    "journal",
    "journal_issn",
    "speciality",
    "vak_document",
    "vak_document_file",
    "vak_snapshot",
    "vak_parse",
    "vak_parse_warning",
    "vak_listing",
    "vak_listing_issn",
    "vak_former_title",
    "vak_former_issn",
    "vak_group",
    "vak_group_speciality",
    "vak_current",
    "vak_publication",
}


def test_the_metadata_holds_the_tables_of_the_schema() -> None:
    """Sixteen tables, all in `journals`: the shared three and the VAK registry."""
    assert set(METADATA.tables) == {f"{SCHEMA}.{table}" for table in _TABLES}


def test_the_enums_are_the_parser_s() -> None:
    """A branch or a warning code is what vld-vak says, in its order."""
    branch = cast("Enum", SpecialityModel.__table__.c.branch.type)
    code = cast("Enum", VakParseWarningModel.__table__.c.code.type)

    assert list(branch.enums) == [member.value for member in ScienceBranch]
    assert list(code.enums) == [member.value for member in WarningCode]
