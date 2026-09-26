"""Errors of vld-vak: what went wrong, never what to tell a user."""

from __future__ import annotations


class VakError(Exception):
    """Base of every error the library raises."""


class NotVakListError(VakError):
    """The input is not a VAK list: not a PDF, no header, or no edition date."""
