"""Errors of vld-vak: what went wrong, never what to tell a user."""

from __future__ import annotations


class VakError(Exception):
    """Base of every error the library raises."""


class NotVakListError(VakError):
    """The input is not a VAK list: not a PDF, no header, or no edition date."""


class VakSourceError(VakError):
    """The site of VAK did not show the list: unreachable, changed, or ambiguous."""


class VakDownloadError(VakError):
    """A file of the list could not be fetched: status, timeout, not a PDF, too large.

    Attributes:
        url: str - The file.

    """

    def __init__(self, message: str, *, url: str) -> None:
        super().__init__(f"{message}: {url}")
        self.url: str = url
