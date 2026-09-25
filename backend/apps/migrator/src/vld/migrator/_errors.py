"""Refusals of the migrator: each one stops the deploy with a reason."""

from __future__ import annotations


class MigratorError(Exception):
    """A refusal to migrate; the message is the reason shown to the operator."""


class MigrationLockBusyError(MigratorError):
    """Another migration run holds the lock."""


class PreflightError(MigratorError):
    """The database or the scripts are not in a state that is safe to migrate."""


class BackupError(MigratorError):
    """The backup before the upgrade could not be taken or verified."""


class SchemaDriftError(MigratorError):
    """After the upgrade the database does not match the models."""
