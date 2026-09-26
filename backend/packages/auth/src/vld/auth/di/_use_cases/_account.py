"""Use cases of the own account."""

from __future__ import annotations

from dishka import Provider, Scope, provide

from vld.auth.application import DescribeMe, UpdateProfile, UserRepository
from vld.core.database import UnitOfWork


class AuthAccountUseCaseProvider(Provider):
    """Use cases of the own account."""

    @provide(scope=Scope.REQUEST)
    def describe_me(self, users: UserRepository) -> DescribeMe:
        """Build "who am I".

        Args:
            users: UserRepository - Account store.

        Returns:
            DescribeMe - The use case.

        """
        return DescribeMe(users)

    @provide(scope=Scope.REQUEST)
    def update_profile(self, users: UserRepository, uow: UnitOfWork) -> UpdateProfile:
        """Build the profile change.

        Args:
            users: UserRepository - Account store.
            uow: UnitOfWork - Transaction boundary.

        Returns:
            UpdateProfile - The use case.

        """
        return UpdateProfile(users, uow)
