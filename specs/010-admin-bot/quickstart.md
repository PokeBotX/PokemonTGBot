# Admin Bot Quickstart

## Required Env

```env
ADMIN_BOT_TOKEN=
ADMIN_BOT_ALLOWED_IDS=123456789
```

Optional webhook-specific env:

```env
ADMIN_BOT_WEBHOOK_URL=https://example.com
ADMIN_BOT_WEBHOOK_PATH=/admin-webhook
ADMIN_BOT_WEBHOOK_CERT_PATH=
ADMIN_BOT_HOST=0.0.0.0
ADMIN_BOT_PORT=8001
```

The admin bot reuses the same DB and MinIO env vars as the main bot.

## Local Run

```bash
uv sync
uv run python main_admin_local.py
```

## Webhook Run

```bash
uv run python main_admin.py
```

## Current Functional Slice

- separate token and entrypoint
- private-chat-only access
- allowlist from env
- dedicated admin session store prefixes
- shared confirmation framework
- DB-backed admin audit table
- currency grants
- pokemon grants by `pokemon_id`
- pokemon catalog creation
- image upload to MinIO and variant attachment
- image `source` editing
- image `display_order` / `default` editing

## Verification

```bash
uv run pytest tests/unit/test_admin_access.py tests/unit/test_admin_actions.py tests/unit/test_admin_images.py tests/integration/test_admin_bot_flow.py -v
uv run ruff check main_admin.py main_admin_local.py bot/admin bot/navigation/session.py bot/db/database.py tests/unit/test_admin_access.py tests/unit/test_admin_actions.py tests/unit/test_admin_images.py tests/integration/test_admin_bot_flow.py
```
