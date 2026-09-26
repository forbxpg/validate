"""Mapping of an account."""

from __future__ import annotations

from vld.auth.domain import Profile, User
from vld.auth.infrastructure.models import UserModel


def apply_user_to_model(user: User, model: UserModel) -> None:
    """Copy the changeable state of an account into its ORM model.

    Args:
        user: User - Domain entity.
        model: UserModel - ORM model to update.

    """
    profile = user.profile
    model.email = user.email
    model.email_verified_at = user.email_verified_at
    model.password_hash = user.password_hash
    model.role = user.role
    model.is_admin = user.is_admin
    model.is_active = user.is_active
    model.tokens_invalidated_after = user.tokens_invalidated_after
    model.first_name_ru = profile.first_name_ru
    model.last_name_ru = profile.last_name_ru
    model.first_name_en = profile.first_name_en
    model.last_name_en = profile.last_name_en
    model.group_number = profile.group_number
    model.institution_name = profile.institution_name


def user_to_model(user: User) -> UserModel:
    """Build the ORM model of an account.

    Args:
        user: User - Domain entity.

    Returns:
        UserModel - ORM model.

    """
    model = UserModel(id=user.id)
    apply_user_to_model(user, model)
    return model


def user_from_model(model: UserModel) -> User:
    """Build the domain entity of an account.

    Args:
        model: UserModel - ORM model.

    Returns:
        User - Domain entity.

    """
    return User(
        id=model.id,
        email=model.email,
        email_verified_at=model.email_verified_at,
        password_hash=model.password_hash,
        role=model.role,
        is_admin=model.is_admin,
        is_active=model.is_active,
        tokens_invalidated_after=model.tokens_invalidated_after,
        profile=Profile(
            first_name_ru=model.first_name_ru,
            last_name_ru=model.last_name_ru,
            first_name_en=model.first_name_en,
            last_name_en=model.last_name_en,
            group_number=model.group_number,
            institution_name=model.institution_name,
        ),
    )
