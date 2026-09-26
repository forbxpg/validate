"""Finding the list on the site of VAK: its news item, current file and archive."""

from __future__ import annotations

import json
from datetime import datetime
from typing import TYPE_CHECKING, ClassVar, cast

from pydantic import BaseModel, ConfigDict, ValidationError

from vld.vak.errors import VakSourceError

from ._http import DEFAULT_BASE_URL, HEADERS, httpx

if TYPE_CHECKING:
    from collections.abc import Iterator

# Every edition of the list is a file of one news item with this mark and title.
LIST_MARK = 46
LIST_TITLE = (
    "Перечень рецензируемых научных изданий, в которых должны быть опубликованы"
)
_NEWS_TYPE = 19
_PAGE_SIZE = 50
# Two dozen news items today; a site that keeps answering «next» is broken.
_MOST_PAGES = 20


class ArchiveFile(BaseModel):
    """A file of the news item: the current edition or a past one.

    Attributes:
        url: str - Where to fetch it.
        name: str - File name on the site.
        size: int | None - Size in bytes, when the site gives it.

    """

    model_config: ClassVar[ConfigDict] = ConfigDict(frozen=True, extra="ignore")

    url: str
    name: str
    size: int | None = None


class VakListing(BaseModel):
    """The news item of the list.

    Attributes:
        news_id: str - Id of the news item.
        published_at: datetime - When the item was last published.
        current_url: str - The file the text of the item links: the current edition.
        files: tuple[ArchiveFile, ...] - Every file of the item, as the site lists them.

    """

    model_config: ClassVar[ConfigDict] = ConfigDict(frozen=True)

    news_id: str
    published_at: datetime
    current_url: str
    files: tuple[ArchiveFile, ...]


class _Mark(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(extra="ignore")

    id: int


class _News(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(extra="ignore")

    id: str
    name: str
    date_published: datetime
    marks: list[_Mark]
    info: str = ""
    files: list[ArchiveFile] = []


class _Page(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(extra="ignore")

    next: str | None
    results: list[_News]


async def fetch_listing(
    client: httpx.AsyncClient,
    *,
    base_url: str = DEFAULT_BASE_URL,
) -> VakListing:
    """Find the news item of the list and the file its text links.

    Old items of the list are still on the site under the same mark and title;
    their text links no file, so the one that does is the list. The site's «next»
    link points inside its own network, so pages are counted here, not followed.

    Args:
        client: httpx.AsyncClient - Timeouts and proxies are the caller's.
        base_url: str - The site, for tests.

    Returns:
        VakListing - The item, its current file and its archive.

    Raises:
        VakSourceError: If the site does not answer, answers something else, or
            shows no item of the list linking a PDF, or several.

    """
    candidates: list[tuple[_News, str]] = []
    for number in range(1, _MOST_PAGES + 1):
        page = await _page(client, base_url, number)
        for news in page.results:
            link = next(_pdf_links(news.info), None) if _is_the_list(news) else None
            if link is not None:
                candidates.append((news, link))
        if page.next is None:
            break
    else:
        msg = f"news-list still has a next page after {_MOST_PAGES}"
        raise VakSourceError(msg)
    if len(candidates) != 1:
        shown = [
            (news.id, news.date_published.date().isoformat()) for news, _ in candidates
        ]
        msg = f"expected one news item of the list linking a PDF, found {shown}"
        raise VakSourceError(msg)
    [(news, current)] = candidates
    return VakListing(
        news_id=news.id,
        published_at=news.date_published,
        current_url=current,
        files=tuple(news.files),
    )


async def _page(client: httpx.AsyncClient, base_url: str, number: int) -> _Page:
    url = f"{base_url}/api/news/news-list"
    params = {"page": number, "pageSize": _PAGE_SIZE, "type": _NEWS_TYPE}
    try:
        response = await client.get(url, params=params, headers=HEADERS)
    except httpx.HTTPError as error:
        msg = f"news-list did not answer: {type(error).__name__}"
        raise VakSourceError(msg) from error
    if not response.is_success:
        msg = f"news-list answered {response.status_code}"
        raise VakSourceError(msg)
    try:
        return _Page.model_validate_json(response.content)
    except ValidationError as error:
        msg = "news-list answered in another shape"
        raise VakSourceError(msg) from error


def _is_the_list(news: _News) -> bool:
    return any(mark.id == LIST_MARK for mark in news.marks) and news.name.startswith(
        LIST_TITLE,
    )


def _pdf_links(info: str) -> Iterator[str]:
    try:
        nodes = cast("object", json.loads(info))
    except json.JSONDecodeError:
        return
    yield from _hrefs(nodes)


def _hrefs(node: object) -> Iterator[str]:
    if isinstance(node, list):
        for child in cast("list[object]", node):
            yield from _hrefs(child)
    elif isinstance(node, dict):
        element = cast("dict[str, object]", node)
        attributes = element.get("attributes")
        if element.get("type") == "a" and isinstance(attributes, dict):
            href = cast("dict[str, object]", attributes).get("href")
            if isinstance(href, str) and href.lower().endswith(".pdf"):
                yield href
        yield from _hrefs(element.get("children"))
