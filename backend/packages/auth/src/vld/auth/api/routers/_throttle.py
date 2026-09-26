"""Limits of the second rate-limit bucket: by the client address."""

from __future__ import annotations

# Thousands of honest users sit behind a mobile NAT; the email bucket catches guessing.
LOGIN_IP_LIMIT = 30
LOGIN_IP_WINDOW_MS = 15 * 60_000

# Registration is expensive and legitimately repeats a few times at most.
REGISTER_IP_LIMIT = 10
REGISTER_IP_WINDOW_MS = 60 * 60_000

# Every request sends a letter to someone's address, so the limit is below registration.
RESEND_IP_LIMIT = 5
RESEND_IP_WINDOW_MS = 60 * 60_000

# Without a limit the reset form mails any address.
PASSWORD_RESET_IP_LIMIT = 5
PASSWORD_RESET_IP_WINDOW_MS = 60 * 60_000

# Every request with a valid token runs bcrypt; the limit is at the login level.
PASSWORD_RESET_CONFIRM_IP_LIMIT = 30
PASSWORD_RESET_CONFIRM_IP_WINDOW_MS = 15 * 60_000
