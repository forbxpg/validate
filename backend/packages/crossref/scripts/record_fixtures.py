"""Record real Crossref answers into ``tests/fixtures``; run by hand, never by tests.

Usage::

    uv run python packages/crossref/scripts/record_fixtures.py --mailto you@example.org

Without ``--mailto`` the requests go to the public pool, one at a time.
"""

from __future__ import annotations

import argparse
import asyncio
import copy
import json
from pathlib import Path
from typing import cast

import httpx

FIXTURES = Path(__file__).parents[1] / "tests" / "fixtures"
BASE_URL = "https://api.crossref.org"
PAUSE_SECONDS = 0.5
ATTEMPTS = 5
TRANSIENT_FROM = 429

WORKS: dict[str, tuple[str, dict[str, str]]] = {
    "work_journal_article": ("/works/10.1103/physrevlett.1.1", {}),
    "work_rich": ("/works/10.7554/elife.85324", {}),
    "work_book_chapter": ("/works/10.1007/978-3-031-30897-0_14", {}),
    "work_posted_content": ("/works/10.20944/preprints202407.1143.v1", {}),
    "work_partial_date": ("/works/10.1097/00000441-183007130-00046", {}),
    "work_agency": ("/works/10.1103/physrevlett.1.1/agency", {}),
    "works_page_facets": (
        "/works",
        {"query": "graphene", "rows": "5", "facet": "type-name:5,published:5"},
    ),
    "works_page_filtered": (
        "/works",
        {
            "filter": "from-pub-date:2024,type:journal-article,has-orcid:true",
            "rows": "5",
            "sort": "published",
            "order": "desc",
        },
    ),
    "works_sample": ("/works", {"sample": "3"}),
    "works_validation_failure": ("/works", {"filter": "zzz:1"}),
}
"""Fixtures of part 2: works."""

JOURNALS: dict[str, tuple[str, dict[str, str]]] = {
    "journal_prl": ("/journals/0031-9007", {}),
    "journals_page": ("/journals", {"query": "physical review", "rows": "5"}),
    "journal_works_page": (
        "/journals/0031-9007/works",
        {"rows": "3", "sort": "published", "order": "desc"},
    ),
    "journals_filter_refused": ("/journals", {"filter": "zzz:1"}),
}
"""Fixtures of part 3: journals."""

CURSOR_PAGES: dict[str, tuple[str, dict[str, str]]] = {
    "works_cursor": ("/works", {"filter": "prefix:10.1103", "rows": "3"}),
    "journals_cursor": ("/journals", {"rows": "3"}),
}
"""Two consecutive cursor pages each: ``<name>_first`` and ``<name>_second``."""


def _malformed_journal(prl: dict[str, object]) -> dict[str, object]:
    """A copy of ``journal_prl`` with an invalid ISSN and odd shapes.

    Args:
        prl: dict[str, object] - The recorded ``journal_prl`` answer.

    Returns:
        dict[str, object] - The broken copy.

    """
    broken = copy.deepcopy(prl)
    message = cast("dict[str, object]", broken["message"])
    message["ISSN"] = ["0031-9008", "1079-7114"]
    message["issn-type"] = {"type": "electronic", "value": "1079-7114"}
    message["counts"] = "many"
    message["subjects"] = [{"name": "Physics", "ASJC": 3100}, "General Physics", None]
    return broken


def _malformed_work(rich: dict[str, object]) -> dict[str, object]:
    """A copy of ``work_rich`` with the shapes Crossref sometimes sends wrong.

    Args:
        rich: dict[str, object] - The recorded ``work_rich`` answer.

    Returns:
        dict[str, object] - The broken copy.

    """
    broken = copy.deepcopy(rich)
    message = cast("dict[str, object]", broken["message"])
    message["author"] = "not a list"
    message["published"] = "yesterday"
    message["reference"] = None
    message["ISSN"] = ["not-an-issn", "2050-084X"]
    message["title"] = ["A title", None, ""]
    message["volume"] = 12
    return broken


async def _get(client: httpx.AsyncClient, path: str, params: dict[str, str]) -> object:
    """GET a path, retrying 429 and 5xx with a growing pause.

    Args:
        client: httpx.AsyncClient - The HTTP client.
        path: str - Path of the request.
        params: dict[str, str] - Its parameters.

    Returns:
        object - The JSON body, also of a 400.

    Raises:
        RuntimeError: If Crossref kept failing.

    """
    status = 0
    for attempt in range(ATTEMPTS):
        response = await client.get(BASE_URL + path, params=params)
        await asyncio.sleep(PAUSE_SECONDS * (1 << attempt))
        status = response.status_code
        if status < TRANSIENT_FROM:
            return cast("object", response.json())
    msg = f"{path} kept failing: {status}"
    raise RuntimeError(msg)


def _write(name: str, body: object) -> None:
    _ = (FIXTURES / f"{name}.json").write_text(
        json.dumps(body, ensure_ascii=False, indent=2) + "\n",
    )
    print(f"recorded {name}")


async def record(mailto: str | None) -> None:
    """Fetch every fixture and write it.

    Args:
        mailto: str | None - Address for the polite pool; None for the public pool.

    """
    FIXTURES.mkdir(parents=True, exist_ok=True)
    base = {} if mailto is None else {"mailto": mailto}
    agent = "vld-crossref-fixtures/1.0" + (
        "" if mailto is None else f" (mailto:{mailto})"
    )
    async with httpx.AsyncClient(headers={"User-Agent": agent}, timeout=30) as client:
        for name, (path, params) in (WORKS | JOURNALS).items():
            _write(name, await _get(client, path, {**params, **base}))
        for name, (path, params) in CURSOR_PAGES.items():
            first = await _get(client, path, {**params, **base, "cursor": "*"})
            cursor = cast("dict[str, dict[str, str]]", first)["message"]["next-cursor"]
            second = await _get(client, path, {**params, **base, "cursor": cursor})
            _write(f"{name}_first", first)
            _write(f"{name}_second", second)
    rich = cast(
        "dict[str, object]",
        json.loads((FIXTURES / "work_rich.json").read_text()),
    )
    _write("work_malformed_handmade", _malformed_work(rich))
    prl = cast(
        "dict[str, object]",
        json.loads((FIXTURES / "journal_prl.json").read_text()),
    )
    _write("journal_malformed_handmade", _malformed_journal(prl))


def main() -> None:
    """Parse the command line and record."""
    parser = argparse.ArgumentParser(description=__doc__)
    _ = parser.add_argument(
        "--mailto",
        default=None,
        help="address for the polite pool",
    )
    arguments = parser.parse_args()
    asyncio.run(record(cast("str | None", arguments.mailto)))


if __name__ == "__main__":
    main()
