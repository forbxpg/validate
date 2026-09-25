"""Error tracking setup from `ObservabilitySettings`."""

from __future__ import annotations

from typing import TYPE_CHECKING

import sentry_sdk

if TYPE_CHECKING:
    from vld.core.config import ObservabilitySettings


def configure_sentry(settings: ObservabilitySettings) -> None:
    """Start Sentry or GlitchTip when a DSN is set.

    The SDK reads the environment name from `SENTRY_ENVIRONMENT` itself.

    Args:
        settings: ObservabilitySettings - Observability settings.

    """
    if settings.sentry_dsn is None:
        return
    _ = sentry_sdk.init(
        dsn=settings.sentry_dsn.get_secret_value(),
        send_default_pii=False,
        include_local_variables=False,
        # Errors only: performance tracing is not worth its cost at this load.
        traces_sample_rate=0,
    )
