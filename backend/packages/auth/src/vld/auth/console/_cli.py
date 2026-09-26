"""`vld-auth`: grant admin rights and delete accounts from the console."""

from __future__ import annotations

import argparse
import asyncio

import structlog
from dishka import make_async_container

from vld.auth.application import DeleteUser, GrantAdmin
from vld.auth.di import AUTH_PROVIDERS
from vld.auth.domain import UserNotFoundError
from vld.core.config import ObservabilitySettings
from vld.core.di import CONTAINER_VALIDATION, CoreProvider
from vld.core.obs import configure_logging

_log: structlog.stdlib.BoundLogger = structlog.stdlib.get_logger(__name__)


class _Arguments(argparse.Namespace):
    """Parsed command line of `vld-auth`.

    Attributes:
        command: str - `grant-admin` or `delete-user`.
        email: str - Address of the account.

    """

    command: str = ""
    email: str = ""


def main(argv: list[str] | None = None) -> int:
    """Run `vld-auth grant-admin EMAIL` or `vld-auth delete-user EMAIL`.

    Args:
        argv: list[str] | None - Arguments; the process arguments when None.

    Returns:
        int - Exit code: 0 on success, 1 when no account has the address.

    """
    arguments = _parser().parse_args(argv, namespace=_Arguments())
    configure_logging(ObservabilitySettings())
    try:
        asyncio.run(_execute(arguments))
    except UserNotFoundError:
        _log.error("account_not_found", command=arguments.command)
        return 1
    return 0


async def _execute(arguments: _Arguments) -> None:
    """Run the chosen command in a request scope of its own container.

    Args:
        arguments: _Arguments - Parsed command line.

    """
    container = make_async_container(
        CoreProvider(),
        *AUTH_PROVIDERS,
        validation_settings=CONTAINER_VALIDATION,
    )
    try:
        async with container() as scope:
            if arguments.command == "grant-admin":
                user = await (await scope.get(GrantAdmin))(arguments.email)
                _log.info("admin_granted", user_id=str(user.id))
            else:
                await (await scope.get(DeleteUser))(arguments.email)
                _log.info("user_deleted")
    finally:
        await container.close()


def _parser() -> argparse.ArgumentParser:
    """Describe the command line.

    Returns:
        argparse.ArgumentParser - Parser of `vld-auth`.

    """
    parser = argparse.ArgumentParser(prog="vld-auth")
    commands = parser.add_subparsers(dest="command", required=True)
    grant = commands.add_parser("grant-admin", help="give an account admin rights")
    _ = grant.add_argument("email", help="address of a registered account")
    delete = commands.add_parser(
        "delete-user",
        help="delete an account and its tokens for good",
    )
    _ = delete.add_argument("email", help="address of the account")
    return parser
