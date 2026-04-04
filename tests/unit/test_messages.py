"""Unit tests for message text templates."""

from bot.ui.messages import get_main_menu_text


def test_get_main_menu_text_uses_safe_label_without_forced_at_prefix() -> None:
    text = get_main_menu_text("Ash")
    assert "👋 Ash," in text
    assert "@Ash" not in text


def test_get_main_menu_text_escapes_html() -> None:
    text = get_main_menu_text("A<b>sh</b>")
    assert "A&lt;b&gt;sh&lt;/b&gt;" in text
