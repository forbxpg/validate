"""What every request to the site of VAK carries."""

from __future__ import annotations

from importlib.metadata import version

try:
    import httpx
except ModuleNotFoundError as error:
    _MISSING = (
        "vld.vak.download requires the 'download' extra: "
        "pip install 'vld-vak[download]'"
    )
    raise ModuleNotFoundError(_MISSING, name=error.name) from error

__all__ = ("DEFAULT_BASE_URL", "HEADERS", "httpx")

DEFAULT_BASE_URL = "https://vak.gisnauka.ru"
# Who asks, so that VAK can see it and write to us.
HEADERS = {
    "User-Agent": f"vld-vak/{version('vld-vak')} (+https://github.com/forbxpg/validate)",
}
