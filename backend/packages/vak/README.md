# vld-vak

The VAK list (Перечень рецензируемых научных изданий) as typed data: a parser of its
PDF that reads every journal, ISSN and speciality with its dates, and says where it
had doubts instead of dropping anything; and a downloader that finds the current
edition on vak.gisnauka.ru.

The library is standalone: it imports `pydantic`, `pdfplumber` (the `parser` extra),
`httpx` (the `download` extra) and the standard library, never another `vld`
package. Import-linter contracts in the root `pyproject.toml` hold that and keep the
extras out of the result models.

- [Install](#install) · [Use](#use) · [The result](#the-result)
- [Warnings](#warnings) · [How the PDF is read](#how-the-pdf-is-read)
- [Download](#download) · [Layout](#layout) · [Tests](#tests)

## Install

```bash
pip install vld-vak               # the result models: read a stored parse (pydantic)
pip install 'vld-vak[parser]'     # plus the parser (pdfplumber)
pip install 'vld-vak[download]'   # plus the downloader (httpx)
pip install 'vld-vak[all]'        # everything
```

In this workspace `uv sync --all-packages` installs everything. Importing
`vld.vak.parser` or `vld.vak.download` without its extra fails with the command that
installs it.

## Use

```python
from pathlib import Path

from vld.vak.models import VakList
from vld.vak.parser import parse

edition = parse(Path("list.pdf").read_bytes())  # about a minute: run it in a thread
print(edition.edition_date, len(edition.journals), len(edition.warnings))

stored = edition.model_dump_json()  # the JSON format, version 1
again = VakList.model_validate_json(stored)  # needs only the base install
```

`parse` takes bytes, not a path. It refuses with `NotVakListError` only what is not
a VAK list: not a PDF, no table header or no «по состоянию на» date on page 1. Any
other problem is a warning.

## The result

```
VakList         format_version (1), parser_version, edition_date, page_count,
                journals, warnings
VakJournal      number, pages, title, issn_printed, issns, groups
VakTitle        printed, main, translation, former (until, title, issns)
SpecialityGroup dates_printed, included («с»), excluded («по»), specialities
Speciality      code, name, branch, printed
ParseWarning    code, page, number, printed, message
```

- ISSNs are normalized to `NNNN-NNNC`, all of a cell in print order. The PDF does not
  say which is print and which electronic, so neither does the result.
- A former title («до 22.12.2020 наименование в Перечне «…» ISSN …») keeps its ISSNs:
  they link a journal to itself across a change of ISSN.
- Specialities stay in their printed groups; a group shares one date cell.
- `code` is `5.9.5` (the 2021 nomenclature) or `10.02.01` (the old one); the format
  of the code tells which.
- `branch` is one of 24 `ScienceBranch` values with Latin names, or `None` when the
  bracket could not be read. A bracket listing two branches gives two specialities.
- Every model is frozen and refuses unknown fields; a JSON of another
  `format_version` is refused.

## Warnings

A code ending in `_repaired` reports a repair that was made: the printed text and the
repaired value are both in the result. Every other code reports something left as
printed.

| Code | When |
|---|---|
| `column_shift` | a page's long rulings differ from the document's column bounds; read by the bounds anyway |
| `row_unrecognized` | a row belongs to no journal and is no header |
| `numbering_gap` | journal numbers skip or repeat (once for the document) |
| `title_unparsed` | a translation or former title bracket that matches no pattern |
| `title_repaired` | a former title or translation bracket closed at the end of the cell |
| `issn_missing` | empty ISSN cell |
| `issn_unrecognized` | text in the ISSN cell that is not an ISSN |
| `issn_checksum` | an ISSN whose check digit is wrong; kept |
| `issn_repaired` | a Cyrillic «Х», another dash or spaces inside an ISSN |
| `journal_without_specialities` | a journal with no speciality read |
| `speciality_unrecognized` | text in the speciality cell before any code |
| `branch_missing` | a speciality without a branch bracket |
| `branch_unknown` | a bracket that is not a branch of the list or its synonyms |
| `branch_repaired` | a branch read through a synonym, a repair, or a bracket not opened or closed |
| `date_unrecognized` | a date cell with more than one reading, or a group without a date |
| `date_repaired` | a date misprint with one reading (`01.022022`, `п о`, `до`, a capital «С») |

The editions of 30.03.2026 and 15.09.2026 give about 220 warnings each, 35 journals
of 3 200 with a warning that is not a repair.

## How the PDF is read

1. Page 1: the header and the edition date. The column bounds are the long vertical
   rulings of the first page that has five columns; short rulings inside a cell do not
   count.
2. Every page: one table extraction with those bounds as explicit lines, so a stray
   line cannot move the ISSN into the title column.
3. Rows become journals: a number starts one; a row without a number continues it; a
   date cell starts a speciality group; a row without a date continues the group, so a
   speciality cut by a row or a page break is joined again.
4. Each cell is read by its own rules (`parser/_title.py`, `_issn.py`,
   `_specialities.py`, `_branches.py`, `_dates.py`).

A new misprint of a branch goes into `SYNONYMS` of `parser/_branches.py` with a test;
until then it is `branch_unknown`.

## Download

```python
import httpx

from vld.vak.download import fetch_listing, fetch_pdf
from vld.vak.parser import parse

async with httpx.AsyncClient(timeout=120, follow_redirects=True) as client:
    listing = await fetch_listing(client)
    pdf = await fetch_pdf(client, listing.current_url)
edition = parse(pdf.data)
```

- The list is one news item on the site (mark 46, «Перечень рецензируемых научных
  изданий, в которых должны быть опубликованы…») whose files keep every past edition
  (`listing.files`, about 80). Items of 2018 and 2019 carry the same mark and title but
  link no file in their text; the item that links a PDF is the list. None or several
  is `VakSourceError`.
- The current edition is the first PDF linked in the text of the item. Its date is
  read from page 1 by the parser, not from the news, whose date is not the edition's.
- `GET /api/news/news-list` without a trailing slash: with one the site answers 404.
  Pages are counted here: the site's «next» link points inside its own network.
- `fetch_pdf` streams with a 50 MB cap, checks the `%PDF-` signature and returns the
  bytes with their size and SHA-256. Failures are `VakDownloadError` with the URL.
- The client is the caller's: timeouts, proxies, redirects. Requests carry
  `User-Agent: vld-vak/<version> (+https://github.com/forbxpg/validate)`. No retries: a
  person runs it again.

## Layout

```
models/        the result, format v1 (pydantic only)
errors/        VakError, NotVakListError, VakSourceError, VakDownloadError
parser/
  _parse.py         parse(): bytes to VakList
  _extract.py       pdfplumber: rows of five cells, edition date, column bounds
  _assemble.py      rows to journals
  _title.py _issn.py _specialities.py _branches.py _dates.py   one cell each
  _finding.py       a finding of a cell reader
download/
  _listing.py       fetch_listing(): the news item, its current file and archive
  _pdf.py           fetch_pdf(): one file, capped and checked
  _http.py          the base URL and the User-Agent
```

## Tests

```bash
uv run pytest packages/vak                                    # unit tests and the sample
VAK_PDF_PATH=/path/to/list.pdf uv run pytest packages/vak -m vak_full   # a whole edition
```

`tests/fixtures/sample.pdf` holds 19 pages of the edition of 15.09.2026, one or two
per quirk; `sample.json` is what the parser reads there. A change in how the parser
reads the list changes `sample.json`; `test_the_version_guard` then fails until the
version of vld-vak is raised and it and the new hash are put into
`tests/fixtures/manifest.json`. Rebuild the sample from a whole edition with
`tests/fixtures/cut_pages.py` (its docstring says how) and read the diff of
`sample.json` before committing it. Every parser bug fixed adds a page to the sample.
