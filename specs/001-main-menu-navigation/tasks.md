# Tasks: Bot Menu & Navigation

**Spec**: 001-main-menu-navigation  
**Status**: Ready to Start  
**Created**: 2026-03-04  
**Total Estimated Time**: 6 days  

---

## 📦 Group 1: Каркас меню (Foundation)

### Task 1.1: Настройка проекта и зависимостей
**Priority**: P0 (Blocker)  
**Estimate**: 2 hours  
**Assigned to**: -  
**Status**: Not Started  

**Description**:
Установить все необходимые зависимости и создать структуру каталогов для бота.

**Subtasks**:
1. Обновить `pyproject.toml` с зависимостями:
   - `python-telegram-bot[all]>=21.0`
   - `structlog>=24.1.0`
   - `python-dotenv>=1.0.0`
   - `pytest>=8.0.0` (dev)
   - `pytest-asyncio>=0.23.0` (dev)
   - `pytest-mock>=3.12.0` (dev)

2. Создать структуру каталогов:
   ```bash
   mkdir -p bot/{handlers/sections,ui,navigation,utils}
   mkdir -p tests/{unit,integration}
   touch bot/__init__.py bot/handlers/__init__.py
   touch bot/handlers/sections/__init__.py bot/ui/__init__.py
   touch bot/navigation/__init__.py bot/utils/__init__.py
   touch tests/__init__.py tests/unit/__init__.py tests/integration/__init__.py
   ```

3. Установить зависимости через `uv sync`

**Acceptance Criteria** (как проверить):
- ✅ `uv sync` выполняется без ошибок
- ✅ Все папки `bot/`, `bot/handlers/`, `bot/ui/`, `bot/navigation/`, `bot/utils/` существуют
- ✅ Все `__init__.py` файлы созданы
- ✅ `python-telegram-bot`, `structlog`, `python-dotenv` доступны в виртуальном окружении
- ✅ Команда `uv run python -c "import telegram; print(telegram.__version__)"` работает

**Dependencies**: None

---

### Task 1.2: Настройка structured logging
**Priority**: P0 (Blocker)  
**Estimate**: 1 hour  
**Assigned to**: -  
**Status**: Not Started  

**Description**:
Настроить structured logging с использованием `structlog` для трассируемости действий бота.

**Subtasks**:
1. Создать `bot/utils/logging.py` с конфигурацией structlog
2. Настроить JSON-вывод логов
3. Добавить процессоры: timestamp, log_level, exc_info
4. Уважать переменную окружения `LOG_LEVEL` из `.env`

**Implementation**:
```python
# bot/utils/logging.py
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

**Acceptance Criteria**:
- ✅ Файл `bot/utils/logging.py` создан
- ✅ Импорт `from bot.utils.logging import setup_logging` работает без ошибок
- ✅ Логи выводятся в формате JSON
- ✅ Тестовый лог: `structlog.get_logger().info("test", key="value")` выводит JSON с полями `event`, `key`, `timestamp`, `level`
- ✅ Переменная `LOG_LEVEL=DEBUG` в `.env` меняет уровень логирования

**Dependencies**: Task 1.1

---

### Task 1.3: Context Extraction модуль
**Priority**: P0 (Blocker)  
**Estimate**: 1.5 hours  
**Assigned to**: -  
**Status**: Not Started  

**Description**:
Создать модуль для извлечения контекста из Telegram Update (chat_id, user_id, thread_id).

**Subtasks**:
1. Создать `bot/navigation/context.py`
2. Определить dataclass `MessageContext`
3. Реализовать функцию `extract_context(update: Update) -> MessageContext`
4. Обрабатывать: private chat, group chat, forum topic (thread_id)
5. Выбрасывать `ValueError` для невалидных update

**Implementation**:
```python
# bot/navigation/context.py
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
    """Extract context from Telegram update."""
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

**Acceptance Criteria**:
- ✅ Файл `bot/navigation/context.py` создан
- ✅ `extract_context()` возвращает правильные `chat_id`, `user_id`, `chat_type`
- ✅ `message_thread_id` извлекается корректно для forum topics
- ✅ `ValueError` выбрасывается для update без `effective_chat` или `effective_user`
- ✅ Unit тесты `tests/unit/test_context.py` покрывают все сценарии (private, group, forum, invalid)

**Dependencies**: Task 1.1

---

### Task 1.4: Session Management система
**Priority**: P0 (Blocker)  
**Estimate**: 2 hours  
**Assigned to**: -  
**Status**: Not Started  

**Description**:
Создать систему управления сессиями меню с TTL и callback locking для защиты от двойных нажатий.

**Subtasks**:
1. Создать `bot/navigation/session.py`
2. Определить dataclass `MenuSession` (session_id, chat_id, message_id, thread_id, user_id, TTL)
3. Реализовать класс `SessionStore` с методами:
   - `create_session()` — создать новую сессию
   - `get_session()` — получить сессию (None если истекла)
   - `delete_session()` — удалить сессию
   - `is_callback_locked()` — проверить блокировку callback
   - `lock_callback()` — заблокировать callback
   - `cleanup_expired()` — очистить истекшие сессии
4. Установить TTL сессий: 10 минут
5. Установить TTL callback locks: 10 секунд
6. Создать глобальный `session_store` instance

**Acceptance Criteria**:
- ✅ Файл `bot/navigation/session.py` создан
- ✅ `MenuSession` имеет поля: `session_id`, `chat_id`, `message_id`, `message_thread_id`, `user_id`, `created_at`, `expires_at`
- ✅ `session_store.create_session()` создаёт UUID4 session_id
- ✅ `session_store.get_session()` возвращает `None` для истекших сессий (TTL 10 мин)
- ✅ `session_store.is_callback_locked()` возвращает `True` для дубликатов в течение 10 сек
- ✅ `cleanup_expired()` удаляет старые сессии и locks
- ✅ Unit тесты `tests/unit/test_session.py` покрывают создание, expiration, locking, cleanup

**Dependencies**: Task 1.1

---

### Task 1.5: Message Templates и UI константы
**Priority**: P1  
**Estimate**: 45 minutes  
**Assigned to**: -  
**Status**: Not Started  

**Description**:
Создать файл с текстовыми шаблонами сообщений и метаданными разделов.

**Subtasks**:
1. Создать `bot/ui/messages.py`
2. Определить `MAIN_MENU_TEXT` — приветствие для главного меню
3. Определить `SECTION_PLACEHOLDER_TEMPLATE` — шаблон для заглушек разделов
4. Создать словарь `SECTIONS` с emoji и названиями всех 9 разделов
5. Определить константы для сообщений об ошибках:
   - `ERROR_STALE_MENU` — устаревшее меню
   - `ERROR_PROCESSING` — обрабатывается
   - `ERROR_INVALID_CALLBACK` — неверный callback
   - `ERROR_BOT_RESTARTED` — бот перезапущен

**Acceptance Criteria**:
- ✅ Файл `bot/ui/messages.py` создан
- ✅ `MAIN_MENU_TEXT` содержит HTML-форматированное приветствие (2-3 строки)
- ✅ `SECTIONS` словарь содержит 9 разделов: shop, market, profile, games, collection, updates, chat, support, info
- ✅ Каждый раздел имеет `emoji` и `title`
- ✅ `get_section_placeholder("shop")` возвращает форматированный текст с emoji и заголовком
- ✅ Все error constants определены

**Dependencies**: Task 1.1

---

### Task 1.6: Menu Keyboard Builder
**Priority**: P1  
**Estimate**: 1.5 hours  
**Assigned to**: -  
**Status**: Not Started  

**Description**:
Создать функции для построения inline-клавиатур главного меню и кнопки "Назад".

**Subtasks**:
1. Создать `bot/ui/menu.py`
2. Реализовать `build_main_menu_keyboard(session_id: str) -> InlineKeyboardMarkup`
   - Layout: 3 ряда × 3 кнопки (9 кнопок всего)
   - Callback data: `menu:<section>:<session_id>`
3. Реализовать `build_back_button(session_id: str) -> InlineKeyboardMarkup`
   - Одна кнопка "🔙 Назад в меню"
   - Callback data: `menu:back:<session_id>`

**Acceptance Criteria**:
- ✅ Файл `bot/ui/menu.py` создан
- ✅ `build_main_menu_keyboard()` возвращает клавиатуру с 9 кнопками в 3 рядах
- ✅ Порядок кнопок соответствует спецификации: Магазин|Рынок|Профиль / Мини-игры|Коллекция|Обновления / Чат|Поддержка|Информация
- ✅ Callback data всех кнопок соответствует формату `menu:<section>:<session_id>`
- ✅ `build_back_button()` возвращает клавиатуру с 1 кнопкой
- ✅ Unit тесты `tests/unit/test_menu_builder.py` проверяют структуру клавиатур и формат callback_data

**Dependencies**: Task 1.1

---

## 🎮 Group 2: Command Handlers (/start, /menu)

### Task 2.1: Реализация /start и /menu команд
**Priority**: P1  
**Estimate**: 2 hours  
**Assigned to**: -  
**Status**: Not Started  

**Description**:
Создать handlers для команд `/start` и `/menu`, которые отправляют главное меню.

**Subtasks**:
1. Создать `bot/handlers/commands.py`
2. Реализовать `start_command()` и `menu_command()`
3. Внутренняя функция `_show_main_menu()`:
   - Извлечь context через `extract_context()`
   - Отправить сообщение с временным session_id
   - Создать реальную сессию после получения message_id
   - Обновить клавиатуру с реальным session_id
   - Логировать действие
4. Обрабатывать `message_thread_id` для forum topics
5. Обрабатывать ошибки Telegram API

**Acceptance Criteria**:
- ✅ Файл `bot/handlers/commands.py` создан
- ✅ `/start` отправляет главное меню в личном чате
- ✅ `/menu` отправляет главное меню в групповом чате
- ✅ Меню отправляется с правильным `message_thread_id` в forum topics
- ✅ После отправки создаётся сессия в `session_store`
- ✅ Клавиатура содержит правильный `session_id` в callback_data
- ✅ Логируются события: `show_main_menu`, `main_menu_sent`
- ✅ Ошибки Telegram API логируются с деталями

**Dependencies**: Tasks 1.3, 1.4, 1.5, 1.6

---

## 🔀 Group 3: Callback Router

### Task 3.1: Callback Data Parser
**Priority**: P1  
**Estimate**: 1.5 hours  
**Assigned to**: -  
**Status**: Not Started  

**Description**:
Создать парсер для callback_data в формате `menu:<section>:<session_id>`.

**Subtasks**:
1. Создать `bot/navigation/router.py`
2. Определить dataclass `CallbackData` (action, section, session_id)
3. Реализовать `parse_callback_data(data: str) -> Optional[CallbackData]`
   - Разделить по `:`
   - Проверить формат (3 части)
   - Проверить action == "menu"
   - Вернуть `None` для невалидных данных
   - Логировать ошибки парсинга

**Acceptance Criteria**:
- ✅ Файл `bot/navigation/router.py` создан
- ✅ `parse_callback_data("menu:shop:abc123")` возвращает `CallbackData(action="menu", section="shop", session_id="abc123")`
- ✅ `parse_callback_data("invalid")` возвращает `None`
- ✅ `parse_callback_data("other:shop:abc")` возвращает `None` (неверный action)
- ✅ Невалидные данные логируются с `logger.warning()`
- ✅ Unit тесты `tests/unit/test_router.py` покрывают валидные и невалидные случаи

**Dependencies**: Task 1.2

---

### Task 3.2: Navigation Router класс
**Priority**: P1  
**Estimate**: 1 hour  
**Assigned to**: -  
**Status**: Not Started  

**Description**:
Создать router для регистрации и получения handler'ов для разделов.

**Subtasks**:
1. В `bot/navigation/router.py` создать класс `NavigationRouter`
2. Методы:
   - `register(section: str, handler: Callable)` — зарегистрировать handler
   - `get_handler(section: str) -> Optional[Callable]` — получить handler
   - `list_routes() -> list[str]` — список всех routes
3. Создать глобальный `navigation_router` instance
4. Логировать регистрацию routes

**Acceptance Criteria**:
- ✅ Класс `NavigationRouter` создан в `bot/navigation/router.py`
- ✅ `navigation_router.register("shop", handler_func)` регистрирует handler
- ✅ `navigation_router.get_handler("shop")` возвращает зарегистрированный handler
- ✅ `navigation_router.get_handler("unknown")` возвращает `None`
- ✅ `navigation_router.list_routes()` возвращает список всех зарегистрированных routes
- ✅ Регистрация логируется: `route_registered` с `section`
- ✅ Unit тесты `tests/unit/test_router.py` покрывают регистрацию, получение, list_routes

**Dependencies**: Task 3.1

---

### Task 3.3: Главный Callback Query Handler
**Priority**: P1 (Critical)  
**Estimate**: 3 hours  
**Assigned to**: -  
**Status**: Not Started  

**Description**:
Создать центральный handler для всех callback queries от inline-кнопок.

**Subtasks**:
1. Создать `bot/handlers/navigation.py`
2. Реализовать `handle_callback_query(update, context)`:
   - Всегда вызывать `query.answer()` (требование Telegram)
   - Проверить callback lock (защита от двойных кликов)
   - Парсить callback_data через `parse_callback_data()`
   - Валидировать сессию (существует, не истекла)
   - Проверить context match (chat_id, message_id, thread_id)
   - Получить handler через `navigation_router.get_handler()`
   - Вызвать handler с параметрами (update, context, session)
   - Обрабатывать все ошибки gracefully
3. Использовать константы ошибок из `bot/ui/messages`
4. Логировать все события и ошибки

**Acceptance Criteria**:
- ✅ Файл `bot/handlers/navigation.py` создан
- ✅ Валидный callback успешно роутится к handler'у
- ✅ Duplicate callback (double-click) возвращает `ERROR_PROCESSING`
- ✅ Expired session возвращает `ERROR_BOT_RESTARTED`
- ✅ Context mismatch возвращает `ERROR_STALE_MENU`
- ✅ Невалидный callback_data возвращает `ERROR_INVALID_CALLBACK`
- ✅ Unknown section возвращает `ERROR_INVALID_CALLBACK`
- ✅ `query.answer()` вызывается ВСЕГДА (даже при ошибках)
- ✅ Логируются: `callback_received`, `callback_handled`, `callback_duplicate_ignored`, `session_not_found`, `session_context_mismatch`
- ✅ Integration тесты `tests/integration/test_navigation.py` покрывают все edge cases

**Dependencies**: Tasks 1.3, 1.4, 3.1, 3.2

---

## 📄 Group 4: Экраны разделов (Placeholders)

### Task 4.1: Placeholder handler для одного раздела (template)
**Priority**: P1  
**Estimate**: 1 hour  
**Assigned to**: -  
**Status**: Not Started  

**Description**:
Создать template handler для раздела-заглушки (shop) и использовать как шаблон для остальных.

**Subtasks**:
1. Создать `bot/handlers/sections/shop.py`
2. Реализовать `shop_handler(update, context, session)`:
   - Создать новую сессию для back button
   - Обновить сообщение через `query.edit_message_text()`
   - Текст: `get_section_placeholder("shop")`
   - Клавиатура: `build_back_button(new_session_id)`
   - Логировать: `section_displayed`
   - Обрабатывать ошибки Telegram API

**Acceptance Criteria**:
- ✅ Файл `bot/handlers/sections/shop.py` создан
- ✅ `shop_handler()` обновляет сообщение с placeholder текстом
- ✅ Сообщение содержит кнопку "🔙 Назад в меню"
- ✅ Новая сессия создана для back button
- ✅ Callback_data кнопки: `menu:back:<new_session_id>`
- ✅ Логируется: `section_displayed` с `section="shop"`
- ✅ Ошибки Telegram API обрабатываются и логируются
- ✅ Integration test проверяет переход в раздел и возврат

**Dependencies**: Tasks 1.4, 1.5, 1.6

---

### Task 4.2: Placeholder handlers для остальных 8 разделов
**Priority**: P1  
**Estimate**: 2 hours  
**Assigned to**: -  
**Status**: Not Started  

**Description**:
Создать placeholder handlers для остальных разделов по шаблону `shop_handler`.

**Subtasks**:
1. Создать файлы (по аналогии с `shop.py`):
   - `bot/handlers/sections/market.py` → `market_handler()`
   - `bot/handlers/sections/profile.py` → `profile_handler()`
   - `bot/handlers/sections/games.py` → `games_handler()`
   - `bot/handlers/sections/collection.py` → `collection_handler()`
   - `bot/handlers/sections/updates.py` → `updates_handler()`
   - `bot/handlers/sections/chat.py` → `chat_handler()`
   - `bot/handlers/sections/support.py` → `support_handler()`
   - `bot/handlers/sections/info.py` → `info_handler()`

2. Каждый handler должен:
   - Вызывать `get_section_placeholder(section_name)`
   - Создавать новую сессию
   - Показывать кнопку "Назад в меню"
   - Логировать `section_displayed`

**Acceptance Criteria**:
- ✅ Все 8 файлов созданы в `bot/handlers/sections/`
- ✅ Каждый handler показывает правильный placeholder (с emoji и названием)
- ✅ Все handlers имеют кнопку "🔙 Назад в меню"
- ✅ Логи содержат правильный `section` для каждого handler'а
- ✅ Smoke test: клик на каждую кнопку меню → показывается placeholder → кнопка назад работает

**Dependencies**: Task 4.1

---

## 🔙 Group 5: Кнопка "Назад в меню"

### Task 5.1: Back to Menu handler
**Priority**: P1  
**Estimate**: 1 hour  
**Assigned to**: -  
**Status**: Not Started  

**Description**:
Создать handler для кнопки "🔙 Назад в меню", который возвращает пользователя в главное меню.

**Subtasks**:
1. Создать `bot/handlers/sections/back.py`
2. Реализовать `back_to_menu_handler(update, context, session)`:
   - Создать новую сессию для главного меню
   - Обновить сообщение через `query.edit_message_text()`
   - Текст: `MAIN_MENU_TEXT`
   - Клавиатура: `build_main_menu_keyboard(new_session_id)`
   - Логировать: `back_to_menu`
   - Обрабатывать ошибки Telegram API

**Acceptance Criteria**:
- ✅ Файл `bot/handlers/sections/back.py` создан
- ✅ `back_to_menu_handler()` обновляет сообщение с главным меню
- ✅ Клавиатура содержит все 9 кнопок разделов
- ✅ Новая сессия создана для главного меню
- ✅ Логируется: `back_to_menu` с `session_id`
- ✅ Ошибки Telegram API обрабатываются
- ✅ Integration test: переход в раздел → назад → снова переход в другой раздел

**Dependencies**: Tasks 1.4, 1.5, 1.6

---

### Task 5.2: Регистрация всех handlers в router
**Priority**: P1  
**Estimate**: 30 minutes  
**Assigned to**: -  
**Status**: Not Started  

**Description**:
Зарегистрировать все section handlers и back handler в navigation router.

**Subtasks**:
1. В `bot/main.py` создать функцию `register_routes()`
2. Импортировать все handlers из `bot/handlers/sections/`
3. Зарегистрировать каждый handler в `navigation_router`:
   - `navigation_router.register("shop", shop_handler)`
   - `navigation_router.register("market", market_handler)`
   - ... (все 9 разделов)
   - `navigation_router.register("back", back_to_menu_handler)`
4. Логировать список зарегистрированных routes

**Acceptance Criteria**:
- ✅ Функция `register_routes()` создана в `bot/main.py`
- ✅ Все 10 handlers зарегистрированы (9 разделов + back)
- ✅ `navigation_router.list_routes()` возвращает 10 элементов
- ✅ Лог при старте бота показывает: `routes_registered` с списком routes
- ✅ Клик на любую кнопку меню работает без ошибок

**Dependencies**: Tasks 4.2, 5.1

---

## ⚠️ Group 6: Обработка ошибок

### Task 6.1: Обработка ошибок Telegram API
**Priority**: P2  
**Estimate**: 1.5 hours  
**Assigned to**: -  
**Status**: Not Started  

**Description**:
Добавить graceful обработку ошибок Telegram API во всех handlers.

**Subtasks**:
1. В `bot/handlers/commands.py`:
   - Catch ошибки отправки сообщения (нет прав, чат не найден)
   - Логировать `show_main_menu_error`
2. В section handlers:
   - Catch ошибки редактирования сообщения (сообщение удалено, топик удалён)
   - Логировать `section_handler_error`
3. В `back_to_menu_handler`:
   - Catch ошибки редактирования
   - Логировать `back_to_menu_error`

**Acceptance Criteria**:
- ✅ Ошибки отправки/редактирования сообщений не ломают бота
- ✅ Все ошибки логируются с деталями (error message, chat_id, user_id)
- ✅ Пользователь не видит Python traceback (бот продолжает работать)
- ✅ Test: удалить сообщение с меню → нажать кнопку → ошибка логируется, бот не падает

**Dependencies**: Tasks 2.1, 4.1, 5.1

---

### Task 6.2: Обработка неизвестных callback
**Priority**: P2  
**Estimate**: 1 hour  
**Assigned to**: -  
**Status**: Not Started  

**Description**:
Обрабатывать случаи неизвестных callback_data (не в формате `menu:*:*`).

**Subtasks**:
1. В `handle_callback_query()` проверить результат `parse_callback_data()`
2. Если `None` → отправить `ERROR_INVALID_CALLBACK`
3. Проверить, что handler существует для section
4. Если нет → отправить `ERROR_INVALID_CALLBACK`
5. Логировать все случаи: `callback_invalid_format`, `no_handler_for_section`

**Acceptance Criteria**:
- ✅ Callback с невалидным форматом (`"invalid"`) → пользователь видит "❌ Ошибка обработки"
- ✅ Callback с неизвестным section (`"menu:unknown:abc"`) → пользователь видит "❌ Ошибка обработки"
- ✅ Логируются: `callback_invalid_format`, `no_handler_for_section`
- ✅ Unit test: `parse_callback_data("random_string")` возвращает `None`
- ✅ Integration test: отправить callback с невалидными данными → ошибка handled gracefully

**Dependencies**: Task 3.3

---

### Task 6.3: Edge case — бот перезапущен
**Priority**: P2  
**Estimate**: 30 minutes  
**Assigned to**: -  
**Status**: Not Started  

**Description**:
Обрабатывать случай, когда бот перезапущен, session store очищен, но пользователь нажимает на старую кнопку.

**Subtasks**:
1. В `handle_callback_query()` проверить, что `session_store.get_session()` вернула не `None`
2. Если `None` → отправить `ERROR_BOT_RESTARTED`
3. Логировать: `session_not_found`

**Acceptance Criteria**:
- ✅ После перезапуска бота, клик на старую кнопку → пользователь видит "⚠️ Бот был перезапущен. Используйте /menu"
- ✅ Логируется: `session_not_found` с `session_id`, `user_id`
- ✅ Integration test: создать сессию → удалить из store → нажать кнопку → сообщение об ошибке

**Dependencies**: Task 3.3

---

### Task 6.4: Edge case — устаревшие кнопки (context mismatch)
**Priority**: P2  
**Estimate**: 30 minutes  
**Assigned to**: -  
**Status**: Not Started  

**Description**:
Обрабатывать случай, когда пользователь открыл новое меню, но нажимает на кнопку из старого.

**Subtasks**:
1. В `handle_callback_query()` вызвать `session.matches_context()`
2. Если `False` → отправить `ERROR_STALE_MENU`
3. Логировать: `session_context_mismatch`

**Acceptance Criteria**:
- ✅ Пользователь открыл `/menu` дважды → нажал кнопку из первого меню → видит "⚠️ Это меню устарело"
- ✅ Логируется: `session_context_mismatch` с `expected_chat`, `actual_chat`, `expected_message`, `actual_message`
- ✅ Integration test: создать 2 меню → нажать кнопку из первого → ошибка

**Dependencies**: Task 3.3

---

## ✅ Group 7: Тесты

### Task 7.1: Unit тесты — Context Extraction
**Priority**: P1  
**Estimate**: 1 hour  
**Assigned to**: -  
**Status**: Not Started  

**Description**:
Написать unit тесты для `bot/navigation/context.py`.

**Subtasks**:
1. Создать `tests/unit/test_context.py`
2. Mock `Update` object
3. Тесты:
   - `test_extract_context_private_chat()` — private chat
   - `test_extract_context_group_chat()` — group chat
   - `test_extract_context_forum_topic()` — forum topic с thread_id
   - `test_extract_context_missing_chat()` — ValueError для invalid update
   - `test_extract_context_missing_user()` — ValueError для invalid update

**Acceptance Criteria**:
- ✅ Файл `tests/unit/test_context.py` создан
- ✅ Все 5 тестов проходят
- ✅ Coverage для `bot/navigation/context.py` = 100%
- ✅ `uv run pytest tests/unit/test_context.py -v` — все зелёные

**Dependencies**: Task 1.3

---

### Task 7.2: Unit тесты — Session Management
**Priority**: P1  
**Estimate**: 1.5 hours  
**Assigned to**: -  
**Status**: Not Started  

**Description**:
Написать unit тесты для `bot/navigation/session.py`.

**Subtasks**:
1. Создать `tests/unit/test_session.py`
2. Тесты:
   - `test_create_session()` — создание сессии с UUID4
   - `test_session_expiration()` — сессия истекает через 10 минут (mock datetime)
   - `test_get_expired_session()` — get_session() возвращает None для expired
   - `test_session_matches_context()` — context matching
   - `test_callback_locking()` — duplicate prevention (10 сек TTL)
   - `test_cleanup_expired()` — cleanup удаляет старые сессии и locks

**Acceptance Criteria**:
- ✅ Файл `tests/unit/test_session.py` создан
- ✅ Все 6 тестов проходят
- ✅ Coverage для `bot/navigation/session.py` ≥ 95%
- ✅ `uv run pytest tests/unit/test_session.py -v` — все зелёные

**Dependencies**: Task 1.4

---

### Task 7.3: Unit тесты — Router & Parser
**Priority**: P1  
**Estimate**: 1 hour  
**Assigned to**: -  
**Status**: Not Started  

**Description**:
Написать unit тесты для `bot/navigation/router.py`.

**Subtasks**:
1. Создать `tests/unit/test_router.py`
2. Тесты для parser:
   - `test_parse_callback_data_valid()` — валидный формат
   - `test_parse_callback_data_invalid_format()` — неверный формат
   - `test_parse_callback_data_wrong_action()` — action != "menu"
3. Тесты для router:
   - `test_register_handler()` — регистрация
   - `test_get_handler()` — получение handler'а
   - `test_get_handler_unknown()` — None для unknown section
   - `test_list_routes()` — список routes

**Acceptance Criteria**:
- ✅ Файл `tests/unit/test_router.py` создан
- ✅ Все 7 тестов проходят
- ✅ Coverage для `bot/navigation/router.py` = 100%
- ✅ `uv run pytest tests/unit/test_router.py -v` — все зелёные

**Dependencies**: Tasks 3.1, 3.2

---

### Task 7.4: Unit тесты — Menu Builder
**Priority**: P1  
**Estimate**: 1 hour  
**Assigned to**: -  
**Status**: Not Started  

**Description**:
Написать unit тесты для `bot/ui/menu.py`.

**Subtasks**:
1. Создать `tests/unit/test_menu_builder.py`
2. Тесты:
   - `test_build_main_menu_keyboard()` — 9 кнопок в 3 рядах
   - `test_main_menu_callback_format()` — callback_data формат
   - `test_main_menu_session_id_embedded()` — session_id в callback
   - `test_build_back_button()` — 1 кнопка "Назад"
   - `test_back_button_callback_format()` — callback_data формат

**Acceptance Criteria**:
- ✅ Файл `tests/unit/test_menu_builder.py` создан
- ✅ Все 5 тестов проходят
- ✅ Coverage для `bot/ui/menu.py` = 100%
- ✅ `uv run pytest tests/unit/test_menu_builder.py -v` — все зелёные

**Dependencies**: Task 1.6

---

### Task 7.5: Integration тесты — Handlers
**Priority**: P1  
**Estimate**: 2 hours  
**Assigned to**: -  
**Status**: Not Started  

**Description**:
Написать integration тесты для command и callback handlers.

**Subtasks**:
1. Создать `tests/integration/test_handlers.py`
2. Mock `Update`, `ContextTypes`, `session_store`
3. Тесты:
   - `test_start_command_private_chat()` — /start в личке
   - `test_menu_command_group_chat()` — /menu в группе
   - `test_menu_command_forum_topic()` — /menu в forum topic с thread_id
   - `test_shop_handler_shows_placeholder()` — переход в раздел Магазин
   - `test_back_button_returns_to_menu()` — возврат из раздела в меню
   - `test_session_created_correctly()` — сессия создана с правильными данными

**Acceptance Criteria**:
- ✅ Файл `tests/integration/test_handlers.py` создан
- ✅ Все 6 тестов проходят
- ✅ Mock правильно эмулирует Telegram API
- ✅ `uv run pytest tests/integration/test_handlers.py -v` — все зелёные

**Dependencies**: Tasks 2.1, 4.1, 5.1

---

### Task 7.6: Integration тесты — Navigation & Edge Cases
**Priority**: P1  
**Estimate**: 2 hours  
**Assigned to**: -  
**Status**: Not Started  

**Description**:
Написать integration тесты для навигационного роутера и edge cases.

**Subtasks**:
1. Создать `tests/integration/test_navigation.py`
2. Тесты:
   - `test_valid_callback_routed()` — валидный callback роутится
   - `test_duplicate_callback_returns_processing()` — double-click защита
   - `test_expired_session_returns_error()` — expired session → error
   - `test_context_mismatch_returns_stale_menu()` — старое меню → error
   - `test_invalid_callback_data_returns_error()` — невалидный формат
   - `test_unknown_section_returns_error()` — unknown section → error

**Acceptance Criteria**:
- ✅ Файл `tests/integration/test_navigation.py` создан
- ✅ Все 6 тестов проходят
- ✅ Все edge cases покрыты
- ✅ `uv run pytest tests/integration/test_navigation.py -v` — все зелёные

**Dependencies**: Task 3.3

---

### Task 7.7: Smoke тесты (Manual)
**Priority**: P2  
**Estimate**: 1 hour  
**Assigned to**: -  
**Status**: Not Started  

**Description**:
Провести ручное тестирование основных сценариев с реальным ботом.

**Subtasks**:
1. **Happy Path**:
   - Отправить `/start` → меню появляется
   - Нажать "Магазин" → placeholder + кнопка назад
   - Нажать "Назад" → главное меню
   - Нажать "Профиль" → placeholder + кнопка назад

2. **Group Chat**:
   - Добавить бота в тестовую группу
   - Отправить `/menu` → меню появляется
   - Нажать раздел → работает

3. **Forum Topic** (если доступно):
   - Добавить бота в forum-enabled группу
   - Отправить `/menu` в топике → меню в том же топике
   - Нажать раздел → ответ остаётся в топике

4. **Edge Cases**:
   - Отправить `/menu` дважды → две отдельные меню
   - Нажать кнопку из старого меню → "Устаревшее меню"
   - Быстро дважды кликнуть кнопку → "Обрабатывается..."

**Acceptance Criteria**:
- ✅ Все сценарии Happy Path работают
- ✅ Бот корректно работает в группах
- ✅ Forum topics поддерживаются (если применимо)
- ✅ Edge cases обрабатываются gracefully
- ✅ Нет Python traceback в логах
- ✅ UX чувствуется smooth и быстрым

**Dependencies**: All previous tasks

---

## 🚀 Group 8: Bot Application & Deployment

### Task 8.1: Main Bot Application
**Priority**: P0  
**Estimate**: 1.5 hours  
**Assigned to**: -  
**Status**: Not Started  

**Description**:
Создать главный файл `bot/main.py` для запуска бота.

**Subtasks**:
1. Создать `bot/main.py`
2. Импортировать handlers и router
3. Реализовать функцию `register_routes()`
4. Реализовать функцию `main()`:
   - Загрузить `.env`
   - Получить `TELEGRAM_BOT_TOKEN`
   - Создать `Application`
   - Зарегистрировать command handlers (/start, /menu)
   - Зарегистрировать callback query handler
   - Запустить polling
5. Добавить `if __name__ == "__main__": main()`

**Acceptance Criteria**:
- ✅ Файл `bot/main.py` создан
- ✅ `uv run python bot/main.py` запускает бота
- ✅ Бот успешно подключается к Telegram API
- ✅ В логах: `bot_starting`, `routes_registered`, `handlers_registered`
- ✅ Бот отвечает на `/start` и `/menu`
- ✅ Бот обрабатывает callback queries

**Dependencies**: Tasks 2.1, 3.3, 5.2

---

### Task 8.2: README.md с инструкциями
**Priority**: P2  
**Estimate**: 30 minutes  
**Assigned to**: -  
**Status**: Not Started  

**Description**:
Обновить README.md с инструкциями по запуску бота.

**Subtasks**:
1. Добавить секцию "Setup"
2. Добавить секцию "Running the Bot"
3. Добавить секцию "Testing"
4. Добавить секцию "Project Structure"

**Acceptance Criteria**:
- ✅ `README.md` обновлён
- ✅ Инструкции включают: установку зависимостей, настройку `.env`, запуск бота
- ✅ Упомянуты команды для тестирования: `uv run pytest`
- ✅ Описана структура проекта (папки `bot/`, `tests/`)

**Dependencies**: Task 8.1

---

## 📊 Progress Tracking

### Overall Progress
- **Total Tasks**: 30
- **Completed**: 0
- **In Progress**: 0
- **Not Started**: 30
- **Estimated Total Time**: 37.5 hours (~6 days)

### Group Progress
| Group | Tasks | Estimated Time | Status |
|-------|-------|----------------|--------|
| 1. Каркас меню | 6 | 8.75h | Not Started |
| 2. Command Handlers | 1 | 2h | Not Started |
| 3. Callback Router | 3 | 5.5h | Not Started |
| 4. Экраны разделов | 2 | 3h | Not Started |
| 5. Кнопка "Назад" | 2 | 1.5h | Not Started |
| 6. Обработка ошибок | 4 | 3.5h | Not Started |
| 7. Тесты | 7 | 10.5h | Not Started |
| 8. Deployment | 2 | 2h | Not Started |

---

## 🔗 Task Dependencies Graph

```
Task 1.1 (Setup) ──┬─→ Task 1.2 (Logging)
                   ├─→ Task 1.3 (Context)
                   ├─→ Task 1.4 (Session)
                   ├─→ Task 1.5 (Messages)
                   └─→ Task 1.6 (Menu Builder)

Tasks 1.3, 1.4, 1.5, 1.6 ─→ Task 2.1 (Commands)

Task 1.2 ─→ Task 3.1 (Parser) ─→ Task 3.2 (Router)

Tasks 1.3, 1.4, 3.1, 3.2 ─→ Task 3.3 (Callback Handler)

Tasks 1.4, 1.5, 1.6 ─→ Task 4.1 (Shop Handler) ─→ Task 4.2 (Other Sections)

Tasks 1.4, 1.5, 1.6 ─→ Task 5.1 (Back Handler)

Tasks 4.2, 5.1 ─→ Task 5.2 (Register Routes)

Tasks 2.1, 4.1, 5.1 ─→ Task 6.1 (Error Handling)
Task 3.3 ─→ Tasks 6.2, 6.3, 6.4 (Edge Cases)

Task 1.3 ─→ Task 7.1 (Test Context)
Task 1.4 ─→ Task 7.2 (Test Session)
Tasks 3.1, 3.2 ─→ Task 7.3 (Test Router)
Task 1.6 ─→ Task 7.4 (Test Menu)
Tasks 2.1, 4.1, 5.1 ─→ Task 7.5 (Test Handlers)
Task 3.3 ─→ Task 7.6 (Test Navigation)

Tasks 2.1, 3.3, 5.2 ─→ Task 8.1 (Main App)
Task 8.1 ─→ Task 8.2 (README)

All Tasks ─→ Task 7.7 (Smoke Tests)
```

---

## 🎯 Critical Path (Must-Complete для MVP)

1. **Task 1.1** → Project Setup
2. **Task 1.2** → Logging
3. **Task 1.3** → Context Extraction
4. **Task 1.4** → Session Management
5. **Task 1.5** → Message Templates
6. **Task 1.6** → Menu Builder
7. **Task 2.1** → Command Handlers
8. **Task 3.1** → Callback Parser
9. **Task 3.2** → Navigation Router
10. **Task 3.3** → Callback Handler
11. **Task 4.1** → Shop Handler (template)
12. **Task 4.2** → Other Section Handlers
13. **Task 5.1** → Back Handler
14. **Task 5.2** → Register Routes
15. **Task 8.1** → Main Application
16. **Task 7.7** → Smoke Tests

**Critical Path Time**: ~24 hours (~4 days)

---

## ✅ Definition of Done (общий для всех задач)

Задача считается выполненной, когда:
1. ✅ Код написан и соответствует спецификации
2. ✅ Unit/Integration тесты написаны и проходят
3. ✅ Coverage ≥ 90% для новых модулей
4. ✅ Код проверен линтером (`ruff check`)
5. ✅ Логирование работает (нет silent failures)
6. ✅ Manual testing пройден (для UI-задач)
7. ✅ Ошибки обрабатываются gracefully
8. ✅ Документация обновлена (если нужно)

---

## 📝 Notes

- **Приоритет P0** — блокирующие задачи, без них ничего не работает
- **Приоритет P1** — критичные для MVP, должны быть завершены
- **Приоритет P2** — важные, но не блокирующие (можно отложить)

- **Estimated Time** — оценка для одного разработчика
- **Dependencies** — задачи должны быть завершены перед началом текущей

- Рекомендуется начинать с **Group 1 (Каркас)**, затем параллельно **Groups 2-3**, затем **Groups 4-5**, затем **Group 6**, затем **Group 7**, и наконец **Group 8**.
