"""Exceptions for Crossref async API client."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    ErrorDetails = dict[str, object] | list[object] | None


class CrossrefAPIError(Exception):
    """Base exception for Crossref API errors."""

    default_status_code: int = 500
    default_message: str = "Внутренняя ошибка Crossref API"

    def __init__(
        self,
        message: str | None = None,
        status_code: int | None = None,
        *,
        details: ErrorDetails | None = None,
    ) -> None:
        self.status_code: int = status_code or type(self).default_status_code
        self.message: str = message or type(self).default_message
        self.details: ErrorDetails | None = details
        super().__init__(self.message)

    def to_dict(self) -> dict[str, object]:
        """Return structured payload that can be used in HTTP response body.

        Returns:
            Serialized error payload.

        """
        payload: dict[str, object] = {
            "status_code": self.status_code,
            "message": self.message,
        }
        if self.details is not None:
            payload["details"] = self.details

        return payload


class CrossrefRateLimitError(CrossrefAPIError):
    """Exception for rate limit errors."""

    default_status_code: int = 429
    default_message: str = "Превышен лимит запросов Crossref API"


class CrossrefClientError(CrossrefAPIError):
    """Exception for 4xx client errors."""

    default_status_code: int = 400
    default_message: str = "Ошибка при запросе Crossref API"


class CrossrefServerError(CrossrefAPIError):
    """Exception for 5xx server errors."""

    default_status_code: int = 500
    default_message: str = "Сервер Crossref API вернул ошибку"


class CrossrefRequestTimeoutError(CrossrefAPIError):
    """Exception for request timeout errors."""

    default_status_code: int = 408
    default_message: str = "Таймаут при запросе Crossref API"


class CrossrefNotFoundError(CrossrefAPIError):
    """Exception for not found errors."""

    default_status_code: int = 404
    default_message: str = "Не найдено ни одного результата для запроса."


class CrossrefMaxOffsetError(CrossrefAPIError):
    """Exception for max offset errors."""

    default_status_code: int = 400
    default_message: str = "Превышено максимальное значение offset для запроса."


class CrossrefUrlSyntaxError(CrossrefAPIError):
    """Exception for URL syntax errors."""

    default_status_code: int = 400
    default_message: str = "Некорректный URL для запроса."
