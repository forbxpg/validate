"""Metrics of the worker, scraped by Prometheus from its own port."""

from __future__ import annotations

from prometheus_client import Counter, Histogram

OUTBOX_CLAIMED = Counter(
    "vld_worker_outbox_claimed",
    "Outbox rows claimed for publishing.",
    ["table"],
)
OUTBOX_PUBLISHED = Counter(
    "vld_worker_outbox_published",
    "Outbox rows published to the broker.",
    ["table"],
)
OUTBOX_FAILED = Counter(
    "vld_worker_outbox_failed",
    "Outbox rows marked failed: no handler knows their event.",
    ["table"],
)
OUTBOX_DEFERRED = Counter(
    "vld_worker_outbox_deferred",
    "Outbox rows put back for a later attempt after a failed publish.",
    ["table"],
)
OUTBOX_SWEPT = Counter(
    "vld_worker_outbox_swept",
    "Outbox rows released by the sweep after being left claimed.",
    ["table"],
)
RELAY_TURN_FAILURES = Counter(
    "vld_worker_relay_turn_failures",
    "Relay turns that failed as a whole.",
)
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
