"""One run of a command: settings, the client, output, saving and exit codes."""

from __future__ import annotations

import asyncio
import os
import sys
import traceback
import typing
from contextlib import ExitStack
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING

import typer
from pydantic import SecretStr
from rich.console import Console

from vld.crossref import (
    CrossrefBadRequestError,
    CrossrefBlockedError,
    CrossrefClient,
    CrossrefQueryError,
    CrossrefRateLimitedError,
    CrossrefUnavailableError,
    LocalThrottle,
    RateLimits,
)
from vld.crossref.transport import VERSION

from ._logs import configure_logs
from ._render import (
    dump,
    page_document,
    summary,
    write_document,
    write_line,
)
from ._save import JsonLinesFile, file_name, write_json
from ._settings import MAILTO_VARIABLE, CliSettings, resolve_settings

if TYPE_CHECKING:
    from collections.abc import AsyncIterator, Awaitable, Callable, Sequence

    from pydantic import BaseModel
    from rich.console import RenderableType

    from vld.crossref import Page

    from ._options import Common

    type ClientFactory = Callable[[CliSettings], CrossrefClient]
    type Action = Callable[[CrossrefClient, Output], Awaitable[int]]

EXIT_NOT_FOUND = 1
EXIT_QUERY = 2
EXIT_CROSSREF = 3
EXIT_INTERRUPTED = 130
_CHUNK = 20
"""Rows per table while a walk is shown in a terminal."""


def default_client(settings: CliSettings) -> CrossrefClient:
    """Build the client of the command line: the pool follows the identity.

    Args:
        settings: CliSettings - The settings of the run.

    Returns:
        CrossrefClient - A client, not opened yet.

    """
    if settings.plus_token:
        limits = RateLimits.PLUS
    elif settings.mailto:
        limits = RateLimits.POLITE
    else:
        limits = RateLimits.PUBLIC
    return CrossrefClient(
        mailto=settings.mailto,
        throttle=LocalThrottle(limits),
        app=f"vld-crossref-cli/{VERSION}",
        plus_token=SecretStr(settings.plus_token) if settings.plus_token else None,
    )


@dataclass
class Output:
    """Where a command prints and saves what it got.

    Attributes:
        common: Common - The shared options.
        settings: CliSettings - The settings of the run.
        stdout: Console - The console of the data.
        stderr: Console - The console of messages.
        started: datetime - When the command ran, for file names.
        saving: JsonLinesFile | None - The JSON Lines file of a walk being saved.

    """

    common: Common
    settings: CliSettings
    stdout: Console = field(default_factory=Console)
    stderr: Console = field(default_factory=lambda: Console(stderr=True))
    started: datetime = field(default_factory=lambda: datetime.now(tz=UTC))
    saving: JsonLinesFile | None = None

    @property
    def as_json(self) -> bool:
        """Whether the data goes out as JSON.

        Returns:
            bool - True with `--json` or when stdout is not a terminal.

        """
        return self.common.as_json or not self.stdout.is_terminal

    @property
    def saves(self) -> bool:
        """Whether the result is also saved.

        Returns:
            bool - True with `--save-json` or `--out`.

        """
        return self.common.save_json or self.common.out is not None

    def message(self, text: str) -> None:
        """Tell the person something on stderr.

        Args:
            text: str - The message.

        """
        self.stderr.print(text, markup=False, highlight=False)

    def _path(self, parts: Sequence[str], suffix: str) -> Path:
        if self.common.out is not None:
            return self.common.out
        return self.settings.output_dir / file_name(
            *parts,
            stamp=self.started,
            suffix=suffix,
        )

    def _save(self, parts: Sequence[str], document: object) -> None:
        if self.saves:
            path = self._path(parts, ".json")
            write_json(path, document)
            self.message(f"saved {path.resolve()}")

    def one(
        self,
        record: BaseModel,
        render: RenderableType,
        parts: Sequence[str],
    ) -> None:
        """Show and save one record.

        Args:
            record: BaseModel - The record.
            render: RenderableType - How it looks in a terminal.
            parts: Sequence[str] - Parts of the saved file name.

        """
        document = dump(record)
        if self.as_json:
            write_document(sys.stdout, document)
        else:
            self.stdout.print(render)
        self._save(parts, document)

    def fact(
        self,
        document: dict[str, object],
        text: str,
        parts: Sequence[str],
    ) -> None:
        """Show and save a small answer, such as whether a DOI exists.

        Args:
            document: dict[str, object] - The answer as data.
            text: str - The answer in words.
            parts: Sequence[str] - Parts of the saved file name.

        """
        if self.as_json:
            write_document(sys.stdout, document)
        else:
            self.stdout.print(text)
        self._save(parts, document)

    def page[T: BaseModel](
        self,
        page: Page[T],
        render: Sequence[RenderableType],
        parts: Sequence[str],
        pool: str | None,
    ) -> None:
        """Show and save one page of a search.

        Args:
            page: Page[T] - The page.
            render: Sequence[RenderableType] - The table and facet tables.
            parts: Sequence[str] - Parts of the saved file name.
            pool: str | None - The pool of the answer.

        """
        document = page_document(page)
        if self.as_json:
            write_document(sys.stdout, document)
        else:
            for item in render:
                self.stdout.print(item)
            self.stdout.print(
                summary(
                    shown=len(page.items),
                    total=page.total_results,
                    offset=page.offset,
                    pool=pool,
                ),
                style="dim",
            )
        self._save(parts, document)

    def records[T: BaseModel](
        self,
        records: Sequence[T],
        render: RenderableType,
        parts: Sequence[str],
    ) -> None:
        """Show and save a few records at once, such as a sample.

        Args:
            records: Sequence[T] - The records.
            render: RenderableType - The table.
            parts: Sequence[str] - Parts of the saved file name.

        """
        if self.as_json:
            for record in records:
                write_line(sys.stdout, dump(record))
        else:
            self.stdout.print(render)
        self._save(parts, [dump(record) for record in records])

    async def walk[T: BaseModel](
        self,
        records: AsyncIterator[T],
        table: Callable[[Sequence[T]], RenderableType],
        parts: Sequence[str],
    ) -> int:
        """Show and save a walk record by record.

        Args:
            records: AsyncIterator[T] - The walk.
            table: Callable[[Sequence[T]], RenderableType] - Renders a chunk of rows.
            parts: Sequence[str] - Parts of the saved file name.

        Returns:
            int - Records shown.

        """
        with ExitStack() as stack:
            if self.saves:
                self.saving = stack.enter_context(
                    JsonLinesFile(self._path(parts, ".jsonl")),
                )
                _ = stack.callback(self._report_saved)
            return await self._show(records, table)

    def _report_saved(self) -> None:
        if self.saving is not None:
            path = self.saving.path.resolve()
            self.message(f"saved {self.saving.count} records to {path}")

    async def _show[T: BaseModel](
        self,
        records: AsyncIterator[T],
        table: Callable[[Sequence[T]], RenderableType],
    ) -> int:
        shown = 0
        chunk: list[T] = []
        async for record in records:
            shown += 1
            data = dump(record)
            if self.saving is not None:
                self.saving.write(data)
            if self.as_json:
                write_line(sys.stdout, data)
                continue
            chunk.append(record)
            if len(chunk) == _CHUNK:
                self.stdout.print(table(chunk))
                chunk = []
        if chunk:
            self.stdout.print(table(chunk))
        return shown


async def _with_client(client: CrossrefClient, action: Action, output: Output) -> int:
    async with client:
        return await action(client, output)


def run(ctx: typer.Context, common: Common, action: Action) -> None:
    """Run a command: settings, logs, the client, and the exit code of the outcome.

    Args:
        ctx: typer.Context - The context; `ctx.obj` may carry a client factory (tests).
        common: Common - The shared options.
        action: Action - What the command does with the client.

    Raises:
        typer.Exit: Always, with the exit code of the outcome.

    """
    configure_logs(verbose=common.verbose)
    settings = resolve_settings(
        mailto=common.mailto,
        out_dir=common.out_dir,
        cwd=Path.cwd(),
        environ=os.environ,
    )
    output = Output(common=common, settings=settings)
    if settings.mailto is None and settings.plus_token is None:
        output.message(f"public pool, slower: set {MAILTO_VARIABLE}")
    given = typing.cast("object", ctx.obj)
    factory = typing.cast("ClientFactory", given) if callable(given) else default_client
    code = EXIT_CROSSREF
    try:
        code = asyncio.run(_with_client(factory(settings), action, output))
    except (CrossrefQueryError, CrossrefBadRequestError) as error:
        _report(output, common, error)
        code = EXIT_QUERY
    except (CrossrefRateLimitedError, CrossrefUnavailableError) as error:
        _report(output, common, error)
        if settings.mailto is None and settings.plus_token is None:
            output.message(f"the public pool is small: set {MAILTO_VARIABLE}")
        code = EXIT_CROSSREF
    except CrossrefBlockedError as error:
        _report(output, common, error)
        code = EXIT_CROSSREF
    except KeyboardInterrupt:
        saved = f"; {output.saving.count} records saved" if output.saving else ""
        output.message(f"interrupted{saved}")
        code = EXIT_INTERRUPTED
    raise typer.Exit(code)


def _report(output: Output, common: Common, error: Exception) -> None:
    output.message(str(error))
    if isinstance(error, CrossrefBadRequestError):
        for problem in error.problems:
            output.message(f"  {problem.type}: {problem.message}")
    if common.verbose:
        output.message("".join(traceback.format_exception(error)))
