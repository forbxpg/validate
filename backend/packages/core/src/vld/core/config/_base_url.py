"""Normalization of the base URL to the form from which the origin is collected."""

from __future__ import annotations


def normalized_base_url(value: str) -> str:
    """Reject the address from which the origin cannot be collected and bring the register.

    Args:
        value: str - The address from the environment.

    Returns:
        str - The same.

    Raises:
        ValueError: if the scheme or host is missing.

    """
    scheme, _, rest = value.partition("://")
    host, slash, path = rest.partition("/")
    if scheme.lower() not in {"http", "https"} or not host:
        msg = "base url must look like https://example.com"
        raise ValueError(msg)
    return f"{scheme.lower()}://{host.lower()}{slash}{path}".rstrip("/")
