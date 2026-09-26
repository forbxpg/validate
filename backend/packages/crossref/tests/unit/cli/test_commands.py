"""The commands end to end over a fake Crossref: exit code, stdout, stderr."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, cast

import httpx
import pytest
from crossref_support import FakeCrossref, fixture, listing, make_client
from typer.testing import CliRunner

from vld.crossref import RetryPolicy
from vld.crossref.cli import _works
from vld.crossref.cli._app import app

if TYPE_CHECKING:
    from pathlib import Path

    from typer.testing import Result

    from vld.crossref import CrossrefClient
    from vld.crossref.cli._settings import CliSettings

PRL = "/works/10.1103/physrevlett.1.1"

pytestmark = pytest.mark.usefixtures("isolated")


def _invoke(fake: FakeCrossref, *args: str, retry: RetryPolicy | None = None) -> Result:
    def factory(settings: CliSettings) -> CrossrefClient:
        del settings
        return make_client(fake, retry=retry)

    return CliRunner().invoke(app, list(args), obj=factory)


def _work_message() -> dict[str, object]:
    return cast("dict[str, dict[str, object]]", fixture("work_journal_article"))[
        "message"
    ]


def test_get_prints_the_work_as_json_off_a_terminal() -> None:
    """A script gets the record with Crossref's field names."""
    fake = FakeCrossref().on(
        "GET",
        PRL,
        httpx.Response(200, json=fixture("work_journal_article")),
    )

    result = _invoke(fake, "works", "get", "https://doi.org/10.1103/PhysRevLett.1.1")

    assert result.exit_code == 0
    assert json.loads(result.stdout)["DOI"] == "10.1103/physrevlett.1.1"
    assert "public pool" in result.stderr


def test_get_of_an_unknown_doi_exits_1() -> None:
    """Not found is an answer, not a crash."""
    result = _invoke(FakeCrossref(), "works", "get", "10.9999/nothing")

    assert result.exit_code == 1
    assert not result.stdout
    assert "not found" in result.stderr


def test_exists_answers_with_its_exit_code() -> None:
    """0 for yes, 1 for no."""
    fake = FakeCrossref().on("HEAD", PRL, httpx.Response(200))

    found = _invoke(fake, "works", "exists", "10.1103/PhysRevLett.1.1")
    missing = _invoke(FakeCrossref(), "works", "exists", "10.9999/nothing")

    assert (found.exit_code, json.loads(found.stdout)["exists"]) == (0, True)
    assert (missing.exit_code, json.loads(missing.stdout)["exists"]) == (1, False)


def test_search_sends_the_options_and_prints_the_page() -> None:
    """Field queries, shortcuts and --filter reach Crossref as one query."""
    fake = FakeCrossref().on("GET", "/works", listing([_work_message()], total=146))

    result = _invoke(
        fake,
        "works",
        "search",
        "graphene",
        "--author",
        "Geim",
        "--type",
        "journal-article",
        "--from",
        "2010",
        "--filter",
        "until-online-pub-date=2024",
        "--rows",
        "5",
    )

    assert result.exit_code == 0, result.stderr
    params = fake.requests[0].params
    assert params["query"] == "graphene"
    assert params["query.author"] == "Geim"
    assert params["rows"] == "5"
    assert set(params["filter"].split(",")) == {
        "type:journal-article",
        "from-pub-date:2010",
        "until-online-pub-date:2024",
    }
    document = json.loads(result.stdout)
    assert (document["total_results"], len(document["items"])) == (146, 1)


def test_search_of_a_journal_uses_its_works_route() -> None:
    """--journal switches the path, the rest stays."""
    route = "/journals/0031-9007/works"
    fake = FakeCrossref().on("GET", route, listing([_work_message()]))

    result = _invoke(
        fake,
        "works",
        "search",
        "--journal",
        "0031 9007",
        "--author",
        "Geim",
    )

    assert result.exit_code == 0, result.stderr
    assert fake.requests[0].path == route
    assert fake.requests[0].params["query.author"] == "Geim"


def test_a_bad_option_exits_2_before_any_request() -> None:
    """The query is checked on this side."""
    fake = FakeCrossref()

    result = _invoke(fake, "works", "search", "--filter", "from-pub-date=20x")

    assert result.exit_code == 2
    assert "not a date" in result.stderr
    assert fake.requests == []


def test_iterate_prints_one_json_line_per_record() -> None:
    """A walk streams; --max stops it."""
    fake = FakeCrossref().on(
        "GET",
        "/works",
        httpx.Response(200, json=fixture("works_cursor_first")),
        httpx.Response(200, json=fixture("works_cursor_second")),
    )

    result = _invoke(fake, "works", "iterate", "--prefix", "10.1103", "--max", "4")

    assert result.exit_code == 0, result.stderr
    lines = result.stdout.splitlines()
    assert len(lines) == 4
    assert all(json.loads(line)["DOI"].startswith("10.1103/") for line in lines)


def test_iterate_saves_json_lines_into_the_output_folder(tmp_path: Path) -> None:
    """--save-json with --out-dir; the path goes to stderr."""
    fake = FakeCrossref().on(
        "GET",
        "/works",
        httpx.Response(200, json=fixture("works_cursor_first")),
        httpx.Response(200, json=fixture("works_cursor_second")),
    )

    result = _invoke(
        fake,
        "works",
        "iterate",
        "--max",
        "4",
        "--save-json",
        "--out-dir",
        str(tmp_path / "out"),
    )

    assert result.exit_code == 0, result.stderr
    [saved] = list((tmp_path / "out").glob("works-iterate-*.jsonl"))
    assert len(saved.read_text().splitlines()) == 4
    assert str(saved.resolve()) in result.stderr.replace("\n", "")


def test_an_interrupted_walk_keeps_what_it_saved(tmp_path: Path) -> None:
    """Ctrl-C after two pages: exit 130, the records of both pages on disk."""

    def interrupt(request: httpx.Request) -> httpx.Response:
        del request
        raise KeyboardInterrupt

    fake = FakeCrossref().on(
        "GET",
        "/works",
        httpx.Response(200, json=fixture("works_cursor_first")),
        httpx.Response(200, json=fixture("works_cursor_second")),
        interrupt,
    )
    out = tmp_path / "walk.jsonl"

    result = _invoke(
        fake,
        "works",
        "iterate",
        "--all",
        "--page-size",
        "3",
        "--out",
        str(out),
    )

    assert result.exit_code == 130
    assert len(out.read_text().splitlines()) == 6
    assert "interrupted; 6 records saved" in result.stderr


def test_get_saves_one_json_document(tmp_path: Path) -> None:
    """--out names the file and implies saving."""
    fake = FakeCrossref().on(
        "GET",
        PRL,
        httpx.Response(200, json=fixture("work_journal_article")),
    )
    out = tmp_path / "prl.json"

    result = _invoke(fake, "works", "get", "10.1103/PhysRevLett.1.1", "--out", str(out))

    assert result.exit_code == 0, result.stderr
    assert json.loads(out.read_text())["DOI"] == "10.1103/physrevlett.1.1"


def test_rate_limits_exit_3_with_the_mailto_hint() -> None:
    """In the public pool the hint says how to get a bigger one."""
    fake = FakeCrossref().on("GET", PRL, httpx.Response(429))

    result = _invoke(
        fake,
        "works",
        "get",
        "10.1103/PhysRevLett.1.1",
        retry=RetryPolicy(attempts=1),
    )

    assert result.exit_code == 3
    assert "CROSSREF_MAILTO" in result.stderr


def test_debug_logs_stay_off_stdout() -> None:
    """With -v the library logs every request; stdout must still parse."""
    fake = FakeCrossref().on(
        "GET",
        PRL,
        httpx.Response(200, json=fixture("work_journal_article")),
    )

    result = _invoke(fake, "works", "get", "10.1103/PhysRevLett.1.1", "-v")

    assert result.exit_code == 0, result.stderr
    assert json.loads(result.stdout)["DOI"] == "10.1103/physrevlett.1.1"
    assert "crossref_request" in result.stderr


def test_filters_lists_every_filter() -> None:
    """The catalogue --filter takes."""
    result = CliRunner().invoke(app, ["works", "filters", "--json"])

    assert result.exit_code == 0
    names = {item["name"] for item in json.loads(result.stdout)}
    assert len(names) == 90
    assert "until-online-pub-date" in names


def test_journals_get_and_search() -> None:
    """The journals group over the recorded answers."""
    fake = (
        FakeCrossref()
        .on(
            "GET",
            "/journals/0031-9007",
            httpx.Response(200, json=fixture("journal_prl")),
        )
        .on("GET", "/journals", httpx.Response(200, json=fixture("journals_page")))
    )

    journal = _invoke(fake, "journals", "get", "00319007")
    page = _invoke(fake, "journals", "search", "physical review", "--rows", "5")

    assert journal.exit_code == 0, journal.stderr
    assert json.loads(journal.stdout)["title"] == "Physical Review Letters"
    assert page.exit_code == 0, page.stderr
    assert len(json.loads(page.stdout)["items"]) == 5
    assert fake.requests[-1].params["query"] == "physical review"


def test_iterate_without_max_stops_at_the_default(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A walk never runs through everything unless --all says so."""
    monkeypatch.setattr(_works, "DEFAULT_WALK", 4)
    fake = FakeCrossref().on(
        "GET",
        "/works",
        httpx.Response(200, json=fixture("works_cursor_first")),
        httpx.Response(200, json=fixture("works_cursor_second")),
    )

    result = _invoke(fake, "works", "iterate", "--prefix", "10.1103")

    assert result.exit_code == 0, result.stderr
    assert len(result.stdout.splitlines()) == 4


def test_page_bounds_and_a_bad_issn_exit_2_before_any_request() -> None:
    """Refused on this side: rows out of 1..1000, an ISSN with a wrong check digit."""
    fake = FakeCrossref()

    rows = _invoke(fake, "works", "search", "--rows", "0")
    issn = _invoke(fake, "works", "search", "--journal", "0031-9008")

    assert (rows.exit_code, issn.exit_code) == (2, 2)
    assert "check character" in issn.stderr
    assert fake.requests == []
