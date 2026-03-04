"""Message text templates for bot UI."""

def get_main_menu_text(username: str) -> str:
    """Get main menu text with user mention."""
    return f"""
👋 @{username}, <b>Добро пожаловать в PokéCollect!</b>

Коллекционируйте покемонов, торгуйте на рынке и участвуйте в мини-играх.
Выберите раздел из меню ниже:
"""

# Legacy constant for backward compatibility
MAIN_MENU_TEXT = """
👋 <b>Добро пожаловать в PokéCollect!</b>

Коллекционируйте покемонов, торгуйте на рынке и участвуйте в мини-играх.
Выберите раздел из меню ниже:
"""

SECTION_PLACEHOLDER_TEMPLATE = """
{emoji} <b>{title}</b>

Этот раздел находится в разработке.
Скоро здесь появится новый функционал!
"""

# Section titles
SECTIONS = {
    "shop": {"emoji": "🛒", "title": "Магазин"},
    "market": {"emoji": "📈", "title": "Рынок"},
    "profile": {"emoji": "👤", "title": "Профиль"},
    "games": {"emoji": "🎮", "title": "Мини-игры"},
    "collection": {"emoji": "📦", "title": "Моя коллекция"},
    "updates": {"emoji": "📢", "title": "Обновления"},
    "chat": {"emoji": "💬", "title": "Чат"},
    "support": {"emoji": "🆘", "title": "Поддержка"},
    "info": {"emoji": "ℹ️", "title": "Информация"},
}

# Error messages
ERROR_STALE_MENU = "⚠️ Это меню устарело. Используйте /menu для нового."
ERROR_PROCESSING = "⏳ Обрабатывается..."
ERROR_INVALID_CALLBACK = "❌ Ошибка обработки. Попробуйте /menu"
ERROR_BOT_RESTARTED = "⚠️ Бот был перезапущен. Используйте /menu"
ERROR_NOT_YOUR_BUTTON = "⚠️ Это не ваша кнопка!"


def get_section_placeholder(section: str) -> str:
    """Get placeholder text for a section."""
    section_data = SECTIONS.get(section)
    if not section_data:
        return ERROR_INVALID_CALLBACK
    
    return SECTION_PLACEHOLDER_TEMPLATE.format(
        emoji=section_data["emoji"],
        title=section_data["title"],
    )
