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


def test_resolve_mini_app_identity_dev_fallback_is_limited_to_localhost(monkeypatch) -> None:
    monkeypatch.setattr(main, "MINI_APP_DEV_FALLBACK_ENABLED", True)
    monkeypatch.setattr(main, "MINI_APP_DEV_FALLBACK_TELEGRAM_ID", 1640978922)
    monkeypatch.setattr(main, "MINI_APP_DEV_FALLBACK_USERNAME", "termenater")

    telegram_id, username = main._resolve_mini_app_identity(
        x_telegram_init_data=None,
        x_dev_telegram_id="1640978922",
        request_host="127.0.0.1:3000",
    )

    assert (telegram_id, username) == (1640978922, "termenater")

    with pytest.raises(main.HTTPException) as exc_info:
        main._resolve_mini_app_identity(
            x_telegram_init_data=None,
            x_dev_telegram_id="1640978922",
            request_host="app.pokemoncollection.ru",
        )

    assert exc_info.value.status_code == 401


@pytest.mark.asyncio
async def test_setup_webhook_respects_drop_pending_updates(monkeypatch) -> None:
    monkeypatch.setattr(main, "DROP_PENDING_UPDATES", True)

    bot = Mock()
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

    assert bot.set_webhook.await_args.kwargs["drop_pending_updates"] is True


@pytest.mark.asyncio
async def test_setup_webhook_reuses_existing_url_after_dns_failure(monkeypatch) -> None:
    monkeypatch.setattr(main, "DROP_PENDING_UPDATES", False)

    bot = Mock()
    bot.set_webhook = AsyncMock(side_effect=main.BadRequest("Bad webhook: failed to resolve host: temporary failure in name resolution"))
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

    assert bot.set_webhook.await_count == 3
    bot.get_webhook_info.assert_awaited()


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
