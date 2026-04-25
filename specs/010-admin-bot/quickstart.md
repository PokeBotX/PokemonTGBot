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

## Current Foundation Slice

- separate token and entrypoint
- private-chat-only access
- allowlist from env
- dedicated admin session store prefixes
- shared confirmation framework
- DB-backed admin audit table

## Next Functional Slices

1. currency grant
2. pokemon grant
3. pokemon creation
4. image upload and variant management

