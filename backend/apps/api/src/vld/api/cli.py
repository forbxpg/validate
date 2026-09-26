"""`vld-api`: the command that runs the HTTP API under uvicorn."""

from __future__ import annotations

from typing import Annotated

import typer
import uvicorn

APP = "vld.api.main:create_app"
"""The application factory uvicorn imports in every worker process."""

app = typer.Typer(
    name="vld-api",
    help="Run the validate HTTP API. Settings come from the environment only.",
    no_args_is_help=True,
    add_completion=False,
)


@app.callback()
def _group() -> None:
    """Keep `run` a subcommand, so more commands can join it."""


@app.command(help="Serve the API.")
def run(
    *,
    host: Annotated[str, typer.Option(help="Address to bind.")] = "127.0.0.1",
    port: Annotated[int, typer.Option(help="Port to bind.")] = 8000,
    reload: Annotated[
        bool,
        typer.Option(help="Restart on code changes; development only."),
    ] = False,
    workers: Annotated[
        int,
        typer.Option(min=1, help="Worker processes; not with --reload."),
    ] = 1,
    forwarded_allow_ips: Annotated[
        str | None,
        typer.Option(
            help="Proxies trusted for X-Forwarded-*; uvicorn's default otherwise.",
        ),
    ] = None,
) -> None:
    """Serve the API.

    Args:
        host: str - Address to bind.
        port: int - Port to bind.
        reload: bool - Restart on code changes.
        workers: int - Worker processes.
        forwarded_allow_ips: str | None - Trusted proxies.

    Raises:
        typer.BadParameter: If --reload is combined with several workers.

    """
    if reload and workers != 1:
        msg = "--reload runs one process; drop --workers"
        raise typer.BadParameter(msg, param_hint="--workers")
    uvicorn.run(
        APP,
        factory=True,
        host=host,
        port=port,
        reload=reload,
        workers=workers,
        forwarded_allow_ips=forwarded_allow_ips,
        # The application configures logging; uvicorn's lines join the same handler.
        log_config=None,
        server_header=False,
    )


def main() -> None:
    """Run `vld-api`."""
    app()
