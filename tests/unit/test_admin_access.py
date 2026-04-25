"""Unit tests for admin-bot access and configuration."""

from unittest.mock import AsyncMock, Mock

import pytest
from telegram import Chat, Message, Update, User
from telegram.ext import ContextTypes

from bot.admin.config import AdminBotSettings, _parse_allowed_ids
from bot.admin.handlers import menu_admin_command, set_admin_settings_for_tests
from bot.admin.session import admin_session_store


@pytest.fixture(autouse=True)
def reset_admin_state():
    admin_session_store.reset()
    set_admin_settings_for_tests(None)
    yield
    admin_session_store.reset()
    set_admin_settings_for_tests(None)


def test_parse_allowed_ids() -> None:
    assert _parse_allowed_ids("1, 2,3") == frozenset({1, 2, 3})


@pytest.mark.asyncio
async def test_admin_menu_rejects_non_private_chat() -> None:
    set_admin_settings_for_tests(
        AdminBotSettings(
            token="token",
            allowed_ids=frozenset({12345}),
        )
    )

    user = Mock(spec=User)
    user.id = 12345
    user.username = "ash"

    chat = Mock(spec=Chat)
    chat.id = -1001
    chat.type = "supergroup"
    chat.send_message = AsyncMock()

    message = Mock(spec=Message)
    message.message_id = 100
    message.chat = chat
    message.from_user = user
    message.message_thread_id = None

    update = Mock(spec=Update)
    update.effective_user = user
    update.effective_chat = chat
    update.effective_message = message
    context = Mock(spec=ContextTypes.DEFAULT_TYPE)

    await menu_admin_command(update, context)

    assert chat.send_message.called
    assert "только в личке" in chat.send_message.call_args.kwargs["text"]


@pytest.mark.asyncio
async def test_admin_menu_rejects_unauthorized_user() -> None:
    set_admin_settings_for_tests(
        AdminBotSettings(
            token="token",
            allowed_ids=frozenset({99999}),
        )
    )

    user = Mock(spec=User)
    user.id = 12345
    user.username = "ash"

    chat = Mock(spec=Chat)
    chat.id = 12345
    chat.type = "private"
    chat.send_message = AsyncMock()

    message = Mock(spec=Message)
    message.message_id = 100
    message.chat = chat
    message.from_user = user
    message.message_thread_id = None

    update = Mock(spec=Update)
    update.effective_user = user
    update.effective_chat = chat
    update.effective_message = message
    context = Mock(spec=ContextTypes.DEFAULT_TYPE)

    await menu_admin_command(update, context)

    assert chat.send_message.called
    assert "нет доступа" in chat.send_message.call_args.kwargs["text"]

