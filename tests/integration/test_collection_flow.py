"""Integration tests for collection flow."""

from types import SimpleNamespace
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
    query.message = Mock(spec=Message)
    query.message.photo = []
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
    query.message = Mock(spec=Message)
    query.message.photo = []
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

    db = AsyncMock()
    db.get_pokemon_image_selection = AsyncMock(
        return_value=SimpleNamespace(
            image_credit_id=55,
            source_url="https://example.com/alt",
            position=2,
            total=3,
        )
    )
    db.get_active_trade_for_user = AsyncMock(return_value=None)
    application = Mock()
    application.bot_data = {"db": db}
    context = Mock(spec=ContextTypes.DEFAULT_TYPE)
    context.application = application
    context.bot = bot

    await collection_handler(update, context, session)

    assert bot.send_photo.called or bot.send_message.called


@pytest.mark.asyncio
async def test_collection_detail_card_shows_image_switch_button_for_multiple_variants() -> None:
    session = MenuSession(
        session_id="collection-image-session",
        chat_id=12345,
        message_id=100,
        user_id=12345,
        message_thread_id=None,
        data={
            "collection_filters": CollectionFilterState().to_session_payload(),
            "collection_screen": COLLECTION_VIEW_MAIN,
            "collection_entries": [_entry(25, "Pikachu", "Rare", "electric", 1).as_session_payload()],
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

    sent_message = Mock(spec=Message)
    sent_message.message_id = 200
    sent_message.edit_reply_markup = AsyncMock()

    update = Mock(spec=Update)
    update.callback_query = query
    update.effective_user = user
    update.effective_chat = chat
    update.effective_message = message

    bot = Mock()
    bot.send_photo = AsyncMock(return_value=sent_message)
    bot.send_message = AsyncMock(return_value=sent_message)

    db = AsyncMock()
    db.get_pokemon_image_selection = AsyncMock(
        return_value=SimpleNamespace(
            image_credit_id=55,
            source_url="https://example.com/alt",
            position=2,
            total=3,
        )
    )
    db.get_active_trade_for_user = AsyncMock(return_value=None)
    application = Mock()
    application.bot_data = {"db": db}
    context = Mock(spec=ContextTypes.DEFAULT_TYPE)
    context.application = application
    context.bot = bot

    await collection_handler(update, context, session)

    keyboard = sent_message.edit_reply_markup.call_args.kwargs["reply_markup"]
    labels = [button.text for row in keyboard.inline_keyboard for button in row]
    assert "🖼 2/3" in labels


@pytest.mark.asyncio
async def test_collection_detail_with_duplicates_opens_instance_picker_first() -> None:
    session = MenuSession(
        session_id="collection-instance-session",
        chat_id=12345,
        message_id=100,
        user_id=12345,
        message_thread_id=None,
        data={
            "collection_filters": CollectionFilterState().to_session_payload(),
            "collection_screen": COLLECTION_VIEW_MAIN,
            "collection_entries": [_entry(25, "Pikachu", "Rare", "electric", 3).as_session_payload()],
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

    picker_message = Mock(spec=Message)
    picker_message.message_id = 202
    picker_message.edit_reply_markup = AsyncMock()

    bot = Mock()
    bot.send_message = AsyncMock(return_value=picker_message)
    bot.send_photo = AsyncMock()

    db = AsyncMock()
    db.get_user_pokemon_instances_for_species = AsyncMock(
        return_value=[
            _entry(25, "Pikachu", "Rare", "electric", 1),
            CollectionEntry(
                pokemon_id=25,
                sample_user_pokemon_id=251,
                name="Pikachu",
                rarity="Rare",
                pokemon_type="electric",
                quantity=1,
                base_hp=10,
                base_attack=20,
                base_defense=30,
                base_stamina=40,
                image_credit_id=None,
            ),
            CollectionEntry(
                pokemon_id=25,
                sample_user_pokemon_id=252,
                name="Pikachu",
                rarity="Rare",
                pokemon_type="electric",
                quantity=1,
                base_hp=10,
                base_attack=20,
                base_defense=30,
                base_stamina=40,
                image_credit_id=None,
            ),
        ]
    )
    application = Mock()
    application.bot_data = {"db": db}
    context = Mock(spec=ContextTypes.DEFAULT_TYPE)
    context.application = application
    context.bot = bot

    await collection_handler(update, context, session)

    assert db.get_user_pokemon_instances_for_species.called
    assert bot.send_message.called
    assert bot.send_photo.call_count == 0
    picker_text = bot.send_message.call_args.kwargs["text"]
    assert "Выберите экземпляр покемона" in picker_text
    assert "<code>250</code>" in picker_text


@pytest.mark.asyncio
async def test_collection_release_flow_renders_confirmation_and_result() -> None:
    session = MenuSession(
        session_id="collection-release-session",
        chat_id=12345,
        message_id=220,
        user_id=12345,
        message_thread_id=None,
        data={
            "release_user_pokemon_id": 250,
            "release_pokemon_name": "Pikachu",
            "release_rarity": "Rare",
        },
    )

    user = Mock(spec=User)
    user.id = 12345
    user.username = "ash"

    query = AsyncMock(spec=CallbackQuery)
    query.data = f"menu:pkr:{session.session_id}"
    query.message = Mock(spec=Message)
    query.message.photo = []
    query.edit_message_text = AsyncMock()
    query.answer = AsyncMock()

    update = Mock(spec=Update)
    update.callback_query = query
    update.effective_user = user

    context = Mock(spec=ContextTypes.DEFAULT_TYPE)
    context.application = Mock()
    db = AsyncMock()
    db.get_user_pokemon_entry = AsyncMock(return_value=_entry(25, "Pikachu", "Rare", "electric", 1))
    context.application.bot_data = {"db": db}

    await collection_handler(update, context, session)

    assert query.edit_message_text.called
    confirmation_text = query.edit_message_text.call_args.kwargs["text"]
    assert "Отпустить покемона" in confirmation_text
    assert "🪙 <b>100</b>" in confirmation_text

    reply_markup = query.edit_message_text.call_args.kwargs["reply_markup"]
    confirm_callback = reply_markup.inline_keyboard[0][0].callback_data
    confirm_session_id = confirm_callback.split(":")[-1]
    confirm_session = session_store._sessions[confirm_session_id]
    assert confirm_session.data["release_user_pokemon_id"] == 250
    assert confirm_session.data["release_pokemon_name"] == "Pikachu"
    assert confirm_session.data["release_rarity"] == "Rare"

    confirm_query = AsyncMock(spec=CallbackQuery)
    confirm_query.data = confirm_callback
    confirm_query.message = Mock(spec=Message)
    confirm_query.message.photo = []
    confirm_query.edit_message_text = AsyncMock()
    confirm_query.answer = AsyncMock()

    confirm_update = Mock(spec=Update)
    confirm_update.callback_query = confirm_query
    confirm_update.effective_user = user

    db = AsyncMock()
    db.release_user_pokemon = AsyncMock(
        return_value=SimpleNamespace(
            name="Pikachu",
            rarity="Rare",
            reward_amount=100,
        )
    )
    confirm_context = Mock(spec=ContextTypes.DEFAULT_TYPE)
    confirm_context.application = Mock()
    confirm_context.application.bot_data = {"db": db}

    await collection_handler(confirm_update, confirm_context, confirm_session)

    assert db.release_user_pokemon.called
    assert confirm_query.edit_message_text.called
    released_text = confirm_query.edit_message_text.call_args.kwargs["text"]
    assert "Покемон отпущен" in released_text
    assert "🪙 <b>100</b>" in released_text


@pytest.mark.asyncio
async def test_collection_extra_actions_prompt_renders_lock_and_cover_buttons() -> None:
    session = MenuSession(
        session_id="collection-extra-session",
        chat_id=12345,
        message_id=230,
        user_id=12345,
        message_thread_id=None,
        data={
            "release_user_pokemon_id": 250,
            "release_pokemon_name": "Pikachu",
            "release_rarity": "Rare",
        },
    )

    user = Mock(spec=User)
    user.id = 12345
    user.username = "ash"

    query = AsyncMock(spec=CallbackQuery)
    query.data = f"menu:pkm:{session.session_id}"
    query.message = Mock(spec=Message)
    query.message.photo = []
    query.edit_message_text = AsyncMock()
    query.answer = AsyncMock()

    update = Mock(spec=Update)
    update.callback_query = query
    update.effective_user = user

    db = AsyncMock()
    db.get_user_pokemon_entry = AsyncMock(return_value=_entry(25, "Pikachu", "Rare", "electric", 1))
    context = Mock(spec=ContextTypes.DEFAULT_TYPE)
    context.application = Mock()
    context.application.bot_data = {"db": db}

    await collection_handler(update, context, session)

    assert query.edit_message_text.called
    text = query.edit_message_text.call_args.kwargs["text"]
    assert "Дополнительно" in text
    reply_markup = query.edit_message_text.call_args.kwargs["reply_markup"]
    labels = [button.text for row in reply_markup.inline_keyboard for button in row]
    assert "🔒 Залочить" in labels
    assert "🖼 На обложку" in labels
    assert "🛡 Добавить в команду" in labels


@pytest.mark.asyncio
async def test_collection_extra_actions_lock_toggle_updates_menu() -> None:
    session = MenuSession(
        session_id="collection-lock-session",
        chat_id=12345,
        message_id=231,
        user_id=12345,
        message_thread_id=None,
        data={
            "release_user_pokemon_id": 250,
            "release_pokemon_name": "Pikachu",
            "release_rarity": "Rare",
        },
    )

    user = Mock(spec=User)
    user.id = 12345
    user.username = "ash"

    query = AsyncMock(spec=CallbackQuery)
    query.data = f"menu:pkl:{session.session_id}"
    query.message = Mock(spec=Message)
    query.message.photo = []
    query.edit_message_text = AsyncMock()
    query.answer = AsyncMock()

    update = Mock(spec=Update)
    update.callback_query = query
    update.effective_user = user

    db = AsyncMock()
    db.toggle_user_pokemon_lock = AsyncMock(
        return_value=SimpleNamespace(
            user_pokemon_id=250,
            pokemon_id=25,
            name="Pikachu",
            rarity="Rare",
            is_locked=True,
        )
    )
    locked_entry = _entry(25, "Pikachu", "Rare", "electric", 1)
    locked_entry.is_locked = True
    db.get_user_pokemon_entry = AsyncMock(return_value=locked_entry)

    context = Mock(spec=ContextTypes.DEFAULT_TYPE)
    context.application = Mock()
    context.application.bot_data = {"db": db}

    await collection_handler(update, context, session)

    assert db.toggle_user_pokemon_lock.called
    assert query.edit_message_text.called
    text = query.edit_message_text.call_args.kwargs["text"]
    assert "Покемон залочен" in text


@pytest.mark.asyncio
async def test_collection_extra_actions_set_cover_updates_profile_cover() -> None:
    session = MenuSession(
        session_id="collection-cover-session",
        chat_id=12345,
        message_id=232,
        user_id=12345,
        message_thread_id=None,
        data={
            "release_user_pokemon_id": 250,
            "release_pokemon_name": "Pikachu",
            "release_rarity": "Rare",
        },
    )

    user = Mock(spec=User)
    user.id = 12345
    user.username = "ash"

    query = AsyncMock(spec=CallbackQuery)
    query.data = f"menu:pkv:{session.session_id}"
    query.message = Mock(spec=Message)
    query.message.photo = []
    query.edit_message_text = AsyncMock()
    query.answer = AsyncMock()

    update = Mock(spec=Update)
    update.callback_query = query
    update.effective_user = user

    db = AsyncMock()
    cover_entry = _entry(25, "Pikachu", "Rare", "electric", 1)
    cover_entry.image_credit_id = 55
    db.get_user_pokemon_entry = AsyncMock(return_value=cover_entry)
    db.update_profile_cover = AsyncMock(return_value=55)

    context = Mock(spec=ContextTypes.DEFAULT_TYPE)
    context.application = Mock()
    context.application.bot_data = {"db": db}

    await collection_handler(update, context, session)

    assert db.update_profile_cover.called
    assert query.edit_message_text.called
    text = query.edit_message_text.call_args.kwargs["text"]
    assert "Обложка обновлена" in text


@pytest.mark.asyncio
async def test_collection_extra_actions_shows_source_button_when_available() -> None:
    session = MenuSession(
        session_id="collection-extra-session",
        chat_id=12345,
        message_id=240,
        user_id=12345,
        message_thread_id=None,
        data={
            "release_user_pokemon_id": 250,
            "release_pokemon_name": "Pikachu",
            "release_rarity": "Rare",
        },
    )

    user = Mock(spec=User)
    user.id = 12345
    user.username = "ash"

    query = AsyncMock(spec=CallbackQuery)
    query.data = f"menu:pkm:{session.session_id}"
    query.message = Mock(spec=Message)
    query.message.photo = []
    query.edit_message_text = AsyncMock()
    query.answer = AsyncMock()

    update = Mock(spec=Update)
    update.callback_query = query
    update.effective_user = user

    db = AsyncMock()
    entry = _entry(25, "Pikachu", "Rare", "electric", 1)
    entry.image_credit_id = 55
    db.get_user_pokemon_entry = AsyncMock(return_value=entry)
    db.get_pokemon_image_selection = AsyncMock(
        return_value=SimpleNamespace(
            image_credit_id=77,
            source_url="https://example.com/selected-source",
            position=2,
            total=3,
        )
    )

    context = Mock(spec=ContextTypes.DEFAULT_TYPE)
    context.application = Mock()
    context.application.bot_data = {"db": db}

    await collection_handler(update, context, session)

    keyboard = query.edit_message_text.call_args.kwargs["reply_markup"]
    button_texts = [button.text for row in keyboard.inline_keyboard for button in row]
    assert "🔗 Источник" in button_texts
    source_button = next(button for row in keyboard.inline_keyboard for button in row if button.text == "🔗 Источник")
    assert source_button.url == "https://example.com/selected-source"


@pytest.mark.asyncio
async def test_collection_extra_actions_add_to_team_shows_quick_command() -> None:
    session = MenuSession(
        session_id="collection-team-hint",
        chat_id=12345,
        message_id=241,
        user_id=12345,
        message_thread_id=None,
        data={
            "release_user_pokemon_id": 250,
            "release_pokemon_name": "Pikachu",
            "release_rarity": "Rare",
        },
    )

    user = Mock(spec=User)
    user.id = 12345
    user.username = "ash"

    query = AsyncMock(spec=CallbackQuery)
    query.data = f"menu:pkt:{session.session_id}"
    query.message = Mock(spec=Message)
    query.message.photo = []
    query.edit_message_text = AsyncMock()
    query.answer = AsyncMock()

    update = Mock(spec=Update)
    update.callback_query = query
    update.effective_user = user

    db = AsyncMock()
    entry = _entry(25, "Pikachu", "Rare", "electric", 1)
    db.get_user_pokemon_entry = AsyncMock(return_value=entry)

    context = Mock(spec=ContextTypes.DEFAULT_TYPE)
    context.application = Mock()
    context.application.bot_data = {"db": db}

    await collection_handler(update, context, session)

    text = query.edit_message_text.call_args.kwargs["text"]
    assert "/addteam слот 250" in text
    assert "число от <b>1</b> до <b>5</b>" in text
