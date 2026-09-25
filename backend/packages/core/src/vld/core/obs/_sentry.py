"""Set up Sentry/GlitchTip from ``ObservabilitySettings``."""

from __future__ import annotations

from typing import TYPE_CHECKING

import sentry_sdk

from ._redaction import redact_secrets

if TYPE_CHECKING:
    from sentry_sdk.types import Event, Hint

    from vld.core.config import ObservabilitySettings


def _redact_event(event: Event, hint: Hint) -> Event:
    """Redact secret in the address of the event before sending to the tracker.

    Args:
        event: Event - Event collected by the SDK.
        hint: Hint - SDK hints.

    Returns:
        Event - The same event with the secret redacted.

    """
    del hint
    request = event.get("request")
    if isinstance(request, dict):
        url = request.get("url")
        if isinstance(url, str):
            request["url"] = redact_secrets(url)
    transaction = event.get("transaction")
    if isinstance(transaction, str):
        event["transaction"] = redact_secrets(transaction)
    return event


def configure_sentry(settings: ObservabilitySettings, env: str) -> None:
    """Raise the error tracker if the DSN is set.

    Args:
        settings: ObservabilitySettings - Observability settings.
        env: str - Environment (`APP_ENV`).

    """
    if settings.sentry_dsn is None:
        return
    _ = sentry_sdk.init(
        dsn=settings.sentry_dsn.get_secret_value(),
        environment=env,
        send_default_pii=False,
        include_local_variables=False,
        # Tracing answers the questions about performance, which
        # there is no load and volume of storage. It's not worth it.
        traces_sample_rate=0,
        before_send=_redact_event,
        before_send_transaction=_redact_event,
    )
