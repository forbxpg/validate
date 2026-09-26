"""Finding the list: the fake site answers a trimmed copy of the real news-list."""

from __future__ import annotations

import json
from copy import deepcopy
from datetime import UTC, datetime
from pathlib import Path

import httpx
import pytest

from vld.vak.download import fetch_listing
from vld.vak.errors import VakSourceError

BASE = "https://vak.test"
# The answer of 26.09.2026: the list, the К1–К3 distribution (same mark, other
# title), a letter without a mark.
ANSWER = json.loads(
    (Path(__file__).parents[1] / "fixtures/download/news_list.json").read_text(
        encoding="utf-8",
    ),
)
CURRENT = ANSWER["results"][0]["files"][1]["url"]


def _client(handler: httpx.MockTransport) -> httpx.AsyncClient:
    return httpx.AsyncClient(transport=handler)


def _site(
    *pages: dict[str, object],
    seen: list[httpx.Request] | None = None,
) -> httpx.MockTransport:
    def handle(request: httpx.Request) -> httpx.Response:
        if seen is not None:
            seen.append(request)
        number = int(request.url.params.get("page", "1"))
        return httpx.Response(200, json=pages[number - 1])

    return httpx.MockTransport(handle)


def _answer(
    *results: dict[str, object],
    next_page: str | None = None,
) -> dict[str, object]:
    return {
        "count": len(results),
        "next": next_page,
        "previous": None,
        "results": list(results),
    }


def _old_item() -> dict[str, object]:
    """An item of 2019 with the same mark and title and no link in its text."""
    item = deepcopy(ANSWER["results"][0])
    item["id"] = "619e2cfd-5ed5-4eef-9c3b-29c3ea1a1864"
    item["info"] = json.dumps([
        {"type": "p", "attributes": {}, "children": ["Перечень"]},
    ])
    return item


async def test_the_list_and_its_current_file_are_found() -> None:
    """The item with the mark, the title and a PDF link in its text."""
    async with _client(_site(ANSWER)) as client:
        listing = await fetch_listing(client, base_url=BASE)

    assert listing.news_id == "2094e02c-d851-48cd-9d57-fe7ebd34a039"
    assert listing.published_at == datetime(2026, 9, 17, 13, 15, tzinfo=UTC)
    assert listing.current_url == CURRENT
    assert len(listing.files) == 3


async def test_the_request_has_no_trailing_slash_and_names_the_sender() -> None:
    """The path with a slash answers 404 on the real site."""
    seen: list[httpx.Request] = []
    async with _client(_site(ANSWER, seen=seen)) as client:
        _ = await fetch_listing(client, base_url=BASE)

    [request] = seen
    assert request.url.path == "/api/news/news-list"
    assert dict(request.url.params) == {"page": "1", "pageSize": "50", "type": "19"}
    assert request.headers["User-Agent"].startswith("vld-vak/")


async def test_old_items_of_the_list_without_a_link_are_passed_over() -> None:
    """Items of 2018 and 2019 carry the same mark and title."""
    answer = _answer(_old_item(), *ANSWER["results"])

    async with _client(_site(answer)) as client:
        listing = await fetch_listing(client, base_url=BASE)

    assert listing.current_url == CURRENT


async def test_two_items_linking_a_pdf_are_an_error() -> None:
    """Choosing one of two would be a guess."""
    second = deepcopy(ANSWER["results"][0]) | {"id": "another"}
    answer = _answer(ANSWER["results"][0], second)

    async with _client(_site(answer)) as client:
        with pytest.raises(VakSourceError, match="found"):
            _ = await fetch_listing(client, base_url=BASE)


@pytest.mark.parametrize("drop", ["the item", "the link"])
async def test_no_item_linking_a_pdf_is_an_error(drop: str) -> None:
    """Without the item, or with an item whose text links nothing."""
    results = deepcopy(ANSWER["results"])
    if drop == "the item":
        results = results[1:]
    else:
        results[0]["info"] = ""

    async with _client(_site(_answer(*results))) as client:
        with pytest.raises(VakSourceError, match=r"found \[\]"):
            _ = await fetch_listing(client, base_url=BASE)


async def test_pages_are_counted_here_and_next_is_not_followed() -> None:
    """The site's next link points inside its own network."""
    internal = "http://fisgna-service.prod.sol.mtp/api/news/news-list?page=2&pageSize=50&type=19"
    first = _answer(ANSWER["results"][2], next_page=internal)
    second = _answer(*ANSWER["results"][:2])
    seen: list[httpx.Request] = []

    async with _client(_site(first, second, seen=seen)) as client:
        listing = await fetch_listing(client, base_url=BASE)

    assert listing.current_url == CURRENT
    assert [(request.url.host, request.url.params["page"]) for request in seen] == [
        ("vak.test", "1"),
        ("vak.test", "2"),
    ]


async def test_a_site_that_never_ends_is_an_error() -> None:
    """Twenty pages of «next» is no list of two dozen items."""
    endless = _answer(ANSWER["results"][2], next_page="more")

    async with _client(_site(*[endless] * 25)) as client:
        with pytest.raises(VakSourceError, match="next page"):
            _ = await fetch_listing(client, base_url=BASE)


@pytest.mark.parametrize(
    ("response", "reason"),
    [
        (httpx.Response(404, text="Not Found"), "answered 404"),
        (httpx.Response(200, json={"results": "nothing"}), "another shape"),
    ],
)
async def test_another_answer_is_an_error(
    response: httpx.Response,
    reason: str,
) -> None:
    """A status other than 2xx, or JSON of another shape."""
    async with _client(httpx.MockTransport(lambda _: response)) as client:
        with pytest.raises(VakSourceError, match=reason):
            _ = await fetch_listing(client, base_url=BASE)


async def test_the_first_link_to_a_pdf_is_the_current_file() -> None:
    """A link to a page of the site before the file is no file."""
    item = deepcopy(ANSWER["results"][0])
    page = {
        "type": "a",
        "attributes": {"href": "https://vak.gisnauka.ru/news"},
        "children": [],
    }
    info = json.loads(item["info"])
    info[0]["children"].insert(0, page)
    item["info"] = json.dumps(info, ensure_ascii=False)

    async with _client(_site(_answer(item))) as client:
        listing = await fetch_listing(client, base_url=BASE)

    assert listing.current_url == CURRENT


async def test_no_answer_is_an_error() -> None:
    """A connection that fails."""

    def refuse(request: httpx.Request) -> httpx.Response:
        message = "refused"
        raise httpx.ConnectError(message, request=request)

    async with _client(httpx.MockTransport(refuse)) as client:
        with pytest.raises(VakSourceError, match="ConnectError"):
            _ = await fetch_listing(client, base_url=BASE)
