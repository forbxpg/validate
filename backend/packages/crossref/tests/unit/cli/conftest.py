"""Every CLI test leaves structlog as it found it."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
import structlog

if TYPE_CHECKING:
    from collections.abc import Iterator
    from pathlib import Path


@pytest.fixture
def isolated(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Iterator[None]:
    """Run in an empty folder, without the settings of the machine."""
    monkeypatch.chdir(tmp_path)
    for variable in ("CROSSREF_MAILTO", "CROSSREF_PLUS_TOKEN", "CROSSREF_OUTPUT_DIR"):
        monkeypatch.delenv(variable, raising=False)
    yield
    structlog.reset_defaults()
