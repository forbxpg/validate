"""Money behind a work: funders, awards and grant projects."""

from __future__ import annotations

from typing import Annotated

from pydantic import BeforeValidator, Field

from vld.crossref.models import (
    CleanStrList,
    CrossrefModel,
    OptDecimal,
    OptInt,
    OptStr,
    PartialDate,
    from_date_parts,
    lenient,
)

from ._contributors import Investigator

DateList = Annotated[
    tuple[Annotated[PartialDate, BeforeValidator(from_date_parts)], ...],
    lenient(()),
]


class FunderId(CrossrefModel):
    """An identifier of a funder.

    Attributes:
        id: str | None - The identifier.
        id_type: str | None - Its kind, such as ``DOI`` or ``ROR``.
        asserted_by: str | None - Who asserted it.

    """

    id: OptStr = None
    id_type: OptStr = Field(default=None, alias="id-type")
    asserted_by: OptStr = Field(default=None, alias="asserted-by")


class Funder(CrossrefModel):
    """A funder of a work.

    Attributes:
        name: str | None - Name.
        doi: str | None - DOI of the funder in the Funder Registry.
        doi_asserted_by: str | None - ``crossref`` or ``publisher``.
        award: tuple[str, ...] - Award numbers.
        id: tuple[FunderId, ...] - Identifiers.

    """

    name: OptStr = None
    doi: OptStr = Field(default=None, alias="DOI")
    doi_asserted_by: OptStr = Field(default=None, alias="doi-asserted-by")
    award: CleanStrList = ()
    id: Annotated[tuple[FunderId, ...], lenient(())] = ()


class AwardAmount(CrossrefModel):
    """Money of an award.

    Attributes:
        amount: Decimal | None - The amount.
        currency: str | None - Currency code.
        percentage: int | None - Share of the project.

    """

    amount: OptDecimal = None
    currency: OptStr = None
    percentage: OptInt = None


class Funding(CrossrefModel):
    """One funding of a grant project.

    Attributes:
        type: str | None - Kind of funding.
        scheme: str | None - Funding scheme.
        award_amount: AwardAmount | None - Money.
        funder: Funder | None - Who pays.

    """

    type: OptStr = None
    scheme: OptStr = None
    award_amount: Annotated[AwardAmount | None, lenient(None)] = Field(
        default=None,
        alias="award-amount",
    )
    funder: Annotated[Funder | None, lenient(None)] = None


class ProjectTitle(CrossrefModel):
    """A title of a grant project.

    Attributes:
        title: str | None - The title.
        language: str | None - Its language.

    """

    title: OptStr = None
    language: OptStr = None


class ProjectDescription(CrossrefModel):
    """A description of a grant project.

    Attributes:
        description: str | None - The text.
        language: str | None - Its language.

    """

    description: OptStr = None
    language: OptStr = None


class Project(CrossrefModel):
    """A grant project, for works of type ``grant``.

    Attributes:
        project_title: tuple[ProjectTitle, ...] - Titles.
        project_description: tuple[ProjectDescription, ...] - Descriptions.
        investigator: tuple[Investigator, ...] - Investigators.
        lead_investigator: tuple[Investigator, ...] - Lead investigators.
        co_lead_investigator: tuple[Investigator, ...] - Co-lead investigators.
        award_start: tuple[PartialDate, ...] - Start dates.
        award_end: tuple[PartialDate, ...] - End dates.
        award_planned_start: tuple[PartialDate, ...] - Planned start dates.
        award_planned_end: tuple[PartialDate, ...] - Planned end dates.
        funding: tuple[Funding, ...] - Fundings.
        award_amount: AwardAmount | None - Total money.

    """

    project_title: Annotated[tuple[ProjectTitle, ...], lenient(())] = Field(
        default=(),
        alias="project-title",
    )
    project_description: Annotated[tuple[ProjectDescription, ...], lenient(())] = Field(
        default=(),
        alias="project-description",
    )
    investigator: Annotated[tuple[Investigator, ...], lenient(())] = ()
    lead_investigator: Annotated[tuple[Investigator, ...], lenient(())] = Field(
        default=(),
        alias="lead-investigator",
    )
    co_lead_investigator: Annotated[tuple[Investigator, ...], lenient(())] = Field(
        default=(),
        alias="co-lead-investigator",
    )
    award_start: DateList = Field(default=(), alias="award-start")
    award_end: DateList = Field(default=(), alias="award-end")
    award_planned_start: DateList = Field(default=(), alias="award-planned-start")
    award_planned_end: DateList = Field(default=(), alias="award-planned-end")
    funding: Annotated[tuple[Funding, ...], lenient(())] = ()
    award_amount: Annotated[AwardAmount | None, lenient(None)] = Field(
        default=None,
        alias="award-amount",
    )
