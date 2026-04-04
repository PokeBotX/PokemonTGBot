"""Focused runtime-health helper tests."""

import os
from unittest.mock import AsyncMock, Mock

import pytest
os.environ.setdefault("TELEGRAM_BOT_TOKEN", "test-token")
os.environ.setdefault("WEBHOOK_URL", "https://example.test")

import main
import main_local


def test_build_health_payload_reports_healthy_when_dependencies_ready(monkeypatch) -> None:
    monkeypatch.setattr(main, "DB_ENABLED", True)
    monkeypatch.setattr(main, "REDIS_ENABLED", True)
    monkeypatch.setattr(main, "bot_app", type("BotApp", (), {"bot_data": {"redis_url": "redis://127.0.0.1:6379/0"}})())
    monkeypatch.setattr(main, "db", type("Db", (), {"pool": object()})())

    payload = main._build_health_payload()

    assert payload["status"] == "healthy"
    assert payload["db_connected"] is True
    assert payload["redis_configured"] is True
    assert main._health_status_code(payload) == 200


def test_build_health_payload_reports_degraded_when_enabled_dependency_missing(monkeypatch) -> None:
    monkeypatch.setattr(main, "DB_ENABLED", True)
    monkeypatch.setattr(main, "REDIS_ENABLED", True)
    monkeypatch.setattr(main, "bot_app", type("BotApp", (), {"bot_data": {}})())
    monkeypatch.setattr(main, "db", None)

    payload = main._build_health_payload()

    assert payload["status"] == "degraded"
    assert payload["db_connected"] is False
    assert payload["redis_configured"] is False
    assert main._health_status_code(payload) == 503


@pytest.mark.asyncio
async def test_setup_webhook_respects_drop_pending_updates(monkeypatch) -> None:
    monkeypatch.setattr(main, "DROP_PENDING_UPDATES", True)

    bot = Mock()
    bot.delete_webhook = AsyncMock()
    bot.set_webhook = AsyncMock()
    bot.get_webhook_info = AsyncMock(
        return_value=type(
            "WebhookInfo",
            (),
            {
                "url": "https://example.test/webhook",
                "has_custom_certificate": False,
                "pending_update_count": 0,
            },
        )()
    )
    monkeypatch.setattr(main, "bot_app", type("BotApp", (), {"bot": bot})())

    await main.setup_webhook()

    bot.delete_webhook.assert_awaited_once_with(drop_pending_updates=True)
    assert bot.set_webhook.await_args.kwargs["drop_pending_updates"] is True


@pytest.mark.asyncio
async def test_local_post_init_respects_drop_pending_updates(monkeypatch) -> None:
    monkeypatch.setattr(main_local, "DB_ENABLED", False)
    monkeypatch.setattr(main_local, "REDIS_ENABLED", False)
    monkeypatch.setattr(main_local, "DROP_PENDING_UPDATES", True)

    application = Mock()
    application.bot_data = {}
    application.bot = Mock()
    application.bot.delete_webhook = AsyncMock()
    application.bot.set_my_commands = AsyncMock()

    await main_local.post_init(application)

    application.bot.delete_webhook.assert_awaited_once_with(drop_pending_updates=True)
