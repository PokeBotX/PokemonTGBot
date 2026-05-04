# VPS Runbook

Короткий operational guide для другого Codex/разработчика, чтобы не гадать, как устроен сервер и как выкатывать изменения.

## Где что живёт

- VPS host: `root@45.95.0.253`
- Repo on server: `/root/pokemonbot`
- Main bot entrypoint: [main.py](/home/deck/Desktop/pokemonbot/main.py)
- Admin bot entrypoint on VPS: [main_admin_local.py](/home/deck/Desktop/pokemonbot/main_admin_local.py)
- Frontend source: [frontend](/home/deck/Desktop/pokemonbot/frontend)
- Exported Mini App static files on VPS: `/var/www/app.pokemoncollection.ru`
- Frontend deploy script: [scripts/deploy_vps_mini_app.sh](/home/deck/Desktop/pokemonbot/scripts/deploy_vps_mini_app.sh)

## Какие сервисы есть

- Main bot service: `pokecollect.service`
- Admin bot service: `pokecollect-admin.service`
- Nginx serves:
  - `https://app.pokemoncollection.ru`
  - storage proxy via `https://app.pokemoncollection.ru/storage/...`

## Что важно понимать

- Main bot работает через `main.py`.
- Admin bot на VPS сейчас работает через `main_admin_local.py`.
- Mini App на сервере не запускается как Next server.
  Он собирается в static export и выкладывается в `/var/www/app.pokemoncollection.ru`.
- Backend API для Mini App живёт в main bot/FastAPI, а не во фронтенде.

## Быстрый вход на сервер

```bash
ssh root@45.95.0.253
cd /root/pokemonbot
```

## Перед любыми DB-изменениями

Сначала сделать бэкап.

```bash
cd /root/pokemonbot
. ./.env
mkdir -p /root/db_backups
STAMP=$(date +%Y%m%d_%H%M%S)
export PGPASSWORD="$DB_PASSWORD"
pg_dump -Fc -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" "$DB_NAME" > "/root/db_backups/pokecollect_${STAMP}.dump"
```

Проверить, что файл реально создался:

```bash
ls -lh /root/db_backups/pokecollect_${STAMP}.dump
```

## Обычный деплой фронта + main bot

Это подходит, когда:
- менялся `frontend/`
- менялся Mini App API/backend
- нужен обычный deploy без ручной возни

```bash
cd /root/pokemonbot
git pull --ff-only origin main_market_guardrails
./scripts/deploy_vps_mini_app.sh main_market_guardrails
```

Что делает скрипт:
- подтягивает ветку
- ставит portable Node в `/opt/node20`, если его нет
- делает `npm ci`
- делает `npm run build -- --webpack`
- публикует static export в `/var/www/app.pokemoncollection.ru`
- reload’ит nginx
- restart’ит `pokecollect.service`

## Когда нужно отдельно применить схему БД

Если менялся [sql/schema.sql](/home/deck/Desktop/pokemonbot/sql/schema.sql), deploy script сам её не применяет.

Нужно сделать отдельно:

```bash
cd /root/pokemonbot
. ./.env
export PGPASSWORD="$DB_PASSWORD"
psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" -f sql/schema.sql
```

После этого обычно стоит перезапустить оба сервиса:

```bash
systemctl restart pokecollect.service pokecollect-admin.service
```

## Когда нужно отдельно перезапустить admin bot

Если менялся только admin runtime:
- [bot/admin](/home/deck/Desktop/pokemonbot/bot/admin)
- [main_admin_local.py](/home/deck/Desktop/pokemonbot/main_admin_local.py)

то можно не гонять полный frontend deploy, а сделать так:

```bash
cd /root/pokemonbot
git pull --ff-only origin main_market_guardrails
systemctl restart pokecollect-admin.service
```

## Полезные проверки после деплоя

Проверить текущий `HEAD`:

```bash
cd /root/pokemonbot
git rev-parse --short HEAD
```

Проверить main bot:

```bash
systemctl status --no-pager pokecollect.service | sed -n '1,12p'
```

Проверить admin bot:

```bash
systemctl status --no-pager pokecollect-admin.service | sed -n '1,12p'
```

Проверить Mini App домен:

```bash
curl -I https://app.pokemoncollection.ru
```

Проверить storage proxy:

```bash
curl -I https://app.pokemoncollection.ru/storage/
```

## Если нужно быстро понять, что именно сломано

Логи main bot:

```bash
journalctl -u pokecollect.service -n 100 --no-pager
```

Логи admin bot:

```bash
journalctl -u pokecollect-admin.service -n 100 --no-pager
```

Логи nginx:

```bash
journalctl -u nginx -n 100 --no-pager
```

## Частые ловушки

- `deploy_vps_mini_app.sh` не применяет `sql/schema.sql`.
- Изменения admin bot не подхватываются, если забыть `systemctl restart pokecollect-admin.service`.
- В Mini App картинки ломаются, если backend отдаёт внутренний MinIO URL вместо `S3_PUBLIC_BASE_URL`.
- Если Telegram временно не резолвит домен для webhook, main bot всё равно должен остаться живым, потому что startup уже защищён retry-логикой.

## Если нужно откатиться

1. Узнать предыдущий commit:

```bash
cd /root/pokemonbot
git log --oneline -n 5
```

2. Переключить repo на нужный commit/branch.
3. Если менялась БД и нужен откат данных, использовать dump из `/root/db_backups`.

## Что сейчас считается нормальным workflow

1. Локально сделать изменения.
2. Прогнать тесты/линт.
3. `git push poke main_market_guardrails`
4. На VPS:
   - `git pull --ff-only origin main_market_guardrails`
   - при необходимости бэкап БД
   - при необходимости `psql -f sql/schema.sql`
   - `./scripts/deploy_vps_mini_app.sh main_market_guardrails`
   - при необходимости `systemctl restart pokecollect-admin.service`
