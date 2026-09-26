"""Schema of the personal details, shared by registration, the account and admins."""

from __future__ import annotations

from typing import ClassVar

from pydantic import BaseModel, ConfigDict, Field

from vld.auth.domain import Profile

from ._limits import MAX_GROUP_NUMBER, MAX_INSTITUTION_NAME, MAX_NAME


class ProfileBody(BaseModel):
    """Personal details in a request or a response.

    Attributes:
        first_name_ru: str | None - First name in Russian.
        last_name_ru: str | None - Last name in Russian.
        first_name_en: str | None - First name in English.
        last_name_en: str | None - Last name in English.
        group_number: str | None - Study group.
        institution_name: str | None - Organization.

    """

    model_config: ClassVar[ConfigDict] = ConfigDict(
        str_strip_whitespace=True,
        from_attributes=True,
    )

    first_name_ru: str | None = Field(default=None, max_length=MAX_NAME)
    last_name_ru: str | None = Field(default=None, max_length=MAX_NAME)
    first_name_en: str | None = Field(default=None, max_length=MAX_NAME)
    last_name_en: str | None = Field(default=None, max_length=MAX_NAME)
    group_number: str | None = Field(default=None, max_length=MAX_GROUP_NUMBER)
    institution_name: str | None = Field(default=None, max_length=MAX_INSTITUTION_NAME)

    def to_domain(self) -> Profile:
        """Turn the body into the domain value, an empty string meaning "not given".

        Returns:
            Profile - The details.

        """
        return Profile(
            **{
                name: value or None
                for name, value in self.model_dump().items()  # pyright: ignore[reportAny]
            },
        )
