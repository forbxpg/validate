"""People and organizations of a work: authors, editors and their affiliations."""

from __future__ import annotations

from typing import Annotated

from pydantic import Field

from vld.crossref.models import (
    CleanStrList,
    CrossrefDate,
    CrossrefModel,
    OptBool,
    OptOrcid,
    OptStr,
    lenient,
)


class AffiliationId(CrossrefModel):
    """An identifier of an organization, such as a ROR id.

    Attributes:
        id: str | None - The identifier.
        id_type: str | None - Its kind, such as ``ROR``.
        asserted_by: str | None - Who asserted it.

    """

    id: OptStr = None
    id_type: OptStr = Field(default=None, alias="id-type")
    asserted_by: OptStr = Field(default=None, alias="asserted-by")


class Affiliation(CrossrefModel):
    """An organization a contributor belongs to, or an institution of a work.

    Attributes:
        name: str | None - Name.
        place: tuple[str, ...] - Places.
        department: tuple[str, ...] - Departments.
        acronym: tuple[str, ...] - Acronyms.
        id: tuple[AffiliationId, ...] - Identifiers.

    """

    name: OptStr = None
    place: CleanStrList = ()
    department: CleanStrList = ()
    acronym: CleanStrList = ()
    id: Annotated[tuple[AffiliationId, ...], lenient(())] = ()


class ContributorRole(CrossrefModel):
    """A role of a contributor in a vocabulary, such as CRediT.

    Attributes:
        role: str | None - The role.
        vocabulary: str | None - The vocabulary.

    """

    role: OptStr = None
    vocabulary: OptStr = None


class Contributor(CrossrefModel):
    """An author, editor, chair or translator.

    Attributes:
        given: str | None - Given name.
        family: str | None - Family name.
        name: str | None - Name of an organization or an undivided name.
        prefix: str | None - Prefix of the name.
        suffix: str | None - Suffix of the name.
        orcid: str | None - ORCID iD, normalized; an invalid one is dropped.
        authenticated_orcid: bool | None - Whether the owner authenticated it.
        sequence: str | None - ``first`` or ``additional``.
        affiliation: tuple[Affiliation, ...] - Affiliations.
        role: tuple[ContributorRole, ...] - Roles.

    """

    given: OptStr = None
    family: OptStr = None
    name: OptStr = None
    prefix: OptStr = None
    suffix: OptStr = None
    orcid: OptOrcid = Field(default=None, alias="ORCID")
    authenticated_orcid: OptBool = Field(default=None, alias="authenticated-orcid")
    sequence: OptStr = None
    affiliation: Annotated[tuple[Affiliation, ...], lenient(())] = ()
    role: Annotated[tuple[ContributorRole, ...], lenient(())] = ()

    @property
    def display_name(self) -> str | None:
        """The name to show: ``given family``, or ``name``.

        Returns:
            str | None - The name, or None when there is none.

        """
        joined = " ".join(part for part in (self.given, self.family) if part)
        return joined or self.name


class Investigator(Contributor):
    """A person of a grant project.

    Attributes:
        alternate_name: str | None - Another name.
        role_start: PartialDate | None - Start of the role.
        role_end: PartialDate | None - End of the role.

    """

    alternate_name: OptStr = Field(default=None, alias="alternate-name")
    role_start: CrossrefDate = Field(default=None, alias="role-start")
    role_end: CrossrefDate = Field(default=None, alias="role-end")
