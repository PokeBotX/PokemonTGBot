"""Unit tests for chat encounter helpers."""

from datetime import UTC, datetime, timedelta
from unittest.mock import patch

from bot.db.database import (
    CHAT_ENCOUNTER_BALL_CATCH_CHANCES,
    CHAT_ENCOUNTER_COOLDOWN_SECONDS,
    _chat_encounter_cooldown_ready,
    _roll_chat_encounter_catch,
)
from bot.handlers.sections.chat_encounters import (
    build_caught_encounter_keyboard,
    build_encounter_keyboard,
)


def test_chat_encounter_cooldown_ready_after_four_hours() -> None:
    now = datetime.now(UTC)
    assert _chat_encounter_cooldown_ready(now - timedelta(seconds=CHAT_ENCOUNTER_COOLDOWN_SECONDS), now) is True


def test_chat_encounter_cooldown_not_ready_before_four_hours() -> None:
    now = datetime.now(UTC)
    assert _chat_encounter_cooldown_ready(
        now - timedelta(seconds=CHAT_ENCOUNTER_COOLDOWN_SECONDS - 1),
        now,
    ) is False


def test_masterball_is_guaranteed_catch() -> None:
    assert CHAT_ENCOUNTER_BALL_CATCH_CHANCES["masterball"] == 100.0
    assert _roll_chat_encounter_catch("masterball") is True


def test_regular_ball_uses_probability_roll() -> None:
    with patch("bot.db.database.random.uniform", return_value=59.0):
        assert _roll_chat_encounter_catch("pokeball") is True
    with patch("bot.db.database.random.uniform", return_value=61.0):
        assert _roll_chat_encounter_catch("pokeball") is False


def test_encounter_keyboard_callback_data_stays_short() -> None:
    keyboard = build_encounter_keyboard(123)
    callback_values = [button.callback_data for row in keyboard.inline_keyboard for button in row]
    assert callback_values == ["enc:123:pokeball", "enc:123:ultraball", "enc:123:masterball"]
    assert all(len(value) <= 64 for value in callback_values)


def test_caught_encounter_keyboard_callback_data_stays_short() -> None:
    keyboard = build_caught_encounter_keyboard(123)
    callback_values = [button.callback_data for row in keyboard.inline_keyboard for button in row]
    assert callback_values == ["enc:123:card"]
    assert all(len(value) <= 64 for value in callback_values)
