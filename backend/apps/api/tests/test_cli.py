"""`vld-api run` turns its options into one uvicorn call."""

from __future__ import annotations

import pytest
import uvicorn
from typer.testing import CliRunner

from vld.api.cli import app

ALL_INTERFACES = "0.0.0.0"  # ruff: ignore[hardcoded-bind-all-interfaces] -- a container binds every interface


@pytest.fixture
def served(monkeypatch: pytest.MonkeyPatch) -> list[dict[str, object]]:
    """Catch the uvicorn call instead of serving."""
    calls: list[dict[str, object]] = []

    def _run(target: str, **options: object) -> None:
        calls.append({"target": target, **options})

    monkeypatch.setattr(uvicorn, "run", _run)
    return calls


def test_run_serves_the_factory_on_localhost_by_default(
    served: list[dict[str, object]],
) -> None:
    """Loopback unless told otherwise; the factory reads settings at start."""
    result = CliRunner().invoke(app, ["run"])

    assert result.exit_code == 0, result.output
    [call] = served
    assert call["target"] == "vld.api.main:create_app"
    assert call["factory"] is True
    assert (call["host"], call["port"]) == ("127.0.0.1", 8000)
    assert (call["reload"], call["workers"]) == (False, 1)
    assert call["log_config"] is None


def test_run_passes_the_options(served: list[dict[str, object]]) -> None:
    """Host, port, reload and trusted proxies reach uvicorn."""
    result = CliRunner().invoke(
        app,
        [
            "run",
            "--host",
            ALL_INTERFACES,
            "--port",
            "8010",
            "--reload",
            "--forwarded-allow-ips",
            "10.0.0.1",
        ],
    )

    assert result.exit_code == 0, result.output
    [call] = served
    assert (call["host"], call["port"], call["reload"]) == (ALL_INTERFACES, 8010, True)
    assert call["forwarded_allow_ips"] == "10.0.0.1"


@pytest.mark.parametrize(
    "argv",
    [["run", "--reload", "--workers", "2"], ["run", "--workers", "0"]],
)
def test_contradictions_exit_2(
    argv: list[str],
    served: list[dict[str, object]],
) -> None:
    """Refused before uvicorn starts."""
    result = CliRunner().invoke(app, argv)

    assert result.exit_code == 2
    assert served == []
