"""Profile of a user: the names and study details a citation needs."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Profile:
    """Optional personal details, all set by the user.

    Attributes:
        first_name_ru: str | None - First name in Russian.
        last_name_ru: str | None - Last name in Russian.
        first_name_en: str | None - First name in English.
        last_name_en: str | None - Last name in English.
        group_number: str | None - Study group.
        institution_name: str | None - Organization, free text until the list of
            organizations exists.

    """

    first_name_ru: str | None = None
    last_name_ru: str | None = None
    first_name_en: str | None = None
    last_name_en: str | None = None
    group_number: str | None = None
    institution_name: str | None = None
