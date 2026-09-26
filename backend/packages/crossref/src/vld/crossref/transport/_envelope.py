from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Self, cast

from vld.crossref.errors import CrossrefSchemaError, ValidationProblem

if TYPE_CHECKING:
    from httpx import Response

_STATUS_OK = "ok"


@dataclass(frozen=True, slots=True)
class Envelope:
    """A successful answer before its message is read by a resource.

    Attributes:
        message_type: str - `work`, `work-list`, `journal` and so on.
        message_version: str - Version of the message format.
        message: object - The raw message.

    """

    message: object
    message_type: str
    message_version: str

    @classmethod
    def from_response(cls, response: Response, *, route: str, url: str) -> Self:
        """Read the envelope of a 200 answer.

        Args:
            response: Response - The answer.
            route: str - Path of the request, for the error.
            url: str - Request URL without `mailto`, for the error.

        Returns:
            Envelope - The envelope.

        Raises:
            CrossrefSchemaError: If the body is not JSON, not an object, has no
                `message` or its `status` is not `ok`.

        """
        try:
            body = cast("object", response.json())
        except ValueError as err:
            detail = "body is not JSON"
            raise CrossrefSchemaError(route=route, url=url, detail=detail) from err

        if not isinstance(body, dict):
            detail = "body is not an object"
            raise CrossrefSchemaError(route=route, url=url, detail=detail)

        fields = cast("dict[str, object]", body)
        status = fields.get("status")
        if not status or status != _STATUS_OK:
            detail = f"status is not {_STATUS_OK}. Got status: {status!r}"
            raise CrossrefSchemaError(route=route, url=url, detail=detail)

        if "message" not in fields:
            detail = "body has no `message`."
            raise CrossrefSchemaError(route=route, url=url, detail=detail)

        return cls(
            message=fields["message"],
            message_type=str(fields.get("message-type", "")),
            message_version=str(fields.get("message-version", "")),
        )

    @staticmethod
    def parse_problems(response: Response) -> tuple[ValidationProblem, ...]:
        """Read the complaints of a 400 answer; plain text becomes one complaint.

        Args:
            response: httpx.Response - The 400 answer.

        Returns:
            tuple[ValidationProblem, ...] - What Crossref refused.

        """
        try:
            body = cast("object", response.json())
        except ValueError:
            return (ValidationProblem(type="unknown", value="", message=response.text),)
        fields = cast("dict[str, object]", body) if isinstance(body, dict) else {}
        items = fields.get("message")
        if not isinstance(items, list):
            return (ValidationProblem(type="unknown", value="", message=response.text),)

        problems: list[ValidationProblem] = []
        for item in cast("list[object]", items):
            if isinstance(item, dict):
                entry = cast("dict[str, object]", item)
                problems.append(
                    ValidationProblem(
                        type=str(entry.get("type", "")),
                        value=str(entry.get("value", "")),
                        message=str(entry.get("message", "")),
                    ),
                )
        return tuple(problems)
