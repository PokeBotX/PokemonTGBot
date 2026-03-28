# Implementation Plan: Bot Menu & Navigation

**Spec**: 001-main-menu-navigation  
**Status**: Ready for Implementation  
**Created**: 2026-03-04  
**Version**: 0.1.0  

## Overview

Этот план описывает реализацию главного меню и навигационной системы для Telegram-бота PokéCollect. Система обеспечивает единую точку входа для всех функций бота с поддержкой работы в личных чатах, группах и тредах/топиках.

**Core Goals**:
- Минимальное время отклика меню (≤1 сек для 95% запросов)
- Устойчивость к повторным нажатиям и устаревшим callback
- Единый стиль UX во всех разделах
- Корректная работа в различных типах чатов

## Architecture

### High-Level Design

```
┌─────────────────────────────────────────────────────────────┐
│                        Telegram API                          │
└─────────────────────┬───────────────────────────────────────┘
                      │
                      ▼
┌─────────────────────────────────────────────────────────────┐
│                    Bot Application                           │
│  ┌──────────────────────────────────────────────────────┐   │
│  │              CommandHandlers                         │   │
│  │  - /start → show_main_menu()                        │   │
│  │  - /menu  → show_main_menu()                        │   │
│  └──────────────────┬───────────────────────────────────┘   │
│                     │                                        │
│  ┌──────────────────▼───────────────────────────────────┐   │
│  │           CallbackQueryHandler                       │   │
│  │  - parse_callback_data()                            │   │
│  │  - route to section handler                         │   │
│  └──────────────────┬───────────────────────────────────┘   │
│                     │                                        │
│  ┌──────────────────▼───────────────────────────────────┐   │
│  │            NavigationRouter                          │   │
│  │  - validate_session()                               │   │
│  │  - check_idempotency()                              │   │
│  │  - dispatch to section                              │   │
│  └──────────────────┬───────────────────────────────────┘   │
│                     │                                        │
│  ┌──────────────────▼───────────────────────────────────┐   │
│  │           Section Handlers                           │   │
│  │  - shop_handler()        (placeholder)              │   │
│  │  - market_handler()      (placeholder)              │   │
│  │  - profile_handler()     (placeholder)              │   │
│  │  - back_to_menu_handler()                           │   │
│  └──────────────────┬───────────────────────────────────┘   │
│                     │                                        │
│  ┌──────────────────▼───────────────────────────────────┐   │
│  │             Menu Builder                             │   │
│  │  - build_main_menu()                                │   │
│  │  - build_section_menu()                             │   │
│  │  - create_back_button()                             │   │
│  └──────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
                      │
                      ▼
┌─────────────────────────────────────────────────────────────┐
│                   Session Store (In-Memory)                  │
│  - menu_sessions: Dict[str, MenuSession]                    │
│  - callback_locks: Dict[str, datetime]                      │
└─────────────────────────────────────────────────────────────┘
```

### Directory Structure

```
pokemonbot/
├── bot/
│   ├── __init__.py
│   ├── main.py                    # Bot initialization & startup
│   ├── handlers/
│   │   ├── __init__.py
│   │   ├── commands.py            # /start, /menu handlers
│   │   ├── navigation.py          # Callback query router
│   │   └── sections/
│   │       ├── __init__.py
│   │       ├── shop.py            # Placeholder: Магазин
│   │       ├── market.py          # Placeholder: Рынок
│   │       ├── profile.py         # Placeholder: Профиль
│   │       ├── games.py           # Placeholder: Мини-игры
│   │       ├── collection.py      # Placeholder: Моя коллекция
│   │       ├── updates.py         # Placeholder: Обновления
│   │       ├── chat.py            # Placeholder: Чат
│   │       ├── support.py         # Placeholder: Поддержка
│   │       └── info.py            # Placeholder: Информация
│   ├── ui/
│   │   ├── __init__.py
│   │   ├── menu.py                # Menu builders & keyboard layouts
│   │   └── messages.py            # Message text templates
│   ├── navigation/
│   │   ├── __init__.py
│   │   ├── router.py              # Callback routing logic
│   │   ├── session.py             # Session management
│   │   └── context.py             # Context extraction (chat_id, thread_id)
│   └── utils/
│       ├── __init__.py
│       └── logging.py             # Structured logging setup
├── tests/
│   ├── __init__.py
│   ├── unit/
│   │   ├── test_router.py
│   │   ├── test_session.py
│   │   ├── test_menu_builder.py
│   │   └── test_context.py
│   └── integration/
│       ├── test_handlers.py
│       └── test_navigation.py
├── .env                            # Environment variables
├── pyproject.toml                  # Dependencies & project config
└── README.md
```

## Implementation Tasks

### Phase 1: Core Infrastructure (Days 1-2)

#### Task 1.1: Project Setup & Dependencies
**Priority**: P0  
**Estimate**: 2 hours  

**Actions**:
1. Update `pyproject.toml` with dependencies:
   ```toml
   [project]
   dependencies = [
       "python-telegram-bot[all]>=21.0",
       "structlog>=24.1.0",
       "python-dotenv>=1.0.0",
   ]
   
   [project.optional-dependencies]
   dev = [
       "pytest>=8.0.0",
       "pytest-asyncio>=0.23.0",
       "pytest-mock>=3.12.0",
   ]
   ```

2. Create directory structure:
   ```bash
   mkdir -p bot/{handlers/sections,ui,navigation,utils}
   mkdir -p tests/{unit,integration}
   touch bot/__init__.py bot/handlers/__init__.py bot/handlers/sections/__init__.py
   touch bot/ui/__init__.py bot/navigation/__init__.py bot/utils/__init__.py
   ```

3. Setup structured logging in `bot/utils/logging.py`

**Acceptance**:
- ✅ All dependencies installed via `uv sync`
- ✅ Directory structure created
- ✅ Logging configured and tested

#### Task 1.2: Context Extraction Module
**Priority**: P0  
**Estimate**: 1 hour  
**File**: `bot/navigation/context.py`

**Implementation**:
```python
from dataclasses import dataclass
from typing import Optional
from telegram import Update

@dataclass
class MessageContext:
    """Context information from a Telegram update."""
    chat_id: int
    user_id: int
    message_id: Optional[int] = None
    message_thread_id: Optional[int] = None
    chat_type: str = "private"  # private, group, supergroup, channel

def extract_context(update: Update) -> MessageContext:
    """
    Extract context from Telegram update.
    
    Returns:
        MessageContext with chat_id, user_id, message_id, thread_id, chat_type
    
    Raises:
        ValueError if update is invalid or missing required fields
    """
    if not update.effective_chat or not update.effective_user:
        raise ValueError("Update missing effective_chat or effective_user")
    
    context = MessageContext(
        chat_id=update.effective_chat.id,
        user_id=update.effective_user.id,
        chat_type=update.effective_chat.type,
    )
    
    if update.effective_message:
        context.message_id = update.effective_message.message_id
        context.message_thread_id = getattr(
            update.effective_message, "message_thread_id", None
        )
    
    return context
```

**Tests** (`tests/unit/test_context.py`):
- Test valid update in private chat
- Test valid update in group
- Test valid update in forum topic (thread_id present)
- Test invalid update (missing chat/user)

**Acceptance**:
- ✅ Function extracts all context fields correctly
- ✅ Tests pass with 100% coverage
- ✅ Raises ValueError for invalid updates

#### Task 1.3: Session Management
**Priority**: P0  
**Estimate**: 2 hours  
**File**: `bot/navigation/session.py`

**Implementation**:
```python
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Dict, Optional

@dataclass
class MenuSession:
    """Menu session data."""
    session_id: str
    chat_id: int
    message_id: int
    message_thread_id: Optional[int]
    user_id: int
    created_at: datetime = field(default_factory=datetime.utcnow)
    expires_at: datetime = field(init=False)
    
    def __post_init__(self):
        self.expires_at = self.created_at + timedelta(minutes=10)
    
    def is_expired(self) -> bool:
        """Check if session has expired."""
        return datetime.utcnow() > self.expires_at
    
    def matches_context(
        self, 
        chat_id: int, 
        message_id: int,
        message_thread_id: Optional[int] = None
    ) -> bool:
        """Check if session matches given context."""
        return (
            self.chat_id == chat_id
            and self.message_id == message_id
            and self.message_thread_id == message_thread_id
        )


class SessionStore:
    """In-memory store for menu sessions and callback locks."""
    
    def __init__(self):
        self._sessions: Dict[str, MenuSession] = {}
        self._callback_locks: Dict[str, datetime] = {}
    
    def create_session(
        self,
        chat_id: int,
        message_id: int,
        user_id: int,
        message_thread_id: Optional[int] = None,
    ) -> str:
        """Create a new menu session."""
        session_id = str(uuid.uuid4())
        session = MenuSession(
            session_id=session_id,
            chat_id=chat_id,
            message_id=message_id,
            message_thread_id=message_thread_id,
            user_id=user_id,
        )
        self._sessions[session_id] = session
        return session_id
    
    def get_session(self, session_id: str) -> Optional[MenuSession]:
        """Get session by ID, return None if expired."""
        session = self._sessions.get(session_id)
        if session and session.is_expired():
            del self._sessions[session_id]
            return None
        return session
    
    def delete_session(self, session_id: str) -> None:
        """Delete session by ID."""
        self._sessions.pop(session_id, None)
    
    def is_callback_locked(self, callback_query_id: str) -> bool:
        """Check if callback is already being processed."""
        lock_time = self._callback_locks.get(callback_query_id)
        if lock_time:
            # Lock expires after 10 seconds
            if datetime.utcnow() - lock_time < timedelta(seconds=10):
                return True
            else:
                del self._callback_locks[callback_query_id]
        return False
    
    def lock_callback(self, callback_query_id: str) -> None:
        """Lock callback to prevent duplicate processing."""
        self._callback_locks[callback_query_id] = datetime.utcnow()
    
    def cleanup_expired(self) -> None:
        """Remove expired sessions and locks."""
        # Cleanup expired sessions
        expired_sessions = [
            sid for sid, session in self._sessions.items()
            if session.is_expired()
        ]
        for sid in expired_sessions:
            del self._sessions[sid]
        
        # Cleanup old callback locks
        cutoff = datetime.utcnow() - timedelta(seconds=10)
        expired_locks = [
            cid for cid, lock_time in self._callback_locks.items()
            if lock_time < cutoff
        ]
        for cid in expired_locks:
            del self._callback_locks[cid]


# Global session store instance
session_store = SessionStore()
```

**Tests** (`tests/unit/test_session.py`):
- Test session creation
- Test session expiration (mock datetime)
- Test session context matching
- Test callback locking (duplicate prevention)
- Test cleanup of expired sessions/locks

**Acceptance**:
- ✅ Sessions expire after 10 minutes
- ✅ Callback locks expire after 10 seconds
- ✅ Context matching works correctly
- ✅ Tests pass with 100% coverage

### Phase 2: Menu UI & Builders (Days 2-3)

#### Task 2.1: Message Templates
**Priority**: P1  
**Estimate**: 1 hour  
**File**: `bot/ui/messages.py`

**Implementation**:
```python
"""Message text templates for bot UI."""

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

def get_section_placeholder(section: str) -> str:
    """Get placeholder text for a section."""
    section_data = SECTIONS.get(section)
    if not section_data:
        return ERROR_INVALID_CALLBACK
    
    return SECTION_PLACEHOLDER_TEMPLATE.format(
        emoji=section_data["emoji"],
        title=section_data["title"],
    )
```

**Acceptance**:
- ✅ All message templates defined
- ✅ Section metadata available
- ✅ HTML formatting used consistently

#### Task 2.2: Menu Keyboard Builder
**Priority**: P1  
**Estimate**: 2 hours  
**File**: `bot/ui/menu.py`

**Implementation**:
```python
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from typing import Optional

def build_main_menu_keyboard(session_id: str) -> InlineKeyboardMarkup:
    """
    Build main menu inline keyboard.
    
    Layout (3 rows × 3 columns):
    Row 1: Магазин | Рынок | Профиль
    Row 2: Мини-игры | Моя коллекция | Обновления
    Row 3: Чат | Поддержка | Информация
    
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
            InlineKeyboardButton("🎮 Мини-игры", callback_data=f"menu:games:{session_id}"),
            InlineKeyboardButton("📦 Моя коллекция", callback_data=f"menu:collection:{session_id}"),
            InlineKeyboardButton("📢 Обновления", callback_data=f"menu:updates:{session_id}"),
        ],
        [
            InlineKeyboardButton("💬 Чат", callback_data=f"menu:chat:{session_id}"),
            InlineKeyboardButton("🆘 Поддержка", callback_data=f"menu:support:{session_id}"),
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
```

**Tests** (`tests/unit/test_menu_builder.py`):
- Test main menu has 9 buttons in 3 rows
- Test callback_data format: `menu:<section>:<session_id>`
- Test back button format
- Test session_id embedded correctly

**Acceptance**:
- ✅ Main menu keyboard has correct layout
- ✅ Callback data follows spec format
- ✅ Tests pass with 100% coverage

### Phase 3: Handlers & Routing (Days 3-5)

#### Task 3.1: Callback Data Parser & Router
**Priority**: P1  
**Estimate**: 2 hours  
**File**: `bot/navigation/router.py`

**Implementation**:
```python
from dataclasses import dataclass
from typing import Callable, Dict, Optional
import structlog

logger = structlog.get_logger()

@dataclass
class CallbackData:
    """Parsed callback data."""
    action: str       # "menu"
    section: str      # "shop", "back", etc.
    session_id: str   # UUID4

def parse_callback_data(data: str) -> Optional[CallbackData]:
    """
    Parse callback_data format: menu:<section>:<session_id>
    
    Args:
        data: Callback data string from inline button
    
    Returns:
        CallbackData object or None if format is invalid
    
    Example:
        >>> parse_callback_data("menu:shop:abc-123")
        CallbackData(action='menu', section='shop', session_id='abc-123')
    """
    try:
        parts = data.split(":")
        if len(parts) != 3:
            logger.warning("callback_data_invalid_format", data=data, parts_count=len(parts))
            return None
        
        action, section, session_id = parts
        
        if action != "menu":
            logger.warning("callback_data_unknown_action", action=action, data=data)
            return None
        
        return CallbackData(action=action, section=section, session_id=session_id)
    
    except Exception as e:
        logger.error("callback_data_parse_error", data=data, error=str(e))
        return None


class NavigationRouter:
    """Routes callback queries to appropriate section handlers."""
    
    def __init__(self):
        self._routes: Dict[str, Callable] = {}
    
    def register(self, section: str, handler: Callable) -> None:
        """Register a handler for a section."""
        self._routes[section] = handler
        logger.info("route_registered", section=section)
    
    def get_handler(self, section: str) -> Optional[Callable]:
        """Get handler for a section."""
        return self._routes.get(section)
    
    def list_routes(self) -> list[str]:
        """List all registered routes."""
        return list(self._routes.keys())


# Global router instance
navigation_router = NavigationRouter()
```

**Tests** (`tests/unit/test_router.py`):
- Test valid callback_data parsing
- Test invalid formats (wrong delimiter, missing parts)
- Test unknown action (not "menu")
- Test route registration
- Test get_handler returns correct handler
- Test list_routes

**Acceptance**:
- ✅ Parser handles valid and invalid data
- ✅ Router can register and retrieve handlers
- ✅ Tests pass with 100% coverage

#### Task 3.2: Command Handlers (/start, /menu)
**Priority**: P1  
**Estimate**: 2 hours  
**File**: `bot/handlers/commands.py`

**Implementation**:
```python
import structlog
from telegram import Update
from telegram.ext import ContextTypes

from bot.navigation.context import extract_context
from bot.navigation.session import session_store
from bot.ui.menu import build_main_menu_keyboard
from bot.ui.messages import MAIN_MENU_TEXT

logger = structlog.get_logger()

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Handle /start command.
    Shows main menu to user.
    """
    await _show_main_menu(update, context)


async def menu_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Handle /menu command.
    Shows main menu to user.
    """
    await _show_main_menu(update, context)


async def _show_main_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Internal: Send main menu message with inline keyboard.
    
    Handles:
    - Private chats
    - Group chats
    - Forum topics (threads)
    """
    try:
        msg_context = extract_context(update)
        
        logger.info(
            "show_main_menu",
            user_id=msg_context.user_id,
            chat_id=msg_context.chat_id,
            chat_type=msg_context.chat_type,
            thread_id=msg_context.message_thread_id,
        )
        
        # Send menu message
        sent_message = await update.effective_chat.send_message(
            text=MAIN_MENU_TEXT,
            parse_mode="HTML",
            reply_markup=build_main_menu_keyboard("temp"),  # Temporary session_id
            message_thread_id=msg_context.message_thread_id,  # Preserve thread context
        )
        
        # Create session after message is sent (to get message_id)
        session_id = session_store.create_session(
            chat_id=msg_context.chat_id,
            message_id=sent_message.message_id,
            user_id=msg_context.user_id,
            message_thread_id=msg_context.message_thread_id,
        )
        
        # Update message with real session_id
        await sent_message.edit_reply_markup(
            reply_markup=build_main_menu_keyboard(session_id)
        )
        
        logger.info(
            "main_menu_sent",
            session_id=session_id,
            message_id=sent_message.message_id,
        )
    
    except Exception as e:
        logger.error(
            "show_main_menu_error",
            error=str(e),
            user_id=update.effective_user.id if update.effective_user else None,
            chat_id=update.effective_chat.id if update.effective_chat else None,
        )
```

**Tests** (`tests/integration/test_handlers.py`):
- Test /start sends menu in private chat
- Test /menu sends menu in group chat
- Test menu sent with correct thread_id in forum
- Test session created with correct context
- Test error handling (invalid update)

**Acceptance**:
- ✅ Commands work in all chat types
- ✅ Session created and stored correctly
- ✅ Message sent with proper thread_id
- ✅ Tests pass

#### Task 3.3: Callback Query Handler
**Priority**: P1  
**Estimate**: 3 hours  
**File**: `bot/handlers/navigation.py`

**Implementation**:
```python
import structlog
from telegram import Update
from telegram.ext import ContextTypes

from bot.navigation.context import extract_context
from bot.navigation.router import parse_callback_data, navigation_router
from bot.navigation.session import session_store
from bot.ui.messages import (
    ERROR_STALE_MENU,
    ERROR_PROCESSING,
    ERROR_INVALID_CALLBACK,
    ERROR_BOT_RESTARTED,
)

logger = structlog.get_logger()

async def handle_callback_query(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Handle all callback queries from inline buttons.
    
    Flow:
    1. Parse callback_data
    2. Check idempotency (duplicate clicks)
    3. Validate session (not expired, correct context)
    4. Route to section handler
    5. Handle errors gracefully
    """
    query = update.callback_query
    
    try:
        # Always answer callback query (Telegram requirement)
        await query.answer()
        
        # Check for duplicate callback (double-click protection)
        if session_store.is_callback_locked(query.id):
            await query.answer(ERROR_PROCESSING, show_alert=False)
            logger.info("callback_duplicate_ignored", callback_id=query.id)
            return
        
        # Lock callback to prevent duplicates
        session_store.lock_callback(query.id)
        
        # Parse callback data
        callback_data = parse_callback_data(query.data)
        if not callback_data:
            await query.answer(ERROR_INVALID_CALLBACK, show_alert=True)
            logger.warning("callback_invalid_format", data=query.data)
            return
        
        logger.info(
            "callback_received",
            section=callback_data.section,
            session_id=callback_data.session_id,
            user_id=update.effective_user.id,
        )
        
        # Validate session
        session = session_store.get_session(callback_data.session_id)
        if not session:
            await query.answer(ERROR_BOT_RESTARTED, show_alert=True)
            logger.warning(
                "session_not_found",
                session_id=callback_data.session_id,
                user_id=update.effective_user.id,
            )
            return
        
        # Check session context matches
        msg_context = extract_context(update)
        if not session.matches_context(
            msg_context.chat_id,
            query.message.message_id,
            msg_context.message_thread_id,
        ):
            await query.answer(ERROR_STALE_MENU, show_alert=True)
            logger.warning(
                "session_context_mismatch",
                session_id=callback_data.session_id,
                expected_chat=session.chat_id,
                actual_chat=msg_context.chat_id,
            )
            return
        
        # Route to section handler
        handler = navigation_router.get_handler(callback_data.section)
        if not handler:
            await query.answer(ERROR_INVALID_CALLBACK, show_alert=True)
            logger.error(
                "no_handler_for_section",
                section=callback_data.section,
            )
            return
        
        # Execute handler
        await handler(update, context, session)
        
        logger.info(
            "callback_handled",
            section=callback_data.section,
            session_id=callback_data.session_id,
        )
    
    except Exception as e:
        logger.error(
            "callback_handler_error",
            error=str(e),
            callback_data=query.data if query else None,
        )
        try:
            await query.answer(ERROR_INVALID_CALLBACK, show_alert=True)
        except:
            pass  # Best effort
```

**Tests** (`tests/integration/test_navigation.py`):
- Test valid callback routed correctly
- Test duplicate callback returns "Processing"
- Test expired session returns "Restarted"
- Test context mismatch returns "Stale menu"
- Test unknown section returns error
- Test invalid callback_data returns error

**Acceptance**:
- ✅ All edge cases handled gracefully
- ✅ User always gets feedback (answer_callback_query)
- ✅ Errors logged with context
- ✅ Tests pass

#### Task 3.4: Section Placeholder Handlers
**Priority**: P1  
**Estimate**: 2 hours  
**Files**: `bot/handlers/sections/*.py`

**Implementation** (example for `shop.py`, repeat for all 9 sections):
```python
import structlog
from telegram import Update
from telegram.ext import ContextTypes

from bot.navigation.session import MenuSession, session_store
from bot.ui.menu import build_back_button
from bot.ui.messages import get_section_placeholder

logger = structlog.get_logger()

async def shop_handler(update: Update, context: ContextTypes.DEFAULT_TYPE, session: MenuSession) -> None:
    """
    Handle 'Магазин' section (placeholder).
    
    Shows placeholder message with 'Back to Menu' button.
    """
    query = update.callback_query
    
    try:
        # Create new session for back button
        new_session_id = session_store.create_session(
            chat_id=session.chat_id,
            message_id=session.message_id,
            user_id=session.user_id,
            message_thread_id=session.message_thread_id,
        )
        
        # Update message with section content
        await query.edit_message_text(
            text=get_section_placeholder("shop"),
            parse_mode="HTML",
            reply_markup=build_back_button(new_session_id),
        )
        
        logger.info(
            "section_displayed",
            section="shop",
            session_id=new_session_id,
            user_id=session.user_id,
        )
    
    except Exception as e:
        logger.error(
            "section_handler_error",
            section="shop",
            error=str(e),
        )


async def back_to_menu_handler(update: Update, context: ContextTypes.DEFAULT_TYPE, session: MenuSession) -> None:
    """
    Handle 'Back to Menu' button.
    
    Returns user to main menu.
    """
    query = update.callback_query
    
    try:
        from bot.ui.menu import build_main_menu_keyboard
        from bot.ui.messages import MAIN_MENU_TEXT
        
        # Create new session for main menu
        new_session_id = session_store.create_session(
            chat_id=session.chat_id,
            message_id=session.message_id,
            user_id=session.user_id,
            message_thread_id=session.message_thread_id,
        )
        
        # Update message with main menu
        await query.edit_message_text(
            text=MAIN_MENU_TEXT,
            parse_mode="HTML",
            reply_markup=build_main_menu_keyboard(new_session_id),
        )
        
        logger.info(
            "back_to_menu",
            session_id=new_session_id,
            user_id=session.user_id,
        )
    
    except Exception as e:
        logger.error(
            "back_to_menu_error",
            error=str(e),
        )
```

**Sections to implement**:
- `shop.py` → shop_handler
- `market.py` → market_handler
- `profile.py` → profile_handler
- `games.py` → games_handler
- `collection.py` → collection_handler
- `updates.py` → updates_handler
- `chat.py` → chat_handler
- `support.py` → support_handler
- `info.py` → info_handler
- `back_to_menu_handler` in navigation.py or separate file

**Tests** (`tests/integration/test_handlers.py`):
- Test each section handler shows placeholder
- Test back button returns to main menu
- Test new session created on navigation

**Acceptance**:
- ✅ All 9 sections have placeholder handlers
- ✅ Back button works from any section
- ✅ Tests pass

### Phase 4: Bot Application (Day 5)

#### Task 4.1: Main Bot Application
**Priority**: P0  
**Estimate**: 2 hours  
**File**: `bot/main.py`

**Implementation**:
```python
import os
import structlog
from dotenv import load_dotenv
from telegram.ext import Application, CommandHandler, CallbackQueryHandler

from bot.handlers.commands import start_command, menu_command
from bot.handlers.navigation import handle_callback_query
from bot.navigation.router import navigation_router

# Import section handlers
from bot.handlers.sections.shop import shop_handler
from bot.handlers.sections.market import market_handler
from bot.handlers.sections.profile import profile_handler
from bot.handlers.sections.games import games_handler
from bot.handlers.sections.collection import collection_handler
from bot.handlers.sections.updates import updates_handler
from bot.handlers.sections.chat import chat_handler
from bot.handlers.sections.support import support_handler
from bot.handlers.sections.info import info_handler
from bot.handlers.sections.back_to_menu_handler import back_to_menu_handler

logger = structlog.get_logger()

def register_routes() -> None:
    """Register all section handlers with navigation router."""
    navigation_router.register("shop", shop_handler)
    navigation_router.register("market", market_handler)
    navigation_router.register("profile", profile_handler)
    navigation_router.register("games", games_handler)
    navigation_router.register("collection", collection_handler)
    navigation_router.register("updates", updates_handler)
    navigation_router.register("chat", chat_handler)
    navigation_router.register("support", support_handler)
    navigation_router.register("info", info_handler)
    navigation_router.register("back", back_to_menu_handler)
    
    logger.info("routes_registered", routes=navigation_router.list_routes())


def main() -> None:
    """Start the bot."""
    load_dotenv()
    
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    if not token:
        raise ValueError("TELEGRAM_BOT_TOKEN not set in .env")
    
    logger.info("bot_starting")
    
    # Register navigation routes
    register_routes()
    
    # Create application
    application = Application.builder().token(token).build()
    
    # Register command handlers
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("menu", menu_command))
    
    # Register callback query handler
    application.add_handler(CallbackQueryHandler(handle_callback_query))
    
    logger.info("handlers_registered")
    
    # Start bot
    application.run_polling(allowed_updates=["message", "callback_query"])


if __name__ == "__main__":
    main()
```

**Acceptance**:
- ✅ Bot starts successfully
- ✅ All handlers registered
- ✅ Routes registered correctly
- ✅ Responds to /start and /menu

#### Task 4.2: Logging Setup
**Priority**: P1  
**Estimate**: 1 hour  
**File**: `bot/utils/logging.py`

**Implementation**:
```python
import os
import structlog

def setup_logging() -> None:
    """Configure structured logging with structlog."""
    log_level = os.getenv("LOG_LEVEL", "INFO").upper()
    
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(
            getattr(structlog, log_level, structlog.INFO)
        ),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )

# Call on module import
setup_logging()
```

**Acceptance**:
- ✅ JSON logs with structured fields
- ✅ LOG_LEVEL respected from .env
- ✅ Logs include timestamp, level, message

### Phase 5: Testing (Days 5-6)

#### Task 5.1: Unit Tests
**Priority**: P1  
**Estimate**: 3 hours  

**Test Coverage**:
- `tests/unit/test_context.py` → Context extraction
- `tests/unit/test_session.py` → Session management
- `tests/unit/test_router.py` → Callback parsing & routing
- `tests/unit/test_menu_builder.py` → Menu keyboard builders

**Run**:
```bash
uv run pytest tests/unit/ -v --cov=bot --cov-report=term-missing
```

**Target**: ≥90% coverage for unit-tested modules

#### Task 5.2: Integration Tests
**Priority**: P1  
**Estimate**: 4 hours  

**Test Scenarios**:
- `tests/integration/test_handlers.py`:
  - Test /start → menu appears
  - Test /menu → menu appears
  - Test click on section → placeholder appears
  - Test click back → menu appears
  
- `tests/integration/test_navigation.py`:
  - Test expired session → error message
  - Test duplicate callback → processing message
  - Test context mismatch → stale menu error
  - Test invalid callback_data → error message

**Mock Setup**:
```python
# Example mock for Update object
from unittest.mock import AsyncMock, MagicMock
from telegram import Update, User, Chat, Message, CallbackQuery

def create_mock_update(
    chat_type="private",
    user_id=123,
    chat_id=456,
    message_id=789,
    callback_data=None,
):
    update = MagicMock(spec=Update)
    update.effective_user = MagicMock(spec=User)
    update.effective_user.id = user_id
    update.effective_chat = MagicMock(spec=Chat)
    update.effective_chat.id = chat_id
    update.effective_chat.type = chat_type
    update.effective_chat.send_message = AsyncMock()
    update.effective_message = MagicMock(spec=Message)
    update.effective_message.message_id = message_id
    
    if callback_data:
        update.callback_query = MagicMock(spec=CallbackQuery)
        update.callback_query.data = callback_data
        update.callback_query.answer = AsyncMock()
        update.callback_query.edit_message_text = AsyncMock()
    
    return update
```

**Run**:
```bash
uv run pytest tests/integration/ -v
```

**Target**: All integration scenarios pass

#### Task 5.3: Smoke Tests (Manual)
**Priority**: P2  
**Estimate**: 1 hour  

**Test Cases**:
1. **Happy Path**:
   - Send /start → Menu appears
   - Click "Магазин" → Placeholder + back button
   - Click back → Menu appears
   - Click "Профиль" → Placeholder + back button

2. **Group Chat**:
   - Add bot to group
   - Send /menu → Menu appears in group
   - Click section → Works in group

3. **Forum Topic**:
   - Add bot to forum-enabled group
   - Send /menu in topic → Menu appears in topic
   - Click section → Response stays in topic

4. **Edge Cases**:
   - Send /menu twice → Two separate menus
   - Click old menu button → "Stale menu" error
   - Double-click button → "Processing" on second click

**Acceptance**:
- ✅ All manual tests pass
- ✅ No unexpected errors in logs
- ✅ UX feels smooth and responsive

## Edge Case Handling

### EC-001: Устаревшие Callback
**Implementation**: Task 3.3 (Callback Query Handler)  
**Validation**: Session context matching  
**User Feedback**: "⚠️ Это меню устарело. Используйте /menu для нового."

### EC-002: Неизвестный Callback
**Implementation**: Task 3.1 (Router), Task 3.3 (Handler)  
**Validation**: Parser returns None, router returns None  
**User Feedback**: "❌ Ошибка обработки. Попробуйте /menu"

### EC-003: Повторное Нажатие (Double-Click)
**Implementation**: Task 1.3 (Session Store), Task 3.3 (Handler)  
**Validation**: Callback lock with 10-second TTL  
**User Feedback**: "⏳ Обрабатывается..."

### EC-004: Бот Перезапущен
**Implementation**: Task 1.3 (Session Store), Task 3.3 (Handler)  
**Validation**: Session not found in store  
**User Feedback**: "⚠️ Бот был перезапущен. Используйте /menu"

### EC-005: Сообщение Удалено
**Implementation**: Task 3.4 (Section Handlers)  
**Validation**: Catch Telegram API error on edit_message  
**User Feedback**: Log error, no user-facing message (impossible)

## UX Guidelines

### Message Format
- **Length**: 2-4 строки (краткость)
- **Formatting**: HTML (`<b>`, `<i>`)
- **Emojis**: В заголовках и кнопках
- **Structure**:
  ```
  <emoji> <b>Заголовок</b>
  
  Короткое описание (1-2 предложения).
  ```

### Keyboard Layout
- **Main Menu**: 3 × 3 grid (9 buttons)
- **Section Pages**: Content + 1 button ("🔙 Назад в меню")
- **Button Text**: Emoji + Russian text (e.g., "🛒 Магазин")

### Response Time
- **Target**: ≤1 секунда для 95% запросов
- **Strategy**:
  - answer_callback_query() вызывается немедленно
  - Если обработка >2 сек → answer("⏳ Загрузка...")

## Timeline & Milestones

| Phase | Tasks | Days | Completion Criteria |
|-------|-------|------|---------------------|
| **Phase 1** | Core Infrastructure | 1-2 | ✅ Context, Session, Logging working |
| **Phase 2** | Menu UI & Builders | 2-3 | ✅ Menu keyboards built correctly |
| **Phase 3** | Handlers & Routing | 3-5 | ✅ All handlers registered & working |
| **Phase 4** | Bot Application | 5 | ✅ Bot starts, responds to /start |
| **Phase 5** | Testing | 5-6 | ✅ Unit tests ≥90% coverage, integration tests pass |
| **Total** | | **6 days** | ✅ Feature complete & tested |

## Dependencies & Integration

### External Dependencies
- `python-telegram-bot>=21.0` — Telegram Bot API wrapper
- `structlog>=24.1.0` — Structured logging
- `python-dotenv>=1.0.0` — Environment variable management

### Internal Dependencies
- None (this is the first feature)

### Future Integration Points
- **Spec 002** (next): "Магазин" section will replace `shop.py` placeholder
- **Spec 003**: "Рынок" section will replace `market.py` placeholder
- **Spec 004**: "Моя коллекция" section will replace `collection.py` placeholder

## Success Metrics

### Performance
- **Menu Response Time**: 95% of requests ≤1 second
- **Callback Processing**: 100% answered within 2 seconds

### Reliability
- **Error Rate**: <1% of callback queries fail
- **Session Validation**: 100% of stale/expired sessions rejected

### Code Quality
- **Unit Test Coverage**: ≥90% for core modules
- **Integration Tests**: All scenarios pass
- **Linting**: `ruff check` passes with no errors

## Risk Mitigation

### Risk 1: Session Store Memory Leak
**Impact**: High  
**Probability**: Medium  
**Mitigation**:
- Implement TTL for sessions (10 minutes)
- Add periodic cleanup task (every 5 minutes)
- Monitor session store size in logs

### Risk 2: Callback Query Timeout (>5 sec)
**Impact**: Medium  
**Probability**: Low  
**Mitigation**:
- Call answer_callback_query() immediately
- Use "Loading..." message for slow operations
- Set reasonable timeout for operations

### Risk 3: Race Conditions (Rapid Clicks)
**Impact**: Medium  
**Probability**: Medium  
**Mitigation**:
- Implement callback locking (10-second TTL)
- Test with rapid-click scenarios
- Log duplicate callback attempts

## Rollout Plan

### Step 1: Local Testing
- Run bot locally with test token
- Test all scenarios manually
- Verify logs are structured correctly

### Step 2: Staging Deployment
- Deploy to staging server
- Invite test users to group chat
- Monitor logs for errors

### Step 3: Production Deployment
- Deploy to production
- Monitor error rate and response times
- Roll back if error rate >5%

## Future Enhancements (Out of Scope)

- **Session Persistence**: Store sessions in Redis for multi-instance deployments
- **Analytics**: Track button click rates and user navigation paths
- **A/B Testing**: Experiment with different menu layouts
- **Personalization**: Show/hide menu items based on user permissions
- **Rate Limiting**: Prevent spam by limiting command frequency per user

---

## Appendix: Callback Data Format Spec

### Format
```
menu:<section>:<session_id>
```

### Fields
- **action**: Always "menu" for navigation callbacks
- **section**: Section identifier (shop, market, profile, games, collection, updates, chat, support, info, back)
- **session_id**: UUID4 string (36 characters)

### Examples
```
menu:shop:a1b2c3d4-e5f6-7890-abcd-ef1234567890
menu:back:f1e2d3c4-b5a6-9870-dcba-fe0987654321
menu:profile:12345678-1234-5678-1234-567812345678
```

### Constraints
- Total length ≤64 bytes (Telegram limit for callback_data)
- UUID4 format enforced for session_id
- Section must be in predefined list

---

**Plan Review Checklist**:
- ✅ All FR requirements addressed
- ✅ Edge cases handled
- ✅ Test plan defined
- ✅ Timeline realistic
- ✅ UX guidelines clear
- ✅ Dependencies identified
