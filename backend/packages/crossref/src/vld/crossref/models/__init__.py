"""Machinery shared by the models of every resource."""

from __future__ import annotations

from ._base import CrossrefModel
from ._dates import CrossrefDate, CrossrefTimestamp, PartialDate, from_date_parts
from ._fields import (
    Doi,
    IssnList,
    OptBool,
    OptDecimal,
    OptDoi,
    OptFloat,
    OptInt,
    OptIssn,
    OptOrcid,
    OptStr,
)
from ._lenient import (
    CleanStrList,
    StrList,
    current_record,
    degraded,
    lenient,
    parse_item,
)
from ._query import TEXT_MAX, QueryModel, QueryPart, Text

__all__ = (
    "TEXT_MAX",
    "CleanStrList",
    "CrossrefDate",
    "CrossrefModel",
    "CrossrefTimestamp",
    "Doi",
    "IssnList",
    "OptBool",
    "OptDecimal",
    "OptDoi",
    "OptFloat",
    "OptInt",
    "OptIssn",
    "OptOrcid",
    "OptStr",
    "PartialDate",
    "QueryModel",
    "QueryPart",
    "StrList",
    "Text",
    "current_record",
    "degraded",
    "from_date_parts",
    "lenient",
    "parse_item",
)
