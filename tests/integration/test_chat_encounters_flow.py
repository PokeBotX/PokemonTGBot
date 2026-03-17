"""Integration tests for chat encounter command flow."""

from unittest.mock import AsyncMock, Mock

import pytest
from telegram import Chat, Message, Update, User
from telegram.ext import ContextTypes

from bot.db.database import ChatEncounter, ChatEncounterAttemptResult, CollectionEntry
from bot.handlers.commands import search_command
from bot.handlers.sections.chat_encounters import handle_encounter_callback


def _encounter() -> ChatEncounter:
    from datetime import UTC, datetime, timedelta

    now = datetime.now(UTC)
    return ChatEncounter(
        encounter_id=1,
        chat_id=-1001,
        message_thread_id=None,
        encounter_message_id=None,
        pokemon_id=382,
        name="Kyogre",
        rarity="Legendary",
        pokemon_type="water",
        image_credit_id=None,
        spawned_at=now,
        expires_at=now + timedelta(minutes=5),
        status="active",
        caught_by_user_id=None,
        caught_user_pokemon_id=None,
        caught_with_item_code=None,
    )


def _caught_encounter() -> ChatEncounter:
    from datetime import UTC, datetime, timedelta

    now = datetime.now(UTC)
    return ChatEncounter(
        encounter_id=1,
        chat_id=-1001,
        message_thread_id=None,
        encounter_message_id=77,
        pokemon_id=382,
        name="Kyogre",
        rarity="Legendary",
        pokemon_type="water",
        image_credit_id=None,
        spawned_at=now,
        expires_at=now + timedelta(minutes=5),
        status="caught",
        caught_by_user_id=1,
        caught_user_pokemon_id=999,
        caught_with_item_code="pokeball",
    )


@pytest.mark.asyncio
async def test_search_command_in_private_chat_rejects() -> None:
    user = Mock(spec=User)
    user.id = 1
    user.username = "ash"

    chat = Mock(spec=Chat)
    chat.id = 1
    chat.type = "private"
    chat.send_message = AsyncMock()

    message = Mock(spec=Message)
    message.message_id = 10
    message.chat = chat
    message.message_thread_id = None

    update = Mock(spec=Update)
    update.effective_user = user
    update.effective_chat = chat
    update.effective_message = message

    context = Mock(spec=ContextTypes.DEFAULT_TYPE)
    context.application = Mock()
    context.application.bot_data = {}

    await search_command(update, context)

    assert chat.send_message.called
    assert "только в чатах" in chat.send_message.call_args.args[0].lower()


@pytest.mark.asyncio
async def test_search_command_in_group_sends_encounter() -> None:
    user = Mock(spec=User)
    user.id = 1
    user.username = "ash"
    user.is_bot = False

    chat = Mock(spec=Chat)
    chat.id = -1001
    chat.type = "group"
    chat.send_photo = AsyncMock(return_value=Mock(spec=Message, message_id=77))
    chat.send_message = AsyncMock(return_value=Mock(spec=Message, message_id=78))

    message = Mock(spec=Message)
    message.message_id = 10
    message.chat = chat
    message.message_thread_id = None

    update = Mock(spec=Update)
    update.effective_user = user
    update.effective_chat = chat
    update.effective_message = message

    db = AsyncMock()
    db.get_or_create_user = AsyncMock(return_value=1)
    db.trigger_search_encounter = AsyncMock(return_value=_encounter())
    db.attach_chat_encounter_message = AsyncMock()
    application = Mock()
    application.bot_data = {"db": db}
    context = Mock(spec=ContextTypes.DEFAULT_TYPE)
    context.application = application
    context.job_queue = None

    await search_command(update, context)

    assert db.trigger_search_encounter.called
    assert chat.send_photo.called or chat.send_message.called
    assert db.attach_chat_encounter_message.called


@pytest.mark.asyncio
async def test_failed_encounter_attempt_sends_public_message() -> None:
    user = Mock(spec=User)
    user.id = 1
    user.username = "ash"
    user.first_name = "Ash"

    chat = Mock(spec=Chat)
    chat.id = -1001
    chat.type = "group"

    message = Mock(spec=Message)
    message.message_id = 77
    message.chat = chat
    message.message_thread_id = None
    message.reply_text = AsyncMock()
    message.photo = []

    query = Mock()
    query.data = "enc:1:pokeball"
    query.message = message
    query.answer = AsyncMock()

    update = Mock(spec=Update)
    update.callback_query = query
    update.effective_user = user

    db = AsyncMock()
    db.attempt_chat_encounter = AsyncMock(
        return_value=ChatEncounterAttemptResult(
            status="failed",
            encounter=_encounter(),
            ball_code="pokeball",
        )
    )
    application = Mock()
    application.bot_data = {"db": db}
    context = Mock(spec=ContextTypes.DEFAULT_TYPE)
    context.application = application

    await handle_encounter_callback(update, context)

    assert message.reply_text.called
    assert "вырвался" in message.reply_text.call_args.args[0].lower()
    query.answer.assert_awaited()


@pytest.mark.asyncio
async def test_caught_encounter_adds_card_button() -> None:
    user = Mock(spec=User)
    user.id = 1
    user.username = "ash"
    user.first_name = "Ash"

    chat = Mock(spec=Chat)
    chat.id = -1001
    chat.type = "group"

    message = Mock(spec=Message)
    message.message_id = 77
    message.chat = chat
    message.message_thread_id = None
    message.photo = [Mock()]

    query = Mock()
    query.data = "enc:1:pokeball"
    query.message = message
    query.answer = AsyncMock()
    query.edit_message_caption = AsyncMock()

    update = Mock(spec=Update)
    update.callback_query = query
    update.effective_user = user

    db = AsyncMock()
    db.attempt_chat_encounter = AsyncMock(
        return_value=ChatEncounterAttemptResult(
            status="caught",
            encounter=_caught_encounter(),
            caught=True,
            ball_code="pokeball",
            catcher_label="@ash",
        )
    )
    application = Mock()
    application.bot_data = {"db": db}
    context = Mock(spec=ContextTypes.DEFAULT_TYPE)
    context.application = application

    await handle_encounter_callback(update, context)

    reply_markup = query.edit_message_caption.call_args.kwargs["reply_markup"]
    assert reply_markup.inline_keyboard[0][0].callback_data == "enc:1:card"


@pytest.mark.asyncio
async def test_view_card_button_sends_card_message() -> None:
    user = Mock(spec=User)
    user.id = 2
    user.username = "misty"
    user.first_name = "Misty"

    chat = Mock(spec=Chat)
    chat.id = -1001
    chat.type = "group"

    message = Mock(spec=Message)
    message.message_id = 77
    message.chat = chat
    message.message_thread_id = None

    query = Mock()
    query.data = "enc:1:card"
    query.message = message
    query.answer = AsyncMock()

    update = Mock(spec=Update)
    update.callback_query = query
    update.effective_user = user

    db = AsyncMock()
    db.get_chat_encounter = AsyncMock(return_value=_caught_encounter())
    db.get_user_pokemon_entry = AsyncMock(
        return_value=CollectionEntry(
            pokemon_id=382,
            sample_user_pokemon_id=999,
            name="Kyogre",
            rarity="Legendary",
            pokemon_type="water",
            quantity=1,
            base_hp=100,
            base_attack=100,
            base_defense=90,
            base_stamina=95,
            image_credit_id=None,
        )
    )
    application = Mock()
    application.bot_data = {"db": db}
    context = Mock(spec=ContextTypes.DEFAULT_TYPE)
    context.application = application
    context.bot = Mock()
    context.bot.send_photo = AsyncMock()
    context.bot.send_message = AsyncMock()

    await handle_encounter_callback(update, context)

    assert context.bot.send_photo.called or context.bot.send_message.called
    query.answer.assert_awaited_with("Карточка открыта.", show_alert=False)
