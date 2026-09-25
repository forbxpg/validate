"""Mechanism of throttling: the limiter itself and buckets by the client address."""

from __future__ import annotations

from ._client_ip import client_ip
from ._throttle import (
    Limiter,
    throttle_by_ip,
    throttle_by_ip_fail_open,
)

__all__ = (
    "Limiter",
    "client_ip",
    "throttle_by_ip",
    "throttle_by_ip_fail_open",
)
