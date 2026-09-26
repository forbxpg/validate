"""Identity of the client: address, Plus key and product."""

from __future__ import annotations

from dataclasses import dataclass
from re import compile as re_compile
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pydantic import SecretStr

VERSION = "0.1.0"
"""Version of the library, sent in `User-Agent`."""

_APP = re_compile(r"[A-Za-z0-9._-]+/[A-Za-z0-9._-]+")


@dataclass(frozen=True, slots=True)
class Identity:
    """Identification of the client, built once.

    Attributes:
        mailto: str | None - Address for the polite pool; None for the public pool.
        plus_token: SecretStr | None - Metadata Plus key; None without Plus.
        app: str - `product/version` of the service.

    """

    app: str
    mailto: str | None
    plus_token: SecretStr | None

    def __post_init__(self) -> None:
        """Refuse an identity Crossref would not accept.

        Raises:
            ValueError: If `mailto` is blank or has no `@`, or `app` is not
                `product/version`.

        """
        if self.mailto is not None and "@" not in self.mailto.strip():
            msg = f"mailto must be an e-mail address, got {self.mailto!r}"
            raise ValueError(msg)
        if not _APP.fullmatch(self.app):
            msg = f"app must be product/version, got {self.app!r}"
            raise ValueError(msg)

    def headers(self) -> dict[str, str]:
        """Headers of every request.

        Returns:
            dict[str, str] - `User-Agent` and, with Plus, the token header.

        """
        agent = (
            f"{self.app} vld-crossref/{VERSION}"
            if self.mailto is None
            else f"{self.app} (mailto:{self.mailto.strip()}) vld-crossref/{VERSION}"
        )
        headers = {"User-Agent": agent}
        if self.plus_token is not None:
            token = self.plus_token.get_secret_value()
            headers["Crossref-Plus-API-Token"] = f"Bearer {token}"
        return headers

    def params(self) -> dict[str, str]:
        """Query parameters of every request.

        Returns:
            dict[str, str] - `mailto` when set.

        """
        return {} if self.mailto is None else {"mailto": self.mailto.strip()}
