"""Integration tests for collection flow."""

from unittest.mock import AsyncMock, Mock

import pytest
from telegram import CallbackQuery, Chat, Message, Update, User
from telegram.ext import ContextTypes

from bot.db.database import CollectionEntry, CollectionFilterState, CollectionPage
from bot.handlers.sections.collection import (
    COLLECTION_VIEW_MAIN,
    collection_handler,
    show_collection_screen,
)
from bot.navigation.session import MenuSession, session_store


@pytest.fixture(autouse=True)
def clear_sessions():
    """Clear session store before each test."""
    session_store._sessions.clear()
    session_store._callback_locks.clear()
    yield
    session_store._sessions.clear()
    session_store._callback_locks.clear()


def _entry(pokemon_id: int, name: str, rarity: str, pokemon_type: str, quantity: int) -> CollectionEntry:
    return CollectionEntry(
        pokemon_id=pokemon_id,
        sample_user_pokemon_id=pokemon_id * 10,
        name=name,
        rarity=rarity,
        pokemon_type=pokemon_type,
        quantity=quantity,
        base_hp=10,
        base_attack=20,
        base_defense=30,
        base_stamina=40,
        image_credit_id=None,
    )


def _page(
    entries: list[CollectionEntry],
    filter_state: CollectionFilterState | None = None,
    current_page: int = 1,
    total_pages: int = 1,
) -> CollectionPage:
    return CollectionPage(
        entries=entries,
        filter_state=filter_state or CollectionFilterState(page=current_page),
        total_entries=len(entries),
        current_page=current_page,
        total_pages=total_pages,
    )


@pytest.mark.asyncio
async def test_collection_command_sends_collection_message() -> None:
    user = Mock(spec=User)
    user.id = 12345
    user.username = "ash"

    chat = Mock(spec=Chat)
    chat.id = 12345
    chat.type = "private"

    message = Mock(spec=Message)
    message.message_id = 100
    message.chat = chat
    message.from_user = user
    message.message_thread_id = None

    sent_message = Mock(spec=Message)
    sent_message.message_id = 101
    sent_message.edit_reply_markup = AsyncMock()

    update = Mock(spec=Update)
    update.effective_user = user
    update.effective_chat = chat
    update.effective_message = message
    update.effective_chat.send_message = AsyncMock(return_value=sent_message)

    db = AsyncMock()
    db.get_collection_page = AsyncMock(
        return_value=_page([_entry(25, "Pikachu", "Rare", "electric", 2)])
    )
    application = Mock()
    application.bot_data = {"db": db}
    context = Mock(spec=ContextTypes.DEFAULT_TYPE)
    context.application = application

    await show_collection_screen(update, context)

    assert update.effective_chat.send_message.called
    call_args = update.effective_chat.send_message.call_args
    assert "ваша коллекция" in call_args.kwargs["text"]
    assert "Pikachu x2 | id: 25" in call_args.kwargs["text"]
    assert sent_message.edit_reply_markup.called
    assert len(session_store._sessions) == 1


@pytest.mark.asyncio
async def test_collection_handler_opens_filter_screen() -> None:
    session = MenuSession(
        session_id="collection-session",
        chat_id=12345,
        message_id=100,
        user_id=12345,
        message_thread_id=None,
        data={"collection_filters": CollectionFilterState().to_session_payload(), "collection_screen": COLLECTION_VIEW_MAIN},
    )
    session_store._sessions[session.session_id] = session

    query = AsyncMock(spec=CallbackQuery)
    query.data = f"menu:cfs:{session.session_id}"
    query.edit_message_text = AsyncMock()

    user = Mock(spec=User)
    user.id = 12345
    user.username = "ash"

    chat = Mock(spec=Chat)
    chat.id = 12345
    chat.type = "private"

    message = Mock(spec=Message)
    message.message_id = 100
    message.chat = chat
    message.message_thread_id = None

    update = Mock(spec=Update)
    update.callback_query = query
    update.effective_user = user
    update.effective_chat = chat
    update.effective_message = message

    db = AsyncMock()
    db.get_collection_page = AsyncMock(return_value=_page([_entry(25, "Pikachu", "Rare", "electric", 2)]))
    application = Mock()
    application.bot_data = {"db": db}
    context = Mock(spec=ContextTypes.DEFAULT_TYPE)
    context.application = application

    await collection_handler(update, context, session)

    assert query.edit_message_text.called
    text = query.edit_message_text.call_args.kwargs["text"]
    assert "настройки фильтров" in text


@pytest.mark.asyncio
async def test_collection_handler_toggles_duplicate_filter_and_rerenders() -> None:
    session = MenuSession(
        session_id="collection-dup-session",
        chat_id=12345,
        message_id=100,
        user_id=12345,
        message_thread_id=None,
        data={"collection_filters": CollectionFilterState().to_session_payload(), "collection_screen": COLLECTION_VIEW_MAIN},
    )
    session_store._sessions[session.session_id] = session

    query = AsyncMock(spec=CallbackQuery)
    query.data = f"menu:cfd:{session.session_id}"
    query.edit_message_text = AsyncMock()

    user = Mock(spec=User)
    user.id = 12345
    user.username = "ash"

    chat = Mock(spec=Chat)
    chat.id = 12345
    chat.type = "private"

    message = Mock(spec=Message)
    message.message_id = 100
    message.chat = chat
    message.message_thread_id = None

    update = Mock(spec=Update)
    update.callback_query = query
    update.effective_user = user
    update.effective_chat = chat
    update.effective_message = message

    db = AsyncMock()
    db.get_collection_page = AsyncMock(
        return_value=_page(
            [_entry(25, "Pikachu", "Rare", "electric", 2)],
            CollectionFilterState(duplicates_only=True),
        )
    )
    application = Mock()
    application.bot_data = {"db": db}
    context = Mock(spec=ContextTypes.DEFAULT_TYPE)
    context.application = application

    await collection_handler(update, context, session)

    assert query.edit_message_text.called
    text = query.edit_message_text.call_args.kwargs["text"]
    assert "Только дубликаты: включено" in text


@pytest.mark.asyncio
async def test_collection_detail_button_sends_separate_card_message() -> None:
    session = MenuSession(
        session_id="collection-detail-session",
        chat_id=12345,
        message_id=100,
        user_id=12345,
        message_thread_id=None,
        data={
            "collection_filters": CollectionFilterState().to_session_payload(),
            "collection_screen": COLLECTION_VIEW_MAIN,
            "collection_entries": [_entry(25, "Pikachu", "Rare", "electric", 2).as_session_payload()],
        },
    )

    query = AsyncMock(spec=CallbackQuery)
    query.data = f"menu:cd1:{session.session_id}"

    user = Mock(spec=User)
    user.id = 12345
    user.username = "ash"

    chat = Mock(spec=Chat)
    chat.id = 12345
    chat.type = "private"

    message = Mock(spec=Message)
    message.message_id = 100
    message.chat = chat
    message.message_thread_id = None

    update = Mock(spec=Update)
    update.callback_query = query
    update.effective_user = user
    update.effective_chat = chat
    update.effective_message = message

    bot = Mock()
    bot.send_photo = AsyncMock(return_value=Mock(spec=Message, message_id=200))
    bot.send_message = AsyncMock(return_value=Mock(spec=Message, message_id=201))

    application = Mock()
    application.bot_data = {"db": AsyncMock()}
    context = Mock(spec=ContextTypes.DEFAULT_TYPE)
    context.application = application
    context.bot = bot

    await collection_handler(update, context, session)

    assert bot.send_photo.called or bot.send_message.called
