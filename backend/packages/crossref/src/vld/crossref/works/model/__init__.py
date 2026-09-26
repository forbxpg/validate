"""A work and its parts, read tolerantly."""

from __future__ import annotations

from ._contributors import (
    Affiliation,
    AffiliationId,
    Contributor,
    ContributorRole,
    Investigator,
)
from ._funding import (
    AwardAmount,
    Funder,
    FunderId,
    Funding,
    Project,
    ProjectDescription,
    ProjectTitle,
)
from ._links import License, Link, Resources, ResourceUrl
from ._misc import (
    Agency,
    ContentDomain,
    Event,
    FreeToRead,
    IssnType,
    JournalIssue,
    Reference,
    Review,
    StandardsBody,
    WorkAgency,
)
from ._relations import (
    Assertion,
    AssertionExplanation,
    AssertionGroup,
    ClinicalTrial,
    Relation,
    Update,
)
from ._work import Work

__all__ = (
    "Affiliation",
    "AffiliationId",
    "Agency",
    "Assertion",
    "AssertionExplanation",
    "AssertionGroup",
    "AwardAmount",
    "ClinicalTrial",
    "ContentDomain",
    "Contributor",
    "ContributorRole",
    "Event",
    "FreeToRead",
    "Funder",
    "FunderId",
    "Funding",
    "Investigator",
    "IssnType",
    "JournalIssue",
    "License",
    "Link",
    "Project",
    "ProjectDescription",
    "ProjectTitle",
    "Reference",
    "Relation",
    "ResourceUrl",
    "Resources",
    "Review",
    "StandardsBody",
    "Update",
    "Work",
    "WorkAgency",
)
