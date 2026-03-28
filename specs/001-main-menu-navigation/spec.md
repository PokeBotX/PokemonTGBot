# Spec 001: Main Menu & Navigation System

**Status**: Draft  
**Created**: 2026-03-04  
**Version**: 0.1.0  

## Context & Purpose

Главное меню является точкой входа для всех функций бота PokéCollect. Пользователи должны иметь возможность быстро найти нужный раздел и легко вернуться в меню. Бот должен корректно работать как в личных чатах, так и в групповых чатах, включая тредовые/форумные топики.

**Key Design Goals**:
- Минимальное количество кликов до любого раздела (≤2)
- Единый стиль навигации во всех разделах
- Корректная работа в группах и тредах/топиках
- Устойчивость к повторным нажатиям и устаревшим кнопкам

## User Stories

### US-001: Открыть главное меню (P1)
**As a** пользователь бота  
**I want to** открыть главное меню командой `/start` или `/menu`  
**So that** я могу увидеть все доступные разделы бота

**Acceptance Scenarios**:
```gherkin
Scenario: Открытие меню в личном чате
  Given я нахожусь в личном чате сботом
  When я отправляю команду /start или /menu
  Then бот отправляет сообщение с главным меню
  And сообщение содержит inline-клавиатуру с 9 кнопками
  And кнопки: "🛒 Магазин", "📈 Рынок", "👤 Профиль", "🎮 Мини-игры", "📦 Моя коллекция", "📢 Обновления", "💬 Чат", "🆘 Поддержка", "ℹ️ Информация"

Scenario: Открытие меню в групповом чате
  Given бот добавлен в групповой чат
  When я отправляю команду /start или /menu в группе
  Then бот отправляет сообщение с главным меню в этот же чат
  And сообщение содержит inline-клавиатуру с доступными разделами

Scenario: Открытие меню в треде/топике
  Given бот добавлен в групповой чат с включенными топиками (forum/topics)
  And я нахожусь в конкретном треде/топике
  When я отправляю команду /start или /menu
  Then бот отправляет сообщение с меню в тот же тред/топик
  And не отправляет сообщение в основной чат группы
```

### US-002: Навигация по разделам (P1)
**As a** пользователь бота  
**I want to** перейти в любой раздел из главного меню  
**So that** я могу выполнить нужное действие

**Acceptance Scenarios**:
```gherkin
Scenario: Переход в раздел и возврат в меню
  Given я вижу главное меню с inline-клавиатурой
  When я нажимаю на кнопку любого раздела (например, "📦 Моя коллекция")
  Then бот обновляет сообщение и показывает содержимое раздела
  And в сообщении присутствует кнопка "🔙 Назад в меню"
  When я нажимаю "🔙 Назад в меню"
  Then бот обновляет сообщение и показывает главное меню

Scenario: Навигация из треда/топика
  Given я открыл меню в треде/топике группового чата
  When я нажимаю на любую кнопку раздела
  Then бот обновляет сообщение в том же треде/топике
  And не создает новых сообщений в основном чате группы
  When я нажимаю "🔙 Назад в меню"
  Then бот снова показывает главное меню в том же треде/топике
```

### US-003: Обработка устаревших кнопок (P2)
**As a** пользователь бота  
**I want to** получить понятное сообщение, если нажал на устаревшую кнопку  
**So that** я понимаю, что нужно открыть новое меню

**Acceptance Scenarios**:
```gherkin
Scenario: Нажатие на устаревшую кнопку меню
  Given я получил сообщение с главным меню
  And я открыл новое меню командой /menu
  When я нажимаю на кнопку из старого сообщения
  Then бот отправляет callback answer с текстом "⚠️ Это меню устарело. Используйте /menu для нового."
  And сообщение не обновляется

Scenario: Нажатие на кнопку из другого контекста
  Given я открыл меню в личном чате
  And бот отправил мне сообщение с callback_data "menu:shop:session123"
  When в группе я нажимаю на кнопку с callback_data "menu:shop:sessionXYZ"
  Then бот проверяет соответствие session_id текущему контексту
  And если session не совпадает, отправляет callback answer "⚠️ Используйте актуальное меню"
```

### US-004: Защита от двойных нажатий (P2)
**As a** разработчик  
**I want to** предотвратить обработку повторных нажатий на одну кнопку  
**So that** бот не выполняет одно действие дважды и не отправляет дублирующие сообщения

**Acceptance Scenarios**:
```gherkin
Scenario: Двойное нажатие на кнопку раздела
  Given я вижу главное меню
  When я быстро нажимаю на кнопку "📦 Моя коллекция" дважды
  Then бот обрабатывает только первое нажатие
  And второе нажатие возвращает callback answer "⏳ Обрабатывается..."
  And не создает дублирующих запросов к базе данных

Scenario: Повторное нажатие на "Назад в меню"
  Given я нахожусь в разделе "Магазин"
  When я дважды быстро нажимаю "🔙 Назад в меню"
  Then бот обрабатывает только первое нажатие
  And возвращается в главное меню один раз
```

## Edge Cases & Error Handling

### EC-001: Бот добавлен в группу без прав
**Scenario**: Бот добавлен в групповой чат, но не имеет прав на отправку сообщений  
**Expected**: При вызове `/start` или `/menu` бот пытается отправить сообщение, но получает Telegram API error. Логируется warning с chat_id и причиной ошибки. Пользователю не приходит никакого сообщения (невозможно).

### EC-002: Callback query обработан слишком долго
**Scenario**: Пользователь нажал кнопку, но обработка callback query длится >5 секунд (Telegram timeout)  
**Expected**: Бот вызывает `answer_callback_query` в течение первых 2-3 секунд с текстом "⏳ Загрузка...". Если операция завершилась после таймаута, бот редактирует исходное сообщение или отправляет новое в том же контексте.

### EC-003: Сессия меню истекла
**Scenario**: Пользователь нажал кнопку меню, но session_id больше не существует (истёк TTL)  
**Expected**: Бот отвечает через callback answer: "⚠️ Это меню устарело. Используйте /menu для нового." Сообщение с кнопками не обновляется.

### EC-004: Callback data повреждён или некорректен
**Scenario**: Пользователь (или злоумышленник) отправляет callback query с некорректным форматом callback_data  
**Expected**: Бот логирует warning, отвечает через callback answer: "❌ Ошибка обработки. Попробуйте /menu". Сообщение не изменяется.

### EC-005: Пользователь удалил сообщение с меню
**Scenario**: Пользователь удалил сообщение с главным меню, но бот пытается обновить его  
**Expected**: При попытке `edit_message_*` Telegram API вернёт error "Message to edit not found". Бот логирует info и не выполняет повторных попыток. Пользователю предлагается вызвать `/menu` заново.

### EC-006: Бот не может отправить сообщение в тред (топик удалён)
**Scenario**: Пользователь вызвал меню в треде/топике, но во время обработки топик был удалён  
**Expected**: Telegram API вернёт ошибку. Бот логирует warning с chat_id и thread_id. Не пытается отправить сообщение в основной чат.

### EC-007: Одновременные нажатия на разные кнопки
**Scenario**: Пользователь быстро нажимает "📦 Моя коллекция", затем "📈 Рынок"  
**Expected**: Бот обрабатывает оба нажатия последовательно. Второе нажатие может обновить сообщение до того, как первое завершило загрузку. Финальное состояние сообщения соответствует последнему callback.

### EC-008: Бот перезапущен, но меню осталось активным
**Scenario**: Бот был перезапущен, session store очищен, но пользователь нажимает на кнопку старого меню  
**Expected**: Session_id не найден → бот отвечает: "⚠️ Бот был перезапущен. Используйте /menu". Не обновляет сообщение.

## Functional Requirements

### FR-001: Команды для открытия меню
**Priority**: P1  
**Description**: Бот регистрирует команды `/start` и `/menu`. Обе команды отправляют одно и то же сообщение с главным меню.

### FR-002: Структура главного меню
**Priority**: P1  
**Description**: Главное меню содержит inline-клавиатуру с 9 кнопками в 3 ряда:
- Ряд 1: 🛒 Магазин | 📈 Рынок | 👤 Профиль
- Ряд 2: 🎮 Мини-игры | 📦 Моя коллекция | 📢 Обновления
- Ряд 3: 💬 Чат | 🆘 Поддержка | ℹ️ Информация

Текст сообщения: краткое приветствие и описание функций бота (2-3 предложения).

### FR-003: Callback data для кнопок
**Priority**: P1  
**Description**: Каждая кнопка главного меню содержит callback_data в формате:
```
menu:<section>:<session_id>
```
Где:
- `<section>` — идентификатор раздела (shop, market, profile, games, collection, updates, chat, support, info)
- `<session_id>` — уникальный идентификатор сессии меню (UUID4 или timestamp-based)

### FR-004: Генерация session_id
**Priority**: P1  
**Description**: При отправке главного меню бот генерирует уникальный session_id и сохраняет его в in-memory store (dict или Redis) с TTL 10 минут. Session_id привязывается к `chat_id` и `message_id`.

### FR-005: Проверка актуальности сессии
**Priority**: P1  
**Description**: При получении callback query бот проверяет:
1. Существует ли session_id в store
2. Соответствует ли session chat_id и message_id текущего callback

Если проверки не пройдены → callback answer с сообщением об устаревшем меню.

### FR-006: Ответ на callback query
**Priority**: P1  
**Description**: Бот всегда вызывает `answer_callback_query` в течение 2 секунд после получения callback. Если операция требует времени, сначала отправляется answer "⏳ Загрузка...", затем обновляется сообщение.

### FR-007: Работа в групповых чатах
**Priority**: P1  
**Description**: При вызове `/start` или `/menu` бот определяет тип чата через `update.effective_chat.type`:
- `private` — личный чат
- `group`, `supergroup` — групповой чат
- `channel` — канал (игнорируется)

Сообщение с меню отправляется в тот же чат, где была вызвана команда.

### FR-008: Работа в тредах/топиках
**Priority**: P1  
**Description**: Если команда `/start` или `/menu` вызвана в треде/топике (forum topic), бот определяет `message_thread_id` из `update.effective_message.message_thread_id`. Все сообщения и обновления отправляются с параметром `message_thread_id`, чтобы оставаться в контексте треда.

### FR-009: Контекстная привязка callback
**Priority**: P1  
**Description**: При сохранении session_id в store, бот также сохраняет:
- `chat_id`
- `message_id`
- `message_thread_id` (если есть)

При обработке callback query проверяется соответствие всех трёх параметров.

### FR-010: Кнопка "Назад в меню"
**Priority**: P1  
**Description**: Каждый раздел бота содержит inline-кнопку "🔙 Назад в меню" с callback_data:
```
menu:back:<session_id>
```
При нажатии бот обновляет сообщение и показывает главное меню с новым session_id.

### FR-011: Идемпотентность обработки callback
**Priority**: P2  
**Description**: Бот использует механизм защиты от двойных нажатий:
- Сохраняет `callback_query_id` в in-memory store с TTL 10 секунд
- При повторном получении того же `callback_query_id` отвечает: "⏳ Обрабатывается..." и не выполняет действие повторно

### FR-012: Обработка ошибок Telegram API
**Priority**: P2  
**Description**: При ошибках редактирования сообщения (message deleted, chat not found, etc.) бот:
1. Логирует warning с деталями ошибки
2. Удаляет session_id из store
3. Не пытается повторно обновить сообщение
4. Не отправляет дополнительных сообщений пользователю (если невозможно)

### FR-013: Единый стиль сообщений
**Priority**: P1  
**Description**: Все сообщения главного меню и разделов используют единый формат:
- Эмодзи в заголовках разделов
- Краткий текст (не более 3-4 строк)
- Inline-клавиатура с кнопками
- Markdown или HTML форматирование (единообразно во всех разделах)

### FR-014: Логирование навигационных действий
**Priority**: P2  
**Description**: Бот логирует все навигационные действия:
- Открытие главного меню (команда, chat_id, user_id, message_thread_id)
- Переход в раздел (section, session_id, chat_id, user_id)
- Возврат в меню (session_id, chat_id, user_id)
- Ошибки обработки callback (причина, callback_data, chat_id, user_id)

### FR-015: Placeholder контент разделов
**Priority**: P1  
**Description**: На данном этапе разделы (Магазин, Рынок и т.д.) показывают placeholder сообщение:
```
<Эмодзи> <Название раздела>

Этот раздел находится в разработке.

[🔙 Назад в меню]
```
В следующих спеках будет реализован контент для каждого раздела.

## Key Entities & Data Structures

### MenuSession
**Storage**: In-Memory dict или Redis  
**TTL**: 10 минут  
**Structure**:
```python
{
    "session_id": "uuid4-string",
    "chat_id": int,
    "message_id": int,
    "message_thread_id": Optional[int],
    "user_id": int,
    "created_at": datetime,
}
```

### CallbackProcessingLock
**Storage**: In-Memory dict  
**TTL**: 10 секунд  
**Structure**:
```python
{
    "callback_query_id": "unique-string",
    "processed_at": datetime,
}
```

### MenuButton
**Structure** (Python dataclass):
```python
@dataclass
class MenuButton:
    text: str          # "🛒 Магазин"
    section: str       # "shop"
    emoji: str         # "🛒"
    row: int           # 0, 1, 2
    position: int      # 0, 1, 2
```

## Success Criteria

### SC-001: Время отклика меню
**Metric**: 95% запросов `/start` и `/menu` обрабатываются за ≤1 секунду  
**Measurement**: Логи с timestamp запроса и отправки сообщения

### SC-002: Минимальное количество кликов
**Metric**: Любой раздел доступен за ≤2 клика из главного меню  
**Measurement**: Manual testing (клик на раздел → переход) + (клик на "Назад" → возврат)

### SC-003: Корректность работы в группах
**Metric**: 100% команд `/menu` в групповых чатах отправляют сообщение в тот же чат  
**Measurement**: Integration test с mock чатом типа `group` и `supergroup`

### SC-004: Корректность работы в тредах/топиках
**Metric**: 100% команд `/menu` в тредах отправляют сообщение с правильным `message_thread_id`  
**Measurement**: Integration test с mock топика (forum chat)

### SC-005: Защита от двойных нажатий
**Metric**: 0 случаев дублирования обработки callback query при двойном нажатии  
**Measurement**: Integration test с отправкой двух идентичных callback query

### SC-006: Обработка устаревших кнопок
**Metric**: 100% нажатий на устаревшие кнопки возвращают понятное сообщение об ошибке  
**Measurement**: Test с истёкшим session_id

### SC-007: Единообразие стиля
**Metric**: Все 9 разделов используют одинаковый формат сообщений и кнопок  
**Measurement**: Manual review + automated check структуры inline-клавиатуры

### SC-008: Отсутствие необработанных callback errors
**Metric**: 0 случаев, когда callback query не получил answer в течение 5 секунд  
**Measurement**: Monitoring логов Telegram API errors

## Technical Notes

### Context Detection Strategy
```python
def get_message_context(update: Update) -> dict:
    """Extract chat_id, message_id, and thread_id from update."""
    return {
        "chat_id": update.effective_chat.id,
        "message_id": update.effective_message.message_id,
        "message_thread_id": getattr(update.effective_message, "message_thread_id", None),
        "user_id": update.effective_user.id,
    }
```

### Session ID Generation
```python
import uuid
from datetime import datetime, timedelta

def create_menu_session(context: dict) -> str:
    session_id = str(uuid.uuid4())
    session_store[session_id] = {
        **context,
        "created_at": datetime.utcnow(),
        "expires_at": datetime.utcnow() + timedelta(minutes=10),
    }
    return session_id
```

### Callback Data Parsing
```python
def parse_callback_data(data: str) -> dict:
    """Parse callback_data format: menu:<section>:<session_id>"""
    parts = data.split(":")
    if len(parts) != 3 or parts[0] != "menu":
        raise ValueError("Invalid callback_data format")
    return {
        "action": parts[0],      # "menu"
        "section": parts[1],     # "shop", "back", etc.
        "session_id": parts[2],  # UUID4
    }
```

## Dependencies & Integration Points

- **python-telegram-bot**: Используется для регистрации command handlers и callback query handlers
- **Session Store**: In-memory dict (для MVP) или Redis (для production)
- **Logging**: structlog для трассируемости навигационных действий
- **Future Integration**: Разделы "Магазин", "Рынок", "Профиль" будут реализованы в отдельных спеках и интегрируются через единый паттерн callback routing

## Out of Scope

- Реализация контента разделов (placeholder на данном этапе)
- Персонализация меню на основе прав пользователя
- A/B тестирование разных вариантов расположения кнопок
- Анимации и интерактивные эффекты в Telegram UI
- Мультиязычность (пока только русский язык)

---

**Review Notes**:
- Требуется согласование emoji для кнопок меню
- Требуется определить формат логирования навигационных действий (JSON или key-value)
- Placeholder контент разделов будет заменён в последующих спеках
