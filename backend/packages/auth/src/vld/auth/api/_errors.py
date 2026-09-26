"""Table «auth domain error -> how it looks outside»."""

from __future__ import annotations

from http import HTTPStatus

from vld.auth.application import (
    InvalidAccessTokenError,
    InvalidRefreshTokenError,
    InvalidTokenError,
    RevocationCheckUnavailableError,
    TargetForbiddenError,
    TokenRevokedError,
    WeakPasswordError,
)
from vld.auth.domain import (
    AccountDeactivatedError,
    AccountGoneError,
    AuthDomainError,
    EmailAlreadyTakenError,
    EmailNotVerifiedError,
    EntityNotFoundError,
    InvalidCredentialsError,
    TokenAlreadyUsedError,
    TokenExpiredError,
    TokenIdAlreadyAssignedError,
    UserNotFoundError,
)
from vld.web.errors import ErrorRegistry, ErrorSpec

from .schemas import AuthErrorCode

# A Redis flap lasts tens of seconds: the answer means "retry".
_REVOCATION_RETRY_AFTER_SECONDS = 5


_INTERNAL = ErrorSpec(
    status=HTTPStatus.INTERNAL_SERVER_ERROR,
    code=AuthErrorCode.INTERNAL_ERROR,
    message="Внутренняя ошибка сервера.",
)

AUTH_ERRORS = ErrorRegistry(
    base=AuthDomainError,
    fallback_code=AuthErrorCode.INTERNAL_ERROR,
    mapping={
        EmailAlreadyTakenError: ErrorSpec(
            status=HTTPStatus.CONFLICT,
            code=AuthErrorCode.EMAIL_ALREADY_TAKEN,
            message="Этот адрес уже зарегистрирован.",
        ),
        WeakPasswordError: ErrorSpec(
            status=HTTPStatus.UNPROCESSABLE_ENTITY,
            code=AuthErrorCode.WEAK_PASSWORD,
            message=(
                "Пароль должен быть не короче 8 символов и содержать "
                "заглавную и строчную букву."
            ),
        ),
        InvalidTokenError: ErrorSpec(
            status=HTTPStatus.BAD_REQUEST,
            code=AuthErrorCode.INVALID_TOKEN,
            message="Ссылка недействительна.",
        ),
        TokenExpiredError: ErrorSpec(
            status=HTTPStatus.BAD_REQUEST,
            code=AuthErrorCode.TOKEN_EXPIRED,
            message="Срок действия ссылки истёк.",
        ),
        TokenAlreadyUsedError: ErrorSpec(
            status=HTTPStatus.BAD_REQUEST,
            code=AuthErrorCode.TOKEN_ALREADY_USED,
            message="Ссылка уже использована.",
        ),
        InvalidCredentialsError: ErrorSpec(
            status=HTTPStatus.UNAUTHORIZED,
            code=AuthErrorCode.INVALID_CREDENTIALS,
            message="Неверный адрес или пароль.",
        ),
        EmailNotVerifiedError: ErrorSpec(
            status=HTTPStatus.FORBIDDEN,
            code=AuthErrorCode.EMAIL_NOT_VERIFIED,
            message="Адрес не подтверждён.",
        ),
        AccountDeactivatedError: ErrorSpec(
            status=HTTPStatus.FORBIDDEN,
            code=AuthErrorCode.ACCOUNT_DEACTIVATED,
            message="Учётная запись отключена.",
        ),
        AccountGoneError: ErrorSpec(
            status=HTTPStatus.UNAUTHORIZED,
            code=AuthErrorCode.ACCOUNT_GONE,
            message="Учётная запись не существует.",
        ),
        TokenRevokedError: ErrorSpec(
            status=HTTPStatus.UNAUTHORIZED,
            code=AuthErrorCode.TOKEN_REVOKED,
            message="Сессия завершена, войдите заново.",
        ),
        InvalidRefreshTokenError: ErrorSpec(
            status=HTTPStatus.UNAUTHORIZED,
            code=AuthErrorCode.INVALID_REFRESH_TOKEN,
            message="Сессия недействительна, войдите заново.",
        ),
        InvalidAccessTokenError: ErrorSpec(
            status=HTTPStatus.UNAUTHORIZED,
            code=AuthErrorCode.INVALID_ACCESS_TOKEN,
            message="Токен доступа недействителен.",
        ),
        RevocationCheckUnavailableError: ErrorSpec(
            status=HTTPStatus.SERVICE_UNAVAILABLE,
            code=AuthErrorCode.REVOCATION_CHECK_UNAVAILABLE,
            message="Сервис временно недоступен, повторите попытку.",
            retry_after=_REVOCATION_RETRY_AFTER_SECONDS,
        ),
        UserNotFoundError: ErrorSpec(
            status=HTTPStatus.NOT_FOUND,
            code=AuthErrorCode.USER_NOT_FOUND,
            message="Пользователь не найден.",
        ),
        TargetForbiddenError: ErrorSpec(
            status=HTTPStatus.FORBIDDEN,
            code=AuthErrorCode.TARGET_FORBIDDEN,
            message="Это действие над данной учётной записью запрещено.",
        ),
        EntityNotFoundError: _INTERNAL,
        TokenIdAlreadyAssignedError: _INTERNAL,
    },
)
