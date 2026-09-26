"""A client of the real Crossref, for tests run by hand before a release."""

from __future__ import annotations

import os
from typing import TYPE_CHECKING

import pytest

from vld.crossref import CrossrefClient, LocalThrottle

if TYPE_CHECKING:
    from collections.abc import AsyncIterator


@pytest.fixture
async def live() -> AsyncIterator[CrossrefClient]:
    """Give a client of the real API; ``CROSSREF_LIVE_MAILTO=public`` uses no address."""
    mailto = os.environ.get("CROSSREF_LIVE_MAILTO")
    if not mailto:
        pytest.skip("CROSSREF_LIVE_MAILTO is not set (an address, or 'public')")
    async with CrossrefClient(
        mailto=None if mailto == "public" else mailto,
        throttle=LocalThrottle(),
        app="vld-crossref-live-tests/1.0",
    ) as client:
        yield client


@pytest.fixture
def live_mailto() -> str | None:
    """Give the address of live runs; None for the public pool."""
    mailto = os.environ.get("CROSSREF_LIVE_MAILTO")
    if not mailto:
        pytest.skip("CROSSREF_LIVE_MAILTO is not set (an address, or 'public')")
    return None if mailto == "public" else mailto
