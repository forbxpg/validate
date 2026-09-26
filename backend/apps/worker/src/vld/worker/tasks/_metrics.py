"""Metrics of the letters, scraped by Prometheus from the worker port."""

from __future__ import annotations

from prometheus_client import Counter, Histogram

LETTERS = Counter(
    "vld_worker_letters",
    "Letters by outcome: sent, dropped (never retried), failed (retried).",
    ["event", "outcome"],
)
LETTER_SECONDS = Histogram(
    "vld_worker_letter_seconds",
    "Time to prepare and send one letter.",
    ["event"],
)
