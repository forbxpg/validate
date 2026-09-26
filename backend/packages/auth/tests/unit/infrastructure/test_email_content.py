"""Letters: the link in both parts, no remote images, the right words."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from vld.auth.infrastructure.email import (
    render_password_reset_email,
    render_verification_email,
)

if TYPE_CHECKING:
    from collections.abc import Callable

_LINK = "https://validate.example/auth/verify-email?token=abc123"

_RENDERERS: tuple[Callable[[str], tuple[str, str, str]], ...] = (
    render_verification_email,
    render_password_reset_email,
)


@pytest.mark.parametrize("render", _RENDERERS)
def test_render_returns_subject_html_text(
    render: Callable[[str], tuple[str, str, str]],
) -> None:
    """A letter has a subject and names the service in both parts."""
    subject, html, text = render(_LINK)
    assert subject.strip()
    assert "Validate" in html
    assert "Validate" in text


@pytest.mark.parametrize("render", _RENDERERS)
def test_link_is_present_in_both_parts(
    render: Callable[[str], tuple[str, str, str]],
) -> None:
    """The link is in the HTML button and in the plain text for clients without HTML."""
    _, html, text = render(_LINK)
    assert _LINK in html
    assert _LINK in text


@pytest.mark.parametrize("render", _RENDERERS)
def test_no_remote_images(render: Callable[[str], tuple[str, str, str]]) -> None:
    """Mail clients block remote images; the button matters more than a logo."""
    _, html, _ = render(_LINK)
    assert "<img" not in html.lower()


def test_two_letters_do_not_share_a_subject() -> None:
    """One subject for both would thread the letters together."""
    verify, _, _ = render_verification_email(_LINK)
    reset, _, _ = render_password_reset_email(_LINK)
    assert verify != reset


def test_reset_letter_tells_a_bystander_to_do_nothing() -> None:
    """A reset letter tells whoever did not ask that the password stays."""
    _, html, text = render_password_reset_email(_LINK)
    phrase = (
        "Если вы не запрашивали смену пароля, просто проигнорируйте это письмо — "
        "пароль останется прежним."
    )
    assert phrase in html
    assert phrase in text
