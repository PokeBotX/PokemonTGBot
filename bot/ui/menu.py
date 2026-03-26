"""Menu keyboard builders."""
from telegram import InlineKeyboardButton, InlineKeyboardMarkup


def build_main_menu_keyboard(session_id: str) -> InlineKeyboardMarkup:
    """
    Build main menu inline keyboard.
    
    Layout:
    Row 1: Магазин | Рынок | Профиль
    Row 2: Моя коллекция | Чат | Информация
    
    Args:
        session_id: Unique session identifier for this menu
    
    Returns:
        InlineKeyboardMarkup with 9 buttons
    """
    keyboard = [
        [
            InlineKeyboardButton("🛒 Магазин", callback_data=f"menu:shop:{session_id}"),
            InlineKeyboardButton("📈 Рынок", callback_data=f"menu:market:{session_id}"),
            InlineKeyboardButton("👤 Профиль", callback_data=f"menu:profile:{session_id}"),
        ],
        [
            InlineKeyboardButton("📦 Моя коллекция", callback_data=f"menu:collection:{session_id}"),
            InlineKeyboardButton("💬 Чат", url="https://t.me/+TQ8-KkXpZa02MDY6"),
            InlineKeyboardButton("ℹ️ Информация", callback_data=f"menu:info:{session_id}"),
        ],
    ]
    return InlineKeyboardMarkup(keyboard)


def build_back_button(session_id: str) -> InlineKeyboardMarkup:
    """
    Build 'Back to Menu' button.
    
    Args:
        session_id: Session ID to embed in callback_data
    
    Returns:
        InlineKeyboardMarkup with single back button
    """
    keyboard = [
        [InlineKeyboardButton("🔙 Назад в меню", callback_data=f"menu:back:{session_id}")],
    ]
    return InlineKeyboardMarkup(keyboard)
