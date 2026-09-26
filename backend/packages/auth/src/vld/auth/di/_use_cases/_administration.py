"""Use cases of administration: accounts and the audit log."""

from __future__ import annotations

from dishka import Provider, Scope, provide

from vld.auth.application import (
    ChangeUserRole,
    Clock,
    DeleteUser,
    GetUser,
    GrantAdmin,
    ListUsers,
    ReadAudit,
    SetUserActive,
    UserRepository,
)
from vld.core.audit import AuditLog, AuditQuery
from vld.core.database import UnitOfWork


class AuthAdministrationUseCaseProvider(Provider):
    """Use cases of administration."""

    @provide(scope=Scope.REQUEST)
    def list_users(self, users: UserRepository) -> ListUsers:
        """Build the list of accounts.

        Args:
            users: UserRepository - Account store.

        Returns:
            ListUsers - The use case.

        """
        return ListUsers(users)

    @provide(scope=Scope.REQUEST)
    def get_user(self, users: UserRepository) -> GetUser:
        """Build the account card.

        Args:
            users: UserRepository - Account store.

        Returns:
            GetUser - The use case.

        """
        return GetUser(users)

    @provide(scope=Scope.REQUEST)
    def set_user_active(
        self,
        users: UserRepository,
        clock: Clock,
        uow: UnitOfWork,
        audit: AuditLog,
    ) -> SetUserActive:
        """Build turning an account off and on.

        Args:
            users: UserRepository - Account store.
            clock: Clock - Clock.
            uow: UnitOfWork - Transaction boundary.
            audit: AuditLog - Audit log.

        Returns:
            SetUserActive - The use case.

        """
        return SetUserActive(users, clock, uow, audit)

    @provide(scope=Scope.REQUEST)
    def change_user_role(
        self,
        users: UserRepository,
        uow: UnitOfWork,
        audit: AuditLog,
    ) -> ChangeUserRole:
        """Build the role change.

        Args:
            users: UserRepository - Account store.
            uow: UnitOfWork - Transaction boundary.
            audit: AuditLog - Audit log.

        Returns:
            ChangeUserRole - The use case.

        """
        return ChangeUserRole(users, uow, audit)

    @provide(scope=Scope.REQUEST)
    def grant_admin(
        self,
        users: UserRepository,
        uow: UnitOfWork,
        audit: AuditLog,
    ) -> GrantAdmin:
        """Build granting admin rights from the console.

        Args:
            users: UserRepository - Account store.
            uow: UnitOfWork - Transaction boundary.
            audit: AuditLog - Audit log.

        Returns:
            GrantAdmin - The use case.

        """
        return GrantAdmin(users, uow, audit)

    @provide(scope=Scope.REQUEST)
    def delete_user(
        self,
        users: UserRepository,
        uow: UnitOfWork,
        audit: AuditLog,
    ) -> DeleteUser:
        """Build deleting an account from the console.

        Args:
            users: UserRepository - Account store.
            uow: UnitOfWork - Transaction boundary.
            audit: AuditLog - Audit log.

        Returns:
            DeleteUser - The use case.

        """
        return DeleteUser(users, uow, audit)

    @provide(scope=Scope.REQUEST)
    def read_audit(self, audit: AuditQuery) -> ReadAudit:
        """Build reading the audit log.

        Args:
            audit: AuditQuery - Audit reader.

        Returns:
            ReadAudit - The use case.

        """
        return ReadAudit(audit)
