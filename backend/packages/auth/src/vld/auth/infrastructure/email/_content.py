"""Content of the letters; the text is for the user and stays Russian."""

from __future__ import annotations

_BRAND = "Validate"
_ACCENT = "#2f6df6"

_TEXT = """\
{brand}

Здравствуйте!

{intro}
{link}

{footer}
"""

_HTML = """\
<div style="font-family:-apple-system,Segoe UI,Roboto,Arial,sans-serif;\
max-width:480px;margin:0 auto;padding:24px;color:#1a1a1a">
  <div style="font-size:20px;font-weight:700;color:{accent};margin-bottom:16px">\
{brand}</div>
  <p style="font-size:15px;line-height:1.5">{intro}</p>
  <p style="margin:24px 0">
    <a href="{link}" style="background:{accent};color:#fff;text-decoration:none;\
padding:12px 24px;border-radius:6px;display:inline-block;font-size:15px">\
{button}</a>
  </p>
  <p style="font-size:13px;color:#666;line-height:1.5">Если кнопка не работает, \
скопируйте ссылку в браузер:<br>{link}</p>
  <p style="font-size:13px;color:#666">{footer}</p>
</div>
"""

_VERIFY_SUBJECT = f"Подтверждение адреса — {_BRAND}"
_VERIFY_INTRO = "Подтвердите адрес электронной почты, чтобы завершить регистрацию."
_VERIFY_BUTTON = "Подтвердить адрес"
_VERIFY_FOOTER = (
    f"Если вы не регистрировались в {_BRAND}, просто проигнорируйте это письмо."
)

_RESET_SUBJECT = f"Смена пароля — {_BRAND}"
_RESET_INTRO = "Задайте новый пароль, перейдя по ссылке. Ссылка действует один час."
_RESET_BUTTON = "Задать новый пароль"
_RESET_FOOTER = (
    "Если вы не запрашивали смену пароля, просто проигнорируйте это письмо — "
    "пароль останется прежним."
)


def _render(
    *,
    subject: str,
    intro: str,
    button: str,
    footer: str,
    link: str,
) -> tuple[str, str, str]:
    """Build a letter from the shared layout.

    Args:
        subject: str - Subject.
        intro: str - Line under the header.
        button: str - Button caption.
        footer: str - The "if it was not you" line.
        link: str - Ready link.

    Returns:
        tuple[str, str, str] - Subject, HTML and plain text.

    """
    html = _HTML.format(
        brand=_BRAND,
        accent=_ACCENT,
        intro=intro,
        button=button,
        footer=footer,
        link=link,
    )
    text = _TEXT.format(brand=_BRAND, intro=intro, link=link, footer=footer)
    return subject, html, text


def render_verification_email(link: str) -> tuple[str, str, str]:
    """Build the letter that confirms an address.

    Args:
        link: str - Ready confirmation link.

    Returns:
        tuple[str, str, str] - Subject, HTML and plain text.

    """
    return _render(
        subject=_VERIFY_SUBJECT,
        intro=_VERIFY_INTRO,
        button=_VERIFY_BUTTON,
        footer=_VERIFY_FOOTER,
        link=link,
    )


def render_password_reset_email(link: str) -> tuple[str, str, str]:
    """Build the letter that sets a new password.

    Args:
        link: str - Ready link to the new-password page.

    Returns:
        tuple[str, str, str] - Subject, HTML and plain text.

    """
    return _render(
        subject=_RESET_SUBJECT,
        intro=_RESET_INTRO,
        button=_RESET_BUTTON,
        footer=_RESET_FOOTER,
        link=link,
    )
