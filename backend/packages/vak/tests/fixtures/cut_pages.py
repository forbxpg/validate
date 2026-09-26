"""Cut the fixture pages out of a whole VAK list and write what the parser reads there.

Run from `backend/` with the edition of 15.09.2026 (the current file of the VAK news
on that day, SHA-256 d16ab69668fb4c4c…):

    uv run python packages/vak/tests/fixtures/cut_pages.py /path/to/list.pdf

It writes `sample.pdf` and `sample.json` next to itself and prints the SHA-256 of
`sample.json`. Read the diff of `sample.json` before committing it, then put the hash
and the parser version into `manifest.json` by hand: the version guard fails until
then.
"""

from __future__ import annotations

import hashlib
import io
import sys
from pathlib import Path

import pypdf

from vld.vak.parser import parse

# Page 1 carries the header and the edition date, so it comes first. Each other page
# shows one quirk of the list; neighbours are kept where a journal crosses a page.
PAGES = (1, 2, 3, 4, 5, 15, 16, 25, 26, 56, 58, 77, 87, 100, 155, 659, 832, 842, 975)
HERE = Path(__file__).parent


def main() -> None:
    """Write the fixture PDF and its expected parse, print the hash for the manifest."""
    source = pypdf.PdfReader(sys.argv[1])
    writer = pypdf.PdfWriter()
    for number in PAGES:
        _ = writer.add_page(source.pages[number - 1])
    writer.compress_identical_objects(remove_duplicates=True, remove_unreferenced=True)
    buffer = io.BytesIO()
    _ = writer.write(buffer)
    data = buffer.getvalue()
    _ = (HERE / "sample.pdf").write_bytes(data)
    expected = parse(data).model_dump_json(indent=2, exclude={"parser_version"}) + "\n"
    _ = (HERE / "sample.json").write_text(expected, encoding="utf-8")
    digest = hashlib.sha256(expected.encode()).hexdigest()
    _ = sys.stdout.write(f"sample.json sha256: {digest}\n")


if __name__ == "__main__":
    main()
