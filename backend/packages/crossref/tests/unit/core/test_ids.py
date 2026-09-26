"""DOIs and ISSNs in any common form."""

from __future__ import annotations

import pytest

from vld.crossref import CrossrefQueryError, normalize_doi, normalize_issn


@pytest.mark.parametrize(
    ("raw", "doi"),
    [
        ("10.1103/PhysRevLett.1.1", "10.1103/physrevlett.1.1"),
        ("  doi:10.1000/XYZ ", "10.1000/xyz"),
        ("DOI:10.1000/xyz", "10.1000/xyz"),
        ("https://doi.org/10.1000/abc", "10.1000/abc"),
        ("http://dx.doi.org/10.1000/abc", "10.1000/abc"),
        ("https://dx.doi.org/10.1000%2Fabc", "10.1000/abc"),
        ("10.1000.10/a(b)c<d>", "10.1000.10/a(b)c<d>"),
    ],
)
def test_a_doi_is_reduced_to_its_bare_lower_case_form(raw: str, doi: str) -> None:
    """Links, prefixes, encoding and case are removed."""
    assert normalize_doi(raw) == doi


@pytest.mark.parametrize(
    "raw",
    ["", "10.1000", "10.1000/", "11.1000/abc", "10.abc/x", "not a doi"],
)
def test_a_non_doi_is_refused(raw: str) -> None:
    """A value without the 10.<registrant>/<suffix> shape is refused."""
    with pytest.raises(CrossrefQueryError, match="not a DOI"):
        _ = normalize_doi(raw)


@pytest.mark.parametrize(
    ("raw", "issn"),
    [
        ("0378-5955", "0378-5955"),
        ("2049-3630", "2049-3630"),
        ("0031 9007", "0031-9007"),
        ("00319007", "0031-9007"),
        ("1050-124x", "1050-124X"),
    ],
)
def test_an_issn_is_reduced_to_the_hyphenated_form(raw: str, issn: str) -> None:
    """Spaces, a missing hyphen and a lower-case x are accepted."""
    assert normalize_issn(raw) == issn


def test_a_wrong_check_digit_is_refused() -> None:
    """The check character guards against a typo."""
    with pytest.raises(CrossrefQueryError, match="check character"):
        _ = normalize_issn("0031-9008")


@pytest.mark.parametrize("raw", ["", "0031-900", "0031-90077", "X031-9007"])
def test_a_non_issn_is_refused(raw: str) -> None:
    """A value without eight positions is refused."""
    with pytest.raises(CrossrefQueryError, match="not an ISSN"):
        _ = normalize_issn(raw)
