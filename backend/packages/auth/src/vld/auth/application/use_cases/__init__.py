"""Use cases of auth, one module per use case, grouped by process."""

from __future__ import annotations

from .account._describe_me import DescribeMe, MeView
from .account._update_profile import UpdateProfile
from .administration._change_user_role import ChangeUserRole
from .administration._delete_user import DeleteUser
from .administration._get_user import GetUser
from .administration._grant_admin import GrantAdmin
from .administration._list_users import ListUsers
from .administration._set_user_active import SetUserActive
from .administration._target_guard import TargetForbiddenError
from .onboarding._register import RegisterCommand, RegisterUser
from .onboarding._resend_verification import (
    ResendVerification,
    ResendVerificationCommand,
)
from .onboarding._send_password_reset_email import (
    SendPasswordResetEmail,
    UnknownResetTargetError,
)
from .onboarding._send_verification_email import (
    SendVerificationEmail,
    UnknownRegisteredUserError,
)
from .onboarding._verify_email import VerifyEmail
from .password._change_password import ChangePassword, ChangePasswordCommand
from .password._request_password_reset import RequestPasswordReset
from .password._reset_password import ResetPassword
from .session._dummy_hash import warm_password_verification
from .session._invalidate import InvalidateSessions
from .session._login import LoginCommand, LoginWithPassword
from .session._logout import Logout
from .session._refresh import InvalidRefreshTokenError, RefreshTokens, TokenRevokedError
from .shared import InvalidTokenError, LoginResult, TokenPair, WeakPasswordError

__all__ = (
    "ChangePassword",
    "ChangePasswordCommand",
    "ChangeUserRole",
    "DeleteUser",
    "DescribeMe",
    "GetUser",
    "GrantAdmin",
    "InvalidRefreshTokenError",
    "InvalidTokenError",
    "InvalidateSessions",
    "ListUsers",
    "LoginCommand",
    "LoginResult",
    "LoginWithPassword",
    "Logout",
    "MeView",
    "RefreshTokens",
    "RegisterCommand",
    "RegisterUser",
    "RequestPasswordReset",
    "ResendVerification",
    "ResendVerificationCommand",
    "ResetPassword",
    "SendPasswordResetEmail",
    "SendVerificationEmail",
    "SetUserActive",
    "TargetForbiddenError",
    "TokenPair",
    "TokenRevokedError",
    "UnknownRegisteredUserError",
    "UnknownResetTargetError",
    "UpdateProfile",
    "VerifyEmail",
    "WeakPasswordError",
    "warm_password_verification",
)
