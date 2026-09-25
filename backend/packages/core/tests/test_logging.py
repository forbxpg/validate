from __future__ import annotations

import json
from typing import TYPE_CHECKING, cast

import structlog

from vld.core.config import ObservabilitySettings
from vld.core.obs import configure_logging

if TYPE_CHECKING:
    import pytest


def _records(capsys: pytest.CaptureFixture[str]) -> list[dict[str, object]]:
    captured = capsys.readouterr()
    records: list[dict[str, object]] = []
    for line in (captured.out + captured.err).splitlines():
        try:
            records.append(cast("dict[str, object]", json.loads(line)))
        except ValueError:
            continue
    return records


def test_info_records_reach_the_output(capsys: pytest.CaptureFixture[str]) -> None:
    configure_logging(ObservabilitySettings(log_level="INFO", log_json=True))
    log: structlog.stdlib.BoundLogger = structlog.stdlib.get_logger("probe")
    log.info("http_error_response", status=401)
    assert any(r["event"] == "http_error_response" for r in _records(capsys))


def test_the_configured_level_actually_filters(
    capsys: pytest.CaptureFixture[str],
) -> None:
    configure_logging(ObservabilitySettings(log_level="WARNING", log_json=True))
    log: structlog.stdlib.BoundLogger = structlog.stdlib.get_logger("probe")
    log.info("below_threshold")
    log.warning("above_threshold")
    events = [r["event"] for r in _records(capsys)]
    assert "below_threshold" not in events
    assert "above_threshold" in events


def test_json_format_is_machine_readable(capsys: pytest.CaptureFixture[str]) -> None:
    configure_logging(ObservabilitySettings(log_level="INFO", log_json=True))
    log: structlog.stdlib.BoundLogger = structlog.stdlib.get_logger("probe")
    log.info("http_error_response", status=429)
    record = next(r for r in _records(capsys) if r["event"] == "http_error_response")
    assert record["status"] == 429
    assert record["level"] == "info"


def test_request_id_from_contextvars_lands_in_the_record(
    capsys: pytest.CaptureFixture[str],
) -> None:
    configure_logging(ObservabilitySettings(log_level="INFO", log_json=True))
    log: structlog.stdlib.BoundLogger = structlog.stdlib.get_logger("probe")
    structlog.contextvars.clear_contextvars()
    _ = structlog.contextvars.bind_contextvars(request_id="deadbeef")
    try:
        log.info("some_event")
    finally:
        structlog.contextvars.clear_contextvars()
    record = next(r for r in _records(capsys) if r["event"] == "some_event")
    assert record["request_id"] == "deadbeef"
