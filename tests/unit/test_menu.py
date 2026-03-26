"""Unit tests for menu keyboard builder."""
import pytest
from telegram import InlineKeyboardButton, InlineKeyboardMarkup

from bot.ui.menu import build_main_menu_keyboard, build_back_button


def test_build_main_menu_keyboard_structure():
    """Test that main menu keyboard has correct structure."""
    session_id = "test-session-123"
    keyboard = build_main_menu_keyboard(session_id)
    
    # Check it's an InlineKeyboardMarkup
    assert isinstance(keyboard, InlineKeyboardMarkup)
    
    assert len(keyboard.inline_keyboard) == 2
    assert len(keyboard.inline_keyboard[0]) == 3
    assert len(keyboard.inline_keyboard[1]) == 3


def test_build_main_menu_keyboard_button_count():
    """Test that main menu has 9 buttons total."""
    session_id = "test-session-123"
    keyboard = build_main_menu_keyboard(session_id)
    
    # Count all buttons
    button_count = sum(len(row) for row in keyboard.inline_keyboard)
    assert button_count == 6


def test_build_main_menu_keyboard_callback_data():
    """Test that all buttons have correct callback_data format."""
    session_id = "test-session-456"
    keyboard = build_main_menu_keyboard(session_id)
    
    expected_sections = [
        "shop", "market", "profile",
        "collection", "chat", "info"
    ]
    
    # Collect all buttons
    all_buttons = []
    for row in keyboard.inline_keyboard:
        all_buttons.extend(row)
    
    # Check each button
    for i, button in enumerate(all_buttons):
        assert isinstance(button, InlineKeyboardButton)
        if button.url:
            assert expected_sections[i] == "chat"
        else:
            assert button.callback_data == f"menu:{expected_sections[i]}:{session_id}"


def test_build_main_menu_keyboard_button_text():
    """Test that all buttons have text with emoji."""
    session_id = "test-session-789"
    keyboard = build_main_menu_keyboard(session_id)
    
    expected_texts = [
        "🛒 Магазин", "📈 Рынок", "👤 Профиль",
        "📦 Моя коллекция", "💬 Чат", "ℹ️ Информация"
    ]
    
    # Collect all buttons
    all_buttons = []
    for row in keyboard.inline_keyboard:
        all_buttons.extend(row)
    
    # Check each button text
    for i, button in enumerate(all_buttons):
        assert button.text == expected_texts[i]


def test_build_main_menu_keyboard_session_id_included():
    """Test that session_id is included in callback_data."""
    session_id = "unique-session-uuid"
    keyboard = build_main_menu_keyboard(session_id)
    
    # Check first button
    first_button = keyboard.inline_keyboard[0][0]
    assert session_id in first_button.callback_data


def test_build_back_button_structure():
    """Test that back button has correct structure."""
    session_id = "test-session-back"
    keyboard = build_back_button(session_id)
    
    # Check it's an InlineKeyboardMarkup
    assert isinstance(keyboard, InlineKeyboardMarkup)
    
    # Check it has 1 row
    assert len(keyboard.inline_keyboard) == 1
    
    # Check row has 1 button
    assert len(keyboard.inline_keyboard[0]) == 1


def test_build_back_button_text():
    """Test that back button has correct text."""
    session_id = "test-session-back"
    keyboard = build_back_button(session_id)
    
    button = keyboard.inline_keyboard[0][0]
    assert button.text == "🔙 Назад в меню"


def test_build_back_button_callback_data():
    """Test that back button has correct callback_data."""
    session_id = "test-session-back-123"
    keyboard = build_back_button(session_id)
    
    button = keyboard.inline_keyboard[0][0]
    assert button.callback_data == f"menu:back:{session_id}"


def test_build_main_menu_keyboard_different_sessions():
    """Test that different session_ids produce different keyboards."""
    keyboard1 = build_main_menu_keyboard("session-1")
    keyboard2 = build_main_menu_keyboard("session-2")
    
    # Get first button from each
    button1 = keyboard1.inline_keyboard[0][0]
    button2 = keyboard2.inline_keyboard[0][0]
    
    # Texts should be same
    assert button1.text == button2.text
    
    # Callback data should be different
    assert button1.callback_data != button2.callback_data
    assert "session-1" in button1.callback_data
    assert "session-2" in button2.callback_data


def test_build_back_button_different_sessions():
    """Test that different session_ids produce different back buttons."""
    keyboard1 = build_back_button("session-1")
    keyboard2 = build_back_button("session-2")
    
    button1 = keyboard1.inline_keyboard[0][0]
    button2 = keyboard2.inline_keyboard[0][0]
    
    # Texts should be same
    assert button1.text == button2.text
    
    # Callback data should be different
    assert button1.callback_data != button2.callback_data
