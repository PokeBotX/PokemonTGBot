"""Configuration helpers for the admin bot."""

from __future__ import annotations

import os
from dataclasses import dataclass


def _parse_allowed_ids(raw_value: str) -> frozenset[int]:
    allowed_ids: set[int] = set()
    for chunk in raw_value.split(","):
        normalized = chunk.strip()
        if not normalized:
            continue
        allowed_ids.add(int(normalized))
    return frozenset(allowed_ids)


@dataclass(frozen=True, slots=True)
class AdminBotSettings:
    """Runtime configuration for the second admin bot."""

    token: str
    allowed_ids: frozenset[int]
    webhook_url: str | None = None
    webhook_path: str = "/admin-webhook"
    webhook_cert_path: str | None = None
    host: str = "0.0.0.0"
    port: int = 8001

    def is_allowed(self, telegram_id: int) -> bool:
        """Return True when the Telegram user id is in the superadmin allowlist."""
        return telegram_id in self.allowed_ids


def load_admin_bot_settings() -> AdminBotSettings:
    """Load admin-bot settings from environment variables."""
    token = (os.getenv("ADMIN_BOT_TOKEN") or "").strip()
    if not token:
        raise ValueError("ADMIN_BOT_TOKEN not set in .env")

    raw_allowed_ids = (os.getenv("ADMIN_BOT_ALLOWED_IDS") or "").strip()
    if not raw_allowed_ids:
        raise ValueError("ADMIN_BOT_ALLOWED_IDS not set in .env")

    allowed_ids = _parse_allowed_ids(raw_allowed_ids)
    if not allowed_ids:
        raise ValueError("ADMIN_BOT_ALLOWED_IDS must contain at least one Telegram user id")

    webhook_url = (os.getenv("ADMIN_BOT_WEBHOOK_URL") or "").strip() or None
    webhook_path = (os.getenv("ADMIN_BOT_WEBHOOK_PATH") or "/admin-webhook").strip() or "/admin-webhook"
    webhook_cert_path = (os.getenv("ADMIN_BOT_WEBHOOK_CERT_PATH") or "").strip() or None
    host = (os.getenv("ADMIN_BOT_HOST") or "0.0.0.0").strip() or "0.0.0.0"
    port = int(os.getenv("ADMIN_BOT_PORT", "8001"))

    return AdminBotSettings(
        token=token,
        allowed_ids=allowed_ids,
        webhook_url=webhook_url,
        webhook_path=webhook_path,
        webhook_cert_path=webhook_cert_path,
        host=host,
        port=port,
    )

