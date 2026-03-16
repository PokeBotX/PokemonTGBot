=== PokéCollect Bot - Полная инструкция по запуску с нуля ===

В этом файле описано, как поднять проект локально с чистого окружения.


1. Что потребуется

- Python 3.12+
- uv
- PostgreSQL
- Telegram Bot Token от @BotFather


2. Установка uv

Если `uv` ещё не установлен:

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

После этого перезапусти терминал или проверь, что `uv` доступен в `PATH`.


3. Установка зависимостей проекта

```bash
uv sync
```


4. Создание `.env`

Самый простой способ:

```bash
cp .env.example .env
```

Потом открой `.env` и заполни значения.

Минимальный пример для локального запуска:

```env
TELEGRAM_BOT_TOKEN=your_bot_token_here
LOG_LEVEL=INFO

DB_ENABLED=true
DB_INIT_SCHEMA=true
DB_SCHEMA_PATH=sql/schema.sql

DATABASE_URL=
DB_HOST=127.0.0.1
DB_PORT=5432
DB_NAME=pokecollect
DB_USER=postgres
DB_PASSWORD=postgres

REDIS_ENABLED=false
REDIS_URL=redis://127.0.0.1:6379/0
```

Важно:
- для локального polling-режима `WEBHOOK_URL` не нужен
- если ты используешь `source .env`, не оставляй в файле значения вида `<YOUR_DOMAIN>`, потому что bash воспринимает их как спецсинтаксис


5. Установка и запуск PostgreSQL

Для работы проекта нужен запущенный PostgreSQL и уже созданная база данных.

Создать базу можно, например, так:

```bash
createdb -U postgres pokecollect
```

Или через `psql`:

```sql
CREATE DATABASE pokecollect;
```

Если PostgreSQL не запущен, стартуй его через системный менеджер сервисов твоей ОС.

Проверка подключения:

```bash
pg_isready -h 127.0.0.1 -p 5432
```


6. Инициализация схемы базы

Вариант A: автоматически при старте бота

Укажи в `.env`:

```env
DB_INIT_SCHEMA=true
```

Тогда бот сам применит `sql/schema.sql` при запуске.

Вариант B: применить схему вручную

```bash
psql -h 127.0.0.1 -U postgres -d pokecollect -f sql/schema.sql
```

После первого успешного применения можно вернуть:

```env
DB_INIT_SCHEMA=false
```


7. Импорт каталога покемонов в PostgreSQL

Для работы гачи таблица `pokemon_catalog` должна быть заполнена.

Если файл `pokedex_all_pokemon_with_safebooru.xlsx` лежит в корне проекта, выполни:

```bash
DB_HOST=127.0.0.1 DB_PORT=5432 DB_NAME=pokecollect DB_USER=postgres DB_PASSWORD=postgres uv run python scripts/import_pokedex_xlsx.py
```

Если нужно перезаписать уже существующие записи каталога:

```bash
DB_HOST=127.0.0.1 DB_PORT=5432 DB_NAME=pokecollect DB_USER=postgres DB_PASSWORD=postgres uv run python scripts/import_pokedex_xlsx.py --replace
```


8. Настройка Redis (опционально, но рекомендуется)

Redis нужен для хранения menu session и callback lock не только в памяти, но и во внешнем хранилище.

Самый простой локальный запуск через Docker:

```bash
docker run -d --name pokemonbot-redis -p 127.0.0.1:6379:6379 redis:7-alpine
```

После этого включи Redis в `.env`:

```env
REDIS_ENABLED=true
REDIS_URL=redis://127.0.0.1:6379/0
```

Проверка контейнера:

```bash
docker ps
docker logs pokemonbot-redis
```


9. Локальный запуск бота

Рекомендуемый режим для локальной проверки:

```bash
uv run python main_local.py
```

Этот режим использует Telegram long polling и проще всего подходит для разработки.


10. Как понять, что старт успешен

При нормальном запуске в логах обычно появляются события:

- `routes_registered`
- `db_connected`
- `db_ready`
- `redis_ready` если Redis включён
- `bot_ready`
- `bot_starting`

Если бот стартует, но Telegram API отвечает таймаутами, проблема обычно в сети до `api.telegram.org`, а не в логике проекта.


11. Первый тест в Telegram

1. Открой своего бота в Telegram
2. Отправь `/start`
3. Открой `🛒 Магазин`
4. Если валюты нет, начисли себе `pokedollar` через SQL
5. Проверь:
   - `Бонус`
   - `Покемоны -> Крутка x1`
   - `Предметы`


12. Как выдать себе тестовую валюту

Если знаешь свой Telegram ID, можно начислить `pokedollar` так:

```sql
INSERT INTO user_balances (user_id, currency_id, amount)
VALUES (
    (SELECT id FROM users WHERE tg_user_id = 123456789),
    (SELECT id FROM currencies WHERE code = 'pokedollar'),
    5000
)
ON CONFLICT (user_id, currency_id)
DO UPDATE SET amount = user_balances.amount + EXCLUDED.amount;
```

Проверка баланса:

```sql
SELECT u.id, u.tg_user_id, c.code, ub.amount
FROM user_balances ub
JOIN users u ON u.id = ub.user_id
JOIN currencies c ON c.id = ub.currency_id
WHERE u.tg_user_id = 123456789
  AND c.code = 'pokedollar';
```


13. Полезные SQL-проверки

Проверить, что каталог покемонов импортирован:

```sql
SELECT COUNT(*) FROM pokemon_catalog;
```

Посмотреть покемонов конкретного пользователя:

```sql
SELECT
    up.id AS user_pokemon_id,
    u.tg_user_id,
    pc.name,
    pc.rarity,
    pc.type,
    up.obtained_at
FROM user_pokemon up
JOIN users u ON u.id = up.owner_user_id
JOIN pokemon_catalog pc ON pc.id = up.pokemon_id
WHERE u.tg_user_id = 123456789
ORDER BY up.id DESC;
```

Проверить shop state:

```sql
SELECT *
FROM user_shop_state;
```


14. Запуск тестов

Все тесты:

```bash
uv run pytest -v
```

Только тесты магазина:

```bash
uv run pytest tests/unit/test_shop.py tests/integration/test_shop_flow.py -v
```


15. Частые проблемы

Проблема: `ModuleNotFoundError`

Решение:

```bash
uv sync
uv run python main_local.py
```

Проблема: `DB_NAME is required when DATABASE_URL is not set`

Переменные БД не подхватились. Либо задай их в `.env`, либо запускай так:

```bash
DB_HOST=127.0.0.1 DB_PORT=5432 DB_NAME=pokecollect DB_USER=postgres DB_PASSWORD=postgres uv run python main_local.py
```

Проблема: `Timed out` при старте

Бот не может достучаться до Telegram API.

Проверь:

```bash
curl -I https://api.telegram.org
getent hosts api.telegram.org
```

Если эти команды не работают, проблема в сети, VPN, фаерволе или провайдере.

Проблема: Redis включён, но бот не стартует

Проверь:

```bash
docker ps
docker logs pokemonbot-redis
```

Если контейнер не запущен, можно временно отключить Redis:

```env
REDIS_ENABLED=false
```

Проблема: магазин открывается, но крутки не работают

Проверь:
- PostgreSQL запущен
- `pokemon_catalog` не пустой
- у пользователя есть `pokedollar`
- `image.png` существует в корне проекта

Проблема: новые таблицы или предметы не появились после обновления схемы

Применить схему заново:

```bash
psql -h 127.0.0.1 -U postgres -d pokecollect -f sql/schema.sql
```


16. Рекомендуемый локальный workflow

```bash
uv sync
uv run pytest -q
uv run python main_local.py
```

Если менялась схема БД:

```bash
psql -h 127.0.0.1 -U postgres -d pokecollect -f sql/schema.sql
```

Если менялся каталог покемонов:

```bash
uv run python scripts/import_pokedex_xlsx.py --replace
```
