"""Integration tests for profile flows."""

from datetime import UTC, datetime
from unittest.mock import AsyncMock, Mock

import pytest
from telegram import CallbackQuery, Chat, Message, Update, User
from telegram.ext import ContextTypes

from bot.db.database import PokemonSearchEntry, ProfileCoverCandidate, ProfileRarityProgress, ProfileSummary
from bot.handlers.commands import profile_command, search_command
from bot.handlers.sections.profile import handle_profile_text_input, profile_handler
from bot.navigation.session import MenuSession, session_store


@pytest.fixture(autouse=True)
def clear_sessions() -> None:
    session_store._sessions.clear()
    session_store._callback_locks.clear()
    session_store._pending_inputs.clear()
    yield
    session_store._sessions.clear()
    session_store._callback_locks.clear()
    session_store._pending_inputs.clear()


def _profile_summary(*, profile_pic_credit_id=None) -> ProfileSummary:
    return ProfileSummary(
        user_id=1,
        telegram_id=12345,
        tg_username="ash",
        nickname="Ash",
        language="ru",
        created_at=datetime.now(UTC),
        total_unique_owned=2,
        total_catalog=1025,
        total_unique_percent=0,
        rarity_progress=(
            ProfileRarityProgress("Legendary", 0, 50, 0),
            ProfileRarityProgress("Epic", 1, 100, 1),
        ),
        profile_pic_credit_id=profile_pic_credit_id,
        cover_pokemon_name=None,
    )


@pytest.mark.asyncio
async def test_profile_command_sends_profile_screen() -> None:
    user = Mock(spec=User)
    user.id = 12345
    user.first_name = "Ash"
    user.username = "ash"

    chat = Mock(spec=Chat)
    chat.id = 12345
    chat.type = "private"

    sent_message = Mock(spec=Message)
    sent_message.message_id = 100
    sent_message.edit_reply_markup = AsyncMock()
    bot = Mock()
    bot.send_photo = AsyncMock(return_value=sent_message)
    bot.send_message = AsyncMock(return_value=sent_message)

    message = Mock(spec=Message)
    message.message_id = 99
    message.chat = chat
    message.message_thread_id = None

    update = Mock(spec=Update)
    update.effective_user = user
    update.effective_chat = chat
    update.effective_message = message

    db = AsyncMock()
    db.get_profile_summary = AsyncMock(return_value=_profile_summary())
    application = Mock()
    application.bot_data = {"db": db}
    context = Mock(spec=ContextTypes.DEFAULT_TYPE)
    context.application = application
    context.bot = bot

    await profile_command(update, context)

    assert bot.send_photo.called or bot.send_message.called
    assert sent_message.edit_reply_markup.called


@pytest.mark.asyncio
async def test_profile_nickname_text_flow_updates_settings_message() -> None:
    session = MenuSession(
        session_id="profile-session",
        chat_id=12345,
        message_id=777,
        user_id=12345,
        message_thread_id=None,
    )
    query = AsyncMock(spec=CallbackQuery)
    query.data = "menu:prn:profile-session"
    query.edit_message_text = AsyncMock()

    user = Mock(spec=User)
    user.id = 12345
    user.username = "ash"
    user.first_name = "Ash"

    callback_update = Mock(spec=Update)
    callback_update.callback_query = query
    callback_update.effective_user = user

    db = AsyncMock()
    db.get_profile_summary = AsyncMock(return_value=_profile_summary())
    application = Mock()
    application.bot_data = {"db": db}
    context = Mock(spec=ContextTypes.DEFAULT_TYPE)
    context.application = application

    await profile_handler(callback_update, context, session)
    pending = session_store.get_pending_input(chat_id=12345, user_id=12345)
    assert pending is not None

    chat = Mock(spec=Chat)
    chat.id = 12345
    chat.type = "private"
    chat.send_message = AsyncMock()

    message = Mock(spec=Message)
    message.message_id = 778
    message.chat = chat
    message.message_thread_id = None
    message.text = "New Ash"

    text_update = Mock(spec=Update)
    text_update.effective_chat = chat
    text_update.effective_user = user
    text_update.effective_message = message

    context.bot = Mock()
    context.bot.edit_message_caption = AsyncMock()
    context.bot.edit_message_text = AsyncMock()
    db.update_profile_nickname = AsyncMock(return_value="New Ash")

    await handle_profile_text_input(text_update, context)

    assert db.update_profile_nickname.called
    assert context.bot.edit_message_caption.called or context.bot.edit_message_text.called
    assert chat.send_message.called


@pytest.mark.asyncio
async def test_profile_cover_search_single_match_updates_cover() -> None:
    session_store.set_pending_input(
        action="profile_cover",
        chat_id=12345,
        user_id=12345,
        source_message_id=777,
        source_message_thread_id=None,
    )

    user = Mock(spec=User)
    user.id = 12345
    user.username = "ash"
    user.first_name = "Ash"

    chat = Mock(spec=Chat)
    chat.id = 12345
    chat.type = "private"
    chat.send_message = AsyncMock()

    message = Mock(spec=Message)
    message.message_id = 778
    message.chat = chat
    message.message_thread_id = None
    message.text = "Pikachu"

    update = Mock(spec=Update)
    update.effective_chat = chat
    update.effective_user = user
    update.effective_message = message

    db = AsyncMock()
    db.search_profile_cover_candidates = AsyncMock(
        return_value=[
            ProfileCoverCandidate(
                pokemon_id=25,
                sample_user_pokemon_id=250,
                name="Pikachu",
                rarity="Rare",
                pokemon_type="electric",
                image_credit_id=55,
            )
        ]
    )
    db.update_profile_cover = AsyncMock(return_value=55)
    db.get_profile_summary = AsyncMock(return_value=_profile_summary(profile_pic_credit_id=55))
    application = Mock()
    application.bot_data = {"db": db}
    context = Mock(spec=ContextTypes.DEFAULT_TYPE)
    context.application = application
    context.bot = Mock()
    context.bot.edit_message_caption = AsyncMock()
    context.bot.edit_message_text = AsyncMock()

    await handle_profile_text_input(update, context)

    assert db.search_profile_cover_candidates.called
    assert db.update_profile_cover.called
    assert context.bot.edit_message_caption.called or context.bot.edit_message_text.called


@pytest.mark.asyncio
async def test_search_command_multiple_results_sends_choice_list() -> None:
    user = Mock(spec=User)
    user.id = 12345
    user.first_name = "Ash"
    user.username = "ash"

    chat = Mock(spec=Chat)
    chat.id = 12345
    chat.type = "private"

    sent_message = Mock(spec=Message)
    sent_message.message_id = 130
    sent_message.edit_reply_markup = AsyncMock()
    chat.send_message = AsyncMock(return_value=sent_message)

    message = Mock(spec=Message)
    message.message_id = 121
    message.chat = chat
    message.message_thread_id = None
    message.text = "/search char"

    update = Mock(spec=Update)
    update.effective_chat = chat
    update.effective_user = user
    update.effective_message = message

    db = AsyncMock()
    db.search_pokemon_catalog = AsyncMock(
        return_value=[
            PokemonSearchEntry(4, "Charmander", "Rare", "fire", 39, 52, 43, 65, None),
            PokemonSearchEntry(5, "Charmeleon", "Rare", "fire", 58, 64, 58, 80, None),
        ]
    )
    application = Mock()
    application.bot_data = {"db": db}
    context = Mock(spec=ContextTypes.DEFAULT_TYPE)
    context.application = application

    await search_command(update, context)

    assert chat.send_message.called
    assert sent_message.edit_reply_markup.called
