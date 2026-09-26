"""Every filter of the works routes as a typed field (90, as Crossref listed them)."""

from __future__ import annotations

from typing import Annotated, Self, cast

from pydantic import Field, model_validator

from vld.crossref.errors import CrossrefQueryError
from vld.crossref.models import QueryPart

from ._enums import FunderDoiAssertedBy
from ._values import (
    DateBound,
    DepositBound,
    ManyDoi,
    ManyFullTextApplication,
    ManyInt,
    ManyIssn,
    ManyLicenseVersion,
    ManyOrcid,
    ManyPrefix,
    ManyRor,
    ManyStr,
    ManyWorkType,
    earliest,
    latest,
    render_value,
)

NonNegative = Annotated[int | None, Field(ge=0)]


class WorksFilter(QueryPart):
    """Filters of a works query; each field is one Crossref filter.

    Different filters narrow the result together; several values of one filter
    widen it (Crossref ORs them).
    """

    # Deposit and index dates
    from_created_date: DepositBound = Field(
        default=None,
        serialization_alias="from-created-date",
    )
    until_created_date: DepositBound = Field(
        default=None,
        serialization_alias="until-created-date",
    )
    from_update_date: DepositBound = Field(
        default=None,
        serialization_alias="from-update-date",
    )
    until_update_date: DepositBound = Field(
        default=None,
        serialization_alias="until-update-date",
    )
    from_deposit_date: DepositBound = Field(
        default=None,
        serialization_alias="from-deposit-date",
    )
    until_deposit_date: DepositBound = Field(
        default=None,
        serialization_alias="until-deposit-date",
    )
    from_index_date: DepositBound = Field(
        default=None,
        serialization_alias="from-index-date",
    )
    until_index_date: DepositBound = Field(
        default=None,
        serialization_alias="until-index-date",
    )
    # Publication dates
    from_pub_date: DateBound = Field(default=None, serialization_alias="from-pub-date")
    until_pub_date: DateBound = Field(
        default=None,
        serialization_alias="until-pub-date",
    )
    from_print_pub_date: DateBound = Field(
        default=None,
        serialization_alias="from-print-pub-date",
    )
    until_print_pub_date: DateBound = Field(
        default=None,
        serialization_alias="until-print-pub-date",
    )
    from_online_pub_date: DateBound = Field(
        default=None,
        serialization_alias="from-online-pub-date",
    )
    until_online_pub_date: DateBound = Field(
        default=None,
        serialization_alias="until-online-pub-date",
    )
    from_accepted_date: DateBound = Field(
        default=None,
        serialization_alias="from-accepted-date",
    )
    until_accepted_date: DateBound = Field(
        default=None,
        serialization_alias="until-accepted-date",
    )
    from_posted_date: DateBound = Field(
        default=None,
        serialization_alias="from-posted-date",
    )
    until_posted_date: DateBound = Field(
        default=None,
        serialization_alias="until-posted-date",
    )
    from_approved_date: DateBound = Field(
        default=None,
        serialization_alias="from-approved-date",
    )
    until_approved_date: DateBound = Field(
        default=None,
        serialization_alias="until-approved-date",
    )
    from_awarded_date: DateBound = Field(
        default=None,
        serialization_alias="from-awarded-date",
    )
    until_awarded_date: DateBound = Field(
        default=None,
        serialization_alias="until-awarded-date",
    )
    from_issued_date: DateBound = Field(
        default=None,
        serialization_alias="from-issued-date",
    )
    until_issued_date: DateBound = Field(
        default=None,
        serialization_alias="until-issued-date",
    )
    from_event_start_date: DateBound = Field(
        default=None,
        serialization_alias="from-event-start-date",
    )
    until_event_start_date: DateBound = Field(
        default=None,
        serialization_alias="until-event-start-date",
    )
    from_event_end_date: DateBound = Field(
        default=None,
        serialization_alias="from-event-end-date",
    )
    until_event_end_date: DateBound = Field(
        default=None,
        serialization_alias="until-event-end-date",
    )
    # Presence flags
    has_abstract: bool | None = Field(default=None, serialization_alias="has-abstract")
    has_affiliation: bool | None = Field(
        default=None,
        serialization_alias="has-affiliation",
    )
    has_affiliation_ror_id: bool | None = Field(
        default=None,
        serialization_alias="has-affiliation-ror-id",
    )
    has_alias: bool | None = Field(default=None, serialization_alias="has-alias")
    has_archive: bool | None = Field(default=None, serialization_alias="has-archive")
    has_assertion: bool | None = Field(
        default=None,
        serialization_alias="has-assertion",
    )
    has_authenticated_orcid: bool | None = Field(
        default=None,
        serialization_alias="has-authenticated-orcid",
    )
    has_award: bool | None = Field(default=None, serialization_alias="has-award")
    has_clinical_trial_number: bool | None = Field(
        default=None,
        serialization_alias="has-clinical-trial-number",
    )
    has_content_domain: bool | None = Field(
        default=None,
        serialization_alias="has-content-domain",
    )
    has_domain_restriction: bool | None = Field(
        default=None,
        serialization_alias="has-domain-restriction",
    )
    has_event: bool | None = Field(default=None, serialization_alias="has-event")
    has_full_text: bool | None = Field(
        default=None,
        serialization_alias="has-full-text",
    )
    has_funder: bool | None = Field(default=None, serialization_alias="has-funder")
    has_funder_doi: bool | None = Field(
        default=None,
        serialization_alias="has-funder-doi",
    )
    has_funder_ror_id: bool | None = Field(
        default=None,
        serialization_alias="has-funder-ror-id",
    )
    has_license: bool | None = Field(default=None, serialization_alias="has-license")
    has_orcid: bool | None = Field(default=None, serialization_alias="has-orcid")
    has_prime_doi: bool | None = Field(
        default=None,
        serialization_alias="has-prime-doi",
    )
    has_references: bool | None = Field(
        default=None,
        serialization_alias="has-references",
    )
    has_relation: bool | None = Field(default=None, serialization_alias="has-relation")
    has_ror_id: bool | None = Field(default=None, serialization_alias="has-ror-id")
    has_update: bool | None = Field(default=None, serialization_alias="has-update")
    has_update_policy: bool | None = Field(
        default=None,
        serialization_alias="has-update-policy",
    )
    is_update: bool | None = Field(default=None, serialization_alias="is-update")
    # Identifiers
    doi: ManyDoi = None
    issn: ManyIssn = None
    isbn: ManyStr = None
    orcid: ManyOrcid = None
    ror_id: ManyRor = Field(default=None, serialization_alias="ror-id")
    prefix: ManyPrefix = None
    member: ManyInt = None
    alternative_id: ManyStr = Field(default=None, serialization_alias="alternative-id")
    article_number: ManyStr = Field(default=None, serialization_alias="article-number")
    clinical_trial_number: ManyStr = Field(
        default=None,
        serialization_alias="clinical-trial-number",
    )
    updates: ManyDoi = None
    # Types and titles
    type: ManyWorkType = None
    type_name: ManyStr = Field(default=None, serialization_alias="type-name")
    container_title: ManyStr = Field(
        default=None,
        serialization_alias="container-title",
    )
    group_title: ManyStr = Field(default=None, serialization_alias="group-title")
    category_name: ManyStr = Field(default=None, serialization_alias="category-name")
    # Licenses and full text
    license_url: ManyStr = Field(default=None, serialization_alias="license.url")
    license_version: ManyLicenseVersion = Field(
        default=None,
        serialization_alias="license.version",
    )
    license_delay: NonNegative = Field(
        default=None,
        serialization_alias="license.delay",
    )
    full_text_type: ManyStr = Field(default=None, serialization_alias="full-text.type")
    full_text_application: ManyFullTextApplication = Field(
        default=None,
        serialization_alias="full-text.application",
    )
    full_text_version: ManyStr = Field(
        default=None,
        serialization_alias="full-text.version",
    )
    # Funding
    funder: ManyStr = None
    funder_doi_asserted_by: FunderDoiAssertedBy | None = Field(
        default=None,
        serialization_alias="funder-doi-asserted-by",
    )
    award_funder: ManyStr = Field(default=None, serialization_alias="award.funder")
    award_number: ManyStr = Field(default=None, serialization_alias="award.number")
    gte_award_amount: NonNegative = Field(
        default=None,
        serialization_alias="gte-award-amount",
    )
    lte_award_amount: NonNegative = Field(
        default=None,
        serialization_alias="lte-award-amount",
    )
    # Relations, updates, Crossmark
    relation_type: ManyStr = Field(default=None, serialization_alias="relation.type")
    relation_object: ManyStr = Field(
        default=None,
        serialization_alias="relation.object",
    )
    relation_object_type: ManyStr = Field(
        default=None,
        serialization_alias="relation.object-type",
    )
    update_type: ManyStr = Field(default=None, serialization_alias="update-type")
    assertion: ManyStr = None
    assertion_group: ManyStr = Field(
        default=None,
        serialization_alias="assertion-group",
    )
    content_domain: ManyStr = Field(default=None, serialization_alias="content-domain")
    # Archives
    archive: ManyStr = None
    directory: ManyStr = None

    @model_validator(mode="after")
    def _ranges_are_not_inverted(self) -> Self:
        """Refuse a ``from`` bound after its ``until`` bound.

        Returns:
            Self - The filter.

        Raises:
            CrossrefQueryError: If a range is empty.

        """
        for name in type(self).model_fields:
            if not name.startswith("from_"):
                continue
            partner = "until_" + name.removeprefix("from_")
            low = cast("object", getattr(self, name))
            high = cast("object", getattr(self, partner))
            lower = earliest(low)
            upper = latest(high)
            if lower is not None and upper is not None and lower > upper:
                msg = f"{name} is after {partner}"
                raise CrossrefQueryError(msg)
        return self

    def render(self) -> str | None:
        """Write the filters as Crossref's ``filter`` parameter.

        Filters come in the order of the catalogue, repeated values in the order
        given.

        Returns:
            str | None - ``name:value,name:value``, or None without filters.

        """
        pairs: list[str] = []
        for name, field in type(self).model_fields.items():
            value = cast("object", getattr(self, name))
            if value is None:
                continue
            key = field.serialization_alias or name
            values = (
                cast("tuple[object, ...]", value)
                if isinstance(value, tuple)
                else (value,)
            )
            pairs.extend(f"{key}:{render_value(item)}" for item in values)
        return ",".join(pairs) or None
