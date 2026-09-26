"""How a work relates to others: relations, updates, trials and Crossmark assertions."""

from __future__ import annotations

from typing import Annotated

from pydantic import Field

from vld.crossref.models import (
    CrossrefModel,
    CrossrefTimestamp,
    OptInt,
    OptStr,
    lenient,
)


class Relation(CrossrefModel):
    """One related object.

    Attributes:
        id: str | None - Identifier of the related object.
        id_type: str | None - Its kind, such as ``doi``.
        asserted_by: str | None - ``subject`` or ``object``.

    """

    id: OptStr = None
    id_type: OptStr = Field(default=None, alias="id-type")
    asserted_by: OptStr = Field(default=None, alias="asserted-by")


class Update(CrossrefModel):
    """A correction, retraction or other update between two works.

    Attributes:
        doi: str | None - The other work.
        type: str | None - Kind of update, such as ``correction``.
        label: str | None - Label to show.
        source: str | None - Who reported it.
        record_id: str | None - Identifier of the record.
        updated: CrossrefTimestamp | None - When.

    """

    doi: OptStr = Field(default=None, alias="DOI")
    type: OptStr = None
    label: OptStr = None
    source: OptStr = None
    record_id: OptStr = Field(default=None, alias="record-id")
    updated: Annotated[CrossrefTimestamp | None, lenient(None)] = None


class ClinicalTrial(CrossrefModel):
    """A clinical trial a work reports.

    Attributes:
        clinical_trial_number: str | None - Number of the trial.
        registry: str | None - Registry DOI.
        type: str | None - Stage of the report.

    """

    clinical_trial_number: OptStr = Field(default=None, alias="clinical-trial-number")
    registry: OptStr = None
    type: OptStr = None


class AssertionGroup(CrossrefModel):
    """A group of Crossmark assertions.

    Attributes:
        name: str | None - Name.
        label: str | None - Label to show.

    """

    name: OptStr = None
    label: OptStr = None


class AssertionExplanation(CrossrefModel):
    """Where an assertion is explained.

    Attributes:
        url: str | None - The link.

    """

    url: OptStr = Field(default=None, alias="URL")


class Assertion(CrossrefModel):
    """A Crossmark assertion, such as a date of peer review.

    Attributes:
        name: str | None - Name.
        value: str | None - Value.
        url: str | None - Link.
        label: str | None - Label to show.
        order: int | None - Position.
        group: AssertionGroup | None - Group.
        explanation: AssertionExplanation | None - Explanation.

    """

    name: OptStr = None
    value: OptStr = None
    url: OptStr = Field(default=None, alias="URL")
    label: OptStr = None
    order: OptInt = None
    group: Annotated[AssertionGroup | None, lenient(None)] = None
    explanation: Annotated[AssertionExplanation | None, lenient(None)] = None
