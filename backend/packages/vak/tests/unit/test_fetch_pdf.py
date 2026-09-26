"""Fetching a file: streamed, capped, checked to be a PDF."""

from __future__ import annotations

import hashlib
from typing import TYPE_CHECKING

import httpx
import pytest

from vld.vak.download import _pdf, fetch_pdf
from vld.vak.errors import VakDownloadError

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

CURRENT = "https://vak.test/s3-files/list.pdf"
PDF = b"%PDF-1.5\n" + b"x" * 1000


def _client(handler: httpx.MockTransport) -> httpx.AsyncClient:
    return httpx.AsyncClient(transport=handler)


async def test_a_pdf_is_fetched_with_its_size_and_hash() -> None:
    """The bytes as sent, and the SHA-256 that identifies the document."""
    async with _client(
        httpx.MockTransport(lambda _: httpx.Response(200, content=PDF)),
    ) as client:
        fetched = await fetch_pdf(client, CURRENT)

    assert (fetched.url, fetched.data, fetched.size) == (CURRENT, PDF, len(PDF))
    assert fetched.sha256 == hashlib.sha256(PDF).hexdigest()


async def test_a_file_that_is_no_pdf_is_an_error() -> None:
    """An HTML page in place of the file."""
    page = httpx.Response(200, text="<html>maintenance</html>")

    async with _client(httpx.MockTransport(lambda _: page)) as client:
        with pytest.raises(VakDownloadError, match="not a PDF") as raised:
            _ = await fetch_pdf(client, CURRENT)

    assert raised.value.url == CURRENT


async def test_another_status_is_an_error() -> None:
    """A file gone from the site."""
    async with _client(httpx.MockTransport(lambda _: httpx.Response(404))) as client:
        with pytest.raises(VakDownloadError, match="answered 404"):
            _ = await fetch_pdf(client, CURRENT)


async def test_a_file_over_the_cap_is_cut_off(monkeypatch: pytest.MonkeyPatch) -> None:
    """The cap stops the stream, not the end of it."""
    monkeypatch.setattr(_pdf, "MAX_PDF_BYTES", 100)

    async with _client(
        httpx.MockTransport(lambda _: httpx.Response(200, content=PDF)),
    ) as client:
        with pytest.raises(VakDownloadError, match="larger than 100 bytes"):
            _ = await fetch_pdf(client, CURRENT)


async def test_a_timeout_is_an_error() -> None:
    """A site that stops answering."""

    def stall(request: httpx.Request) -> httpx.Response:
        message = "slow"
        raise httpx.ReadTimeout(message, request=request)

    async with _client(httpx.MockTransport(stall)) as client:
        with pytest.raises(VakDownloadError, match="ReadTimeout"):
            _ = await fetch_pdf(client, CURRENT)


async def test_the_cap_stops_the_stream_before_its_end(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A file far over the cap is not read to its end first."""
    monkeypatch.setattr(_pdf, "MAX_PDF_BYTES", 5000)
    pulled = 0

    async def endless() -> AsyncIterator[bytes]:
        nonlocal pulled
        yield b"%PDF-1.5\n"
        for _ in range(10_000):
            pulled += 1
            yield b"x" * 1000

    transport = httpx.MockTransport(lambda _: httpx.Response(200, content=endless()))
    async with _client(transport) as client:
        with pytest.raises(VakDownloadError, match="larger than 5000 bytes"):
            _ = await fetch_pdf(client, CURRENT)

    assert pulled < 10
