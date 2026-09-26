"""Fetching one file of the list: streamed, capped, checked to be a PDF."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import cast

from vld.vak.errors import VakDownloadError

from ._http import HEADERS, httpx

# An edition weighs about 10.5 MB; five times that is no list.
MAX_PDF_BYTES = 50 * 1024 * 1024


@dataclass(frozen=True, slots=True)
class VakPdf:
    """A fetched file.

    Attributes:
        url: str - Where it came from.
        data: bytes - The PDF.
        size: int - Its size in bytes.
        sha256: str - Hex digest: the identity of the document.

    """

    url: str
    data: bytes
    size: int
    sha256: str


async def fetch_pdf(client: httpx.AsyncClient, url: str) -> VakPdf:
    """Fetch a file of the list.

    Args:
        client: httpx.AsyncClient - Timeouts, proxies and redirects are the caller's.
        url: str - The file, such as `VakListing.current_url`.

    Returns:
        VakPdf - The bytes, their size and SHA-256.

    Raises:
        VakDownloadError: If the site answers another status, times out, sends
            more than 50 MB or something that is not a PDF.

    """
    try:
        data = await _read(client, url)
    except httpx.HTTPError as error:
        raise VakDownloadError(type(error).__name__, url=url) from error
    if not data.startswith(b"%PDF-"):
        msg = "not a PDF"
        raise VakDownloadError(msg, url=url)
    return VakPdf(
        url=url,
        data=data,
        size=len(data),
        sha256=hashlib.sha256(data).hexdigest(),
    )


async def _read(client: httpx.AsyncClient, url: str) -> bytes:
    data = bytearray()
    async with client.stream("GET", url, headers=HEADERS) as response:
        if not response.is_success:
            msg = f"answered {response.status_code}"
            raise VakDownloadError(msg, url=url)
        encoding = cast("str", response.headers.get("Content-Encoding", "identity"))
        if encoding.lower() != "identity":
            msg = f"compressed ({encoding}) though asked for identity"
            raise VakDownloadError(msg, url=url)
        async for chunk in response.aiter_bytes():
            if len(data) + len(chunk) > MAX_PDF_BYTES:
                msg = f"larger than {MAX_PDF_BYTES} bytes"
                raise VakDownloadError(msg, url=url)
            data.extend(chunk)
    return bytes(data)
