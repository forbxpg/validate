"""Every error exported by core has an entry in the core error registry."""

from __future__ import annotations

import importlib
import pkgutil
from typing import cast

import vld.core
from vld.web.errors import CORE_ERRORS


def _exported_errors() -> set[type[Exception]]:
    found: set[type[Exception]] = set()
    for module in pkgutil.walk_packages(vld.core.__path__, prefix="vld.core."):
        imported = importlib.import_module(module.name)
        for name in cast("tuple[str, ...]", getattr(imported, "__all__", ())):
            attribute: object = getattr(imported, name, None)
            if (
                isinstance(attribute, type)
                and issubclass(attribute, Exception)
                and attribute.__module__.startswith("vld.core.")
            ):
                found.add(attribute)
    return found


def test_every_exported_core_error_is_mapped() -> None:
    """A forgotten error must fail CI instead of answering 500 in production."""
    assert _exported_errors() <= set(CORE_ERRORS.mapping)


def test_the_walk_finds_something() -> None:
    """A completeness test that finds nothing would pass forever."""
    assert _exported_errors()
