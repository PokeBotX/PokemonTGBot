"""Integration tests for profile flows."""

from datetime import UTC, datetime
from unittest.mock import AsyncMock, Mock

import pytest
from telegram import CallbackQuery, Chat, Message, Update, User
from telegram.ext import ContextTypes

from bot.db.database import PokemonSearchEntry, ProfileCoverCandidate, ProfileRarityProgress, ProfileSummary
from bot.handlers.commands import changename_command, profile_command, search_command
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
async def test_profile_root_hides_placeholder_buttons() -> None:
    session = MenuSession(
        session_id="profile-root",
        chat_id=12345,
        message_id=700,
        user_id=12345,
        message_thread_id=None,
    )
    query = AsyncMock(spec=CallbackQuery)
    query.data = "menu:profile:profile-root"
    query.edit_message_caption = AsyncMock()
    query.message = Mock(spec=Message)
    query.message.photo = [object()]

    user = Mock(spec=User)
    user.id = 12345
    user.username = "ash"
    user.first_name = "Ash"

    update = Mock(spec=Update)
    update.callback_query = query
    update.effective_user = user

    db = AsyncMock()
    db.get_profile_summary = AsyncMock(return_value=_profile_summary())
    application = Mock()
    application.bot_data = {"db": db}
    context = Mock(spec=ContextTypes.DEFAULT_TYPE)
    context.application = application

    await profile_handler(update, context, session)

    reply_markup = query.edit_message_caption.call_args.kwargs["reply_markup"]
    labels = [button.text for row in reply_markup.inline_keyboard for button in row]
    assert "🛡 Боевая команда" not in labels
    assert "⭐ VIP" not in labels


@pytest.mark.asyncio
async def test_profile_nickname_button_shows_command_hint() -> None:
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
    if query.edit_message_text.called:
        edited_text = query.edit_message_text.call_args.kwargs["text"]
    else:
        edited_text = query.edit_message_caption.call_args.kwargs["caption"]
    assert "/changename Артём" in edited_text
    assert session_store.get_pending_input(chat_id=12345, user_id=12345) is None


@pytest.mark.asyncio
async def test_changename_command_updates_nickname() -> None:
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
    message.text = "/changename New Ash"

    update = Mock(spec=Update)
    update.effective_chat = chat
    update.effective_user = user
    update.effective_message = message

    db = AsyncMock()
    db.update_profile_nickname = AsyncMock(return_value="New Ash")
    application = Mock()
    application.bot_data = {"db": db}
    context = Mock(spec=ContextTypes.DEFAULT_TYPE)
    context.application = application

    await changename_command(update, context)

    assert db.update_profile_nickname.called
    assert chat.send_message.called


@pytest.mark.asyncio
async def test_profile_settings_keyboard_hides_cover_button() -> None:
    session = MenuSession(
        session_id="profile-settings",
        chat_id=12345,
        message_id=777,
        user_id=12345,
        message_thread_id=None,
    )
    query = AsyncMock(spec=CallbackQuery)
    query.data = "menu:prs:profile-settings"
    query.edit_message_caption = AsyncMock()
    query.message = Mock(spec=Message)
    query.message.photo = [object()]

    user = Mock(spec=User)
    user.id = 12345
    user.username = "ash"
    user.first_name = "Ash"

    update = Mock(spec=Update)
    update.callback_query = query
    update.effective_user = user

    db = AsyncMock()
    db.get_profile_summary = AsyncMock(return_value=_profile_summary())
    application = Mock()
    application.bot_data = {"db": db}
    context = Mock(spec=ContextTypes.DEFAULT_TYPE)
    context.application = application

    await profile_handler(update, context, session)

    reply_markup = query.edit_message_caption.call_args.kwargs["reply_markup"]
    labels = [button.text for row in reply_markup.inline_keyboard for button in row]
    assert "🖼 Обложка" not in labels


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


@pytest.mark.asyncio
async def test_search_command_single_result_sends_card_with_market_button() -> None:
    user = Mock(spec=User)
    user.id = 12345
    user.first_name = "Ash"
    user.username = "ash"

    chat = Mock(spec=Chat)
    chat.id = 12345
    chat.type = "private"

    sent_message = Mock(spec=Message)
    sent_message.message_id = 140
    sent_message.edit_reply_markup = AsyncMock()

    message = Mock(spec=Message)
    message.message_id = 122
    message.chat = chat
    message.message_thread_id = None
    message.text = "/search mew"

    update = Mock(spec=Update)
    update.effective_chat = chat
    update.effective_user = user
    update.effective_message = message

    db = AsyncMock()
    db.search_pokemon_catalog = AsyncMock(
        return_value=[
            PokemonSearchEntry(151, "Mew", "Legendary", "psychic", 100, 100, 100, 100, None),
        ]
    )
    application = Mock()
    application.bot_data = {"db": db}
    context = Mock(spec=ContextTypes.DEFAULT_TYPE)
    context.application = application
    context.bot = Mock()
    context.bot.send_photo = AsyncMock(return_value=sent_message)
    context.bot.send_message = AsyncMock(return_value=sent_message)

    await search_command(update, context)

    assert sent_message.edit_reply_markup.called
    reply_markup = sent_message.edit_reply_markup.call_args.kwargs["reply_markup"]
    assert reply_markup.inline_keyboard[0][0].callback_data.startswith("menu:mce:")


@pytest.mark.asyncio
async def test_search_command_numeric_id_sends_exact_card() -> None:
    user = Mock(spec=User)
    user.id = 12345
    user.first_name = "Ash"
    user.username = "ash"

    chat = Mock(spec=Chat)
    chat.id = 12345
    chat.type = "private"

    sent_message = Mock(spec=Message)
    sent_message.message_id = 141
    sent_message.edit_reply_markup = AsyncMock()

    message = Mock(spec=Message)
    message.message_id = 123
    message.chat = chat
    message.message_thread_id = None
    message.text = "/search 151"

    update = Mock(spec=Update)
    update.effective_chat = chat
    update.effective_user = user
    update.effective_message = message

    db = AsyncMock()
    db.get_pokemon_catalog_entry = AsyncMock(
        return_value=PokemonSearchEntry(151, "Mew", "Legendary", "psychic", 100, 100, 100, 100, None)
    )
    application = Mock()
    application.bot_data = {"db": db}
    context = Mock(spec=ContextTypes.DEFAULT_TYPE)
    context.application = application
    context.bot = Mock()
    context.bot.send_photo = AsyncMock(return_value=sent_message)
    context.bot.send_message = AsyncMock(return_value=sent_message)

    await search_command(update, context)

    assert db.get_pokemon_catalog_entry.called
    assert not db.search_pokemon_catalog.called
    assert sent_message.edit_reply_markup.called
