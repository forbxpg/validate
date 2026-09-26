"""Identifiers the works filters take: ORCID iDs, DOI prefixes, ROR ids."""

from __future__ import annotations

import pytest

from vld.crossref import CrossrefQueryError
from vld.crossref.ids import normalize_orcid, normalize_prefix, normalize_ror


@pytest.mark.parametrize(
    ("raw", "orcid"),
    [
        ("0000-0002-1825-0097", "0000-0002-1825-0097"),
        ("https://orcid.org/0000-0002-1825-0097", "0000-0002-1825-0097"),
        ("0000000218250097", "0000-0002-1825-0097"),
        ("0000-0002-9079-593x", "0000-0002-9079-593X"),
    ],
)
def test_an_orcid_is_reduced_to_its_hyphenated_form(raw: str, orcid: str) -> None:
    """Links, missing hyphens and a lower-case x are accepted."""
    assert normalize_orcid(raw) == orcid


@pytest.mark.parametrize("raw", ["0000-0002-1825-0098", "0000-0002-1825", "orcid"])
def test_a_bad_orcid_is_refused(raw: str) -> None:
    """A wrong check character or length is refused."""
    with pytest.raises(CrossrefQueryError, match="ORCID"):
        _ = normalize_orcid(raw)


@pytest.mark.parametrize(
    ("raw", "prefix"),
    [("10.1103", "10.1103"), (" 10.1000.10 ", "10.1000.10")],
)
def test_a_prefix_is_checked(raw: str, prefix: str) -> None:
    """A DOI prefix is 10. and digits."""
    assert normalize_prefix(raw) == prefix


@pytest.mark.parametrize("raw", ["10.1103/x", "11.1103", "10."])
def test_a_bad_prefix_is_refused(raw: str) -> None:
    """A whole DOI or another number is not a prefix."""
    with pytest.raises(CrossrefQueryError, match="prefix"):
        _ = normalize_prefix(raw)


@pytest.mark.parametrize(
    ("raw", "ror"),
    [("05qwgg493", "05qwgg493"), ("https://ror.org/05QWGG493", "05qwgg493")],
)
def test_a_ror_id_is_reduced_to_nine_characters(raw: str, ror: str) -> None:
    """Links and upper case are accepted."""
    assert normalize_ror(raw) == ror


@pytest.mark.parametrize(
    "raw",
    ["5qwgg493", "05qwgg49", "https://ror.org/", "05qwgg4xx"],
)
def test_a_bad_ror_id_is_refused(raw: str) -> None:
    """A ROR id is a zero, six characters and two digits."""
    with pytest.raises(CrossrefQueryError, match="ROR"):
        _ = normalize_ror(raw)
