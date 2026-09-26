"""Console sender: letters to the log, never in production."""

from __future__ import annotations

import pytest
from structlog.testing import capture_logs

from vld.auth.infrastructure.email import (
    ConsoleEmailSender,
    ConsoleEmailSenderInProductionError,
)
from vld.core.config import AppSettings


def test_production_refuses_the_console_sender() -> None:
    """In production the log would leak working links."""
    with pytest.raises(ConsoleEmailSenderInProductionError):
        _ = ConsoleEmailSender(AppSettings(env="production"))


async def test_the_link_reaches_the_log_and_the_terminal(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Locally the token is shown, so a developer can follow the link."""
    sender = ConsoleEmailSender(AppSettings(env="local"))

    with capture_logs() as logs:
        await sender.send_password_reset("u@b.co", "tok")

    assert logs[0]["event"] == "password_reset_email"
    assert logs[0]["token"] == "tok"
    assert "token=tok" in capsys.readouterr().out
