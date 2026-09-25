from __future__ import annotations

import pytest
from pydantic import ValidationError

from vld.core.config import FrontendSettings


@pytest.mark.parametrize(
    ("given", "expected"),
    [
        ("https://Front.Test", "https://front.test"),
        ("HTTPS://FRONT.TEST", "https://front.test"),
        ("https://front.test/", "https://front.test"),
        ("https://front.test:8443", "https://front.test:8443"),
    ],
)
def test_the_scheme_and_the_host_are_lowered_but_the_path_is_not(
    given: str,
    expected: str,
) -> None:
    assert FrontendSettings(base_url=given).base_url == expected


@pytest.mark.parametrize(
    "given",
    ["front.test", "ftp://front.test", "https://", ""],
)
def test_an_address_without_a_scheme_or_a_host_is_refused(given: str) -> None:
    with pytest.raises(ValidationError):
        _ = FrontendSettings(base_url=given)
