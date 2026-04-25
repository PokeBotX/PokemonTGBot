"""Integration tests for admin-bot foundation flows."""

from unittest.mock import AsyncMock, Mock, patch

import pytest
from telegram import CallbackQuery, Chat, Message, PhotoSize, Update, User
from telegram.ext import ContextTypes

from bot.admin.config import AdminBotSettings
from bot.admin.handlers import (
    handle_admin_callback_query,
    handle_admin_media_input,
    handle_admin_text_input,
    menu_admin_command,
    register_admin_routes,
    register_pending_executor,
    set_admin_settings_for_tests,
    show_pending_action_preview,
    unregister_pending_executor,
)
from bot.admin.pending import AdminPendingAction
from bot.admin.session import admin_session_store
from bot.admin.ui import SECTION_CONFIRM, SECTION_CREATE_POKEMON, SECTION_GRANT_POKEDOLLAR, SECTION_GRANT_POKEMON, SECTION_GRANTS, SECTION_IMAGE_EDIT_SOURCE, SECTION_IMAGE_EDIT_VARIANT, SECTION_IMAGE_UPLOAD_VARIANT, SECTION_IMAGES, SECTION_POKEMON
from bot.db.database import PokemonSearchEntry, UserLookupResult


@pytest.fixture(autouse=True)
def reset_admin_state():
    admin_session_store.reset()
    set_admin_settings_for_tests(None)
    yield
    admin_session_store.reset()
    set_admin_settings_for_tests(None)
    unregister_pending_executor("demo.grant")


def _allowed_settings() -> AdminBotSettings:
    return AdminBotSettings(
        token="token",
        allowed_ids=frozenset({12345}),
    )


def _private_update(*, user_id: int = 12345, username: str = "ash", text: str = "/menu") -> tuple[Mock, Mock, Mock, Mock]:
    user = Mock(spec=User)
    user.id = user_id
    user.username = username

    chat = Mock(spec=Chat)
    chat.id = user_id
    chat.type = "private"

    message = Mock(spec=Message)
    message.message_id = 100
    message.chat = chat
    message.chat_id = user_id
    message.from_user = user
    message.message_thread_id = None
    message.text = text

    update = Mock(spec=Update)
    update.effective_user = user
    update.effective_chat = chat
    update.effective_message = message
    update.callback_query = None
    return update, user, chat, message


def _extract_edited_text(call_args) -> str | None:
    if "text" in call_args.kwargs:
        return call_args.kwargs["text"]
    if call_args.args:
        return call_args.args[0]
    return None


@pytest.mark.asyncio
async def test_admin_menu_allows_superadmin_in_private_chat() -> None:
    set_admin_settings_for_tests(_allowed_settings())
    register_admin_routes()

    update, _, chat, _ = _private_update()
    sent_message = Mock(spec=Message)
    sent_message.message_id = 101
    sent_message.chat_id = chat.id
    sent_message.message_thread_id = None
    sent_message.edit_reply_markup = AsyncMock()
    chat.send_message = AsyncMock(return_value=sent_message)

    context = Mock(spec=ContextTypes.DEFAULT_TYPE)

    await menu_admin_command(update, context)

    assert chat.send_message.called
    assert sent_message.edit_reply_markup.called
    assert len(admin_session_store._sessions) == 1


@pytest.mark.asyncio
async def test_admin_section_callback_opens_placeholder_screen() -> None:
    set_admin_settings_for_tests(_allowed_settings())
    register_admin_routes()

    update, user, chat, _ = _private_update()
    sent_message = Mock(spec=Message)
    sent_message.message_id = 101
    sent_message.chat_id = chat.id
    sent_message.message_thread_id = None
    sent_message.edit_reply_markup = AsyncMock()
    sent_message.edit_text = AsyncMock()
    chat.send_message = AsyncMock(return_value=sent_message)

    context = Mock(spec=ContextTypes.DEFAULT_TYPE)
    await menu_admin_command(update, context)
    session_id = next(iter(admin_session_store._sessions.keys()))

    callback = Mock(spec=CallbackQuery)
    callback.id = "cb1"
    callback.data = f"menu:{SECTION_GRANTS}:{session_id}"
    callback.message = sent_message
    callback.answer = AsyncMock()

    callback_update = Mock(spec=Update)
    callback_update.effective_user = user
    callback_update.effective_chat = chat
    callback_update.callback_query = callback
    callback_update.effective_message = sent_message

    await handle_admin_callback_query(callback_update, context)

    assert sent_message.edit_text.called
    edited_text = _extract_edited_text(sent_message.edit_text.call_args)
    assert "безопасно выдать пользователю" in edited_text


@pytest.mark.asyncio
async def test_admin_pending_confirmation_executes_registered_executor_and_audits() -> None:
    set_admin_settings_for_tests(_allowed_settings())
    register_admin_routes()

    update, user, chat, _ = _private_update()
    sent_message = Mock(spec=Message)
    sent_message.message_id = 101
    sent_message.chat_id = chat.id
    sent_message.message_thread_id = None
    sent_message.edit_reply_markup = AsyncMock()
    sent_message.edit_text = AsyncMock()
    chat.send_message = AsyncMock(return_value=sent_message)

    db = AsyncMock()
    application = Mock()
    application.bot_data = {"db": db}
    context = Mock(spec=ContextTypes.DEFAULT_TYPE)
    context.application = application

    executor = AsyncMock(return_value={"granted": True})
    register_pending_executor("demo.grant", executor)

    pending_action = AdminPendingAction(
        action_type="demo.grant",
        title="Выдать валюту",
        description="Будет начислено 500 PokéDollar пользователю @misty.",
        input_payload={"currency": "pokedollar", "amount": 500},
        target_username="misty",
        target_telegram_id=54321,
    )
    session_id = await show_pending_action_preview(update, context, pending_action=pending_action)
    assert session_id is not None
    assert db.record_admin_action_audit.await_count == 1

    callback = Mock(spec=CallbackQuery)
    callback.id = "cb2"
    callback.data = f"menu:{SECTION_CONFIRM}:{session_id}"
    callback.message = sent_message
    callback.answer = AsyncMock()

    callback_update = Mock(spec=Update)
    callback_update.effective_user = user
    callback_update.effective_chat = chat
    callback_update.callback_query = callback
    callback_update.effective_message = sent_message

    await handle_admin_callback_query(callback_update, context)

    executor.assert_awaited_once()
    assert db.record_admin_action_audit.await_count == 2
    assert sent_message.edit_text.called
    edited_text = _extract_edited_text(sent_message.edit_text.call_args)
    assert "Действие выполнено" in edited_text


@pytest.mark.asyncio
async def test_admin_currency_grant_flow_from_buttons_to_confirm() -> None:
    set_admin_settings_for_tests(_allowed_settings())
    register_admin_routes()

    update, user, chat, _ = _private_update()
    sent_message = Mock(spec=Message)
    sent_message.message_id = 101
    sent_message.chat_id = chat.id
    sent_message.message_thread_id = None
    sent_message.edit_reply_markup = AsyncMock()
    sent_message.edit_text = AsyncMock()
    chat.send_message = AsyncMock(return_value=sent_message)

    db = AsyncMock()
    db.get_user_lookup_by_username = AsyncMock(
        return_value=UserLookupResult(user_id=77, telegram_id=54321, username="misty")
    )
    db.admin_grant_currency = AsyncMock(return_value=1750)
    application = Mock()
    application.bot_data = {"db": db}
    context = Mock(spec=ContextTypes.DEFAULT_TYPE)
    context.application = application

    await menu_admin_command(update, context)
    root_session_id = next(iter(admin_session_store._sessions.keys()))

    start_callback = Mock(spec=CallbackQuery)
    start_callback.id = "cb-grant-start"
    start_callback.data = f"menu:{SECTION_GRANT_POKEDOLLAR}:{root_session_id}"
    start_callback.message = sent_message
    start_callback.answer = AsyncMock()

    start_update = Mock(spec=Update)
    start_update.effective_user = user
    start_update.effective_chat = chat
    start_update.callback_query = start_callback
    start_update.effective_message = sent_message

    await handle_admin_callback_query(start_update, context)

    pending = admin_session_store.get_pending_input(chat_id=chat.id, user_id=user.id)
    assert pending is not None
    assert pending.action == "grant_pokedollar_username"

    username_message = Mock(spec=Message)
    username_message.chat = chat
    username_message.chat_id = chat.id
    username_message.from_user = user
    username_message.text = "@misty"
    username_message.message_thread_id = None

    username_update = Mock(spec=Update)
    username_update.effective_user = user
    username_update.effective_chat = chat
    username_update.effective_message = username_message

    await handle_admin_text_input(username_update, context)

    pending = admin_session_store.get_pending_input(chat_id=chat.id, user_id=user.id)
    assert pending is not None
    assert pending.action == "grant_pokedollar_amount"

    amount_message = Mock(spec=Message)
    amount_message.chat = chat
    amount_message.chat_id = chat.id
    amount_message.from_user = user
    amount_message.text = "500"
    amount_message.message_thread_id = None

    amount_update = Mock(spec=Update)
    amount_update.effective_user = user
    amount_update.effective_chat = chat
    amount_update.effective_message = amount_message

    await handle_admin_text_input(amount_update, context)

    assert admin_session_store.get_pending_input(chat_id=chat.id, user_id=user.id) is None
    assert db.record_admin_action_audit.await_count == 1
    confirm_session_id = list(admin_session_store._sessions.keys())[-1]

    confirm_callback = Mock(spec=CallbackQuery)
    confirm_callback.id = "cb-grant-confirm"
    confirm_callback.data = f"menu:{SECTION_CONFIRM}:{confirm_session_id}"
    confirm_callback.message = sent_message
    confirm_callback.answer = AsyncMock()

    confirm_update = Mock(spec=Update)
    confirm_update.effective_user = user
    confirm_update.effective_chat = chat
    confirm_update.callback_query = confirm_callback
    confirm_update.effective_message = sent_message

    await handle_admin_callback_query(confirm_update, context)

    db.admin_grant_currency.assert_awaited_once_with(
        target_user_id=77,
        currency_code="pokedollar",
        amount=500,
    )
    assert db.record_admin_action_audit.await_count == 2
    edited_text = _extract_edited_text(sent_message.edit_text.call_args)
    assert "Новый баланс" in edited_text


@pytest.mark.asyncio
async def test_admin_pokemon_grant_flow_from_buttons_to_confirm() -> None:
    set_admin_settings_for_tests(_allowed_settings())
    register_admin_routes()

    update, user, chat, _ = _private_update()
    sent_message = Mock(spec=Message)
    sent_message.message_id = 101
    sent_message.chat_id = chat.id
    sent_message.message_thread_id = None
    sent_message.edit_reply_markup = AsyncMock()
    sent_message.edit_text = AsyncMock()
    chat.send_message = AsyncMock(return_value=sent_message)

    db = AsyncMock()
    db.get_user_lookup_by_username = AsyncMock(
        return_value=UserLookupResult(user_id=77, telegram_id=54321, username="misty")
    )
    db.get_pokemon_catalog_entry_by_id = AsyncMock(
        return_value=PokemonSearchEntry(
            pokemon_id=25,
            name="Pikachu",
            rarity="Rare",
            pokemon_type="Electric",
            base_hp=35,
            base_attack=55,
            base_defense=40,
            base_stamina=90,
            image_credit_id=None,
        )
    )
    db.admin_grant_pokemon = AsyncMock(return_value=912)
    application = Mock()
    application.bot_data = {"db": db}
    context = Mock(spec=ContextTypes.DEFAULT_TYPE)
    context.application = application

    await menu_admin_command(update, context)
    root_session_id = next(iter(admin_session_store._sessions.keys()))

    start_callback = Mock(spec=CallbackQuery)
    start_callback.id = "cb-pokemon-start"
    start_callback.data = f"menu:{SECTION_GRANT_POKEMON}:{root_session_id}"
    start_callback.message = sent_message
    start_callback.answer = AsyncMock()

    start_update = Mock(spec=Update)
    start_update.effective_user = user
    start_update.effective_chat = chat
    start_update.callback_query = start_callback
    start_update.effective_message = sent_message

    await handle_admin_callback_query(start_update, context)

    username_message = Mock(spec=Message)
    username_message.chat = chat
    username_message.chat_id = chat.id
    username_message.from_user = user
    username_message.text = "@misty"
    username_message.message_thread_id = None

    username_update = Mock(spec=Update)
    username_update.effective_user = user
    username_update.effective_chat = chat
    username_update.effective_message = username_message

    await handle_admin_text_input(username_update, context)

    pending = admin_session_store.get_pending_input(chat_id=chat.id, user_id=user.id)
    assert pending is not None
    assert pending.action == "grant_pokemon_id"

    pokemon_message = Mock(spec=Message)
    pokemon_message.chat = chat
    pokemon_message.chat_id = chat.id
    pokemon_message.from_user = user
    pokemon_message.text = "25"
    pokemon_message.message_thread_id = None

    pokemon_update = Mock(spec=Update)
    pokemon_update.effective_user = user
    pokemon_update.effective_chat = chat
    pokemon_update.effective_message = pokemon_message

    await handle_admin_text_input(pokemon_update, context)

    confirm_session_id = list(admin_session_store._sessions.keys())[-1]
    confirm_callback = Mock(spec=CallbackQuery)
    confirm_callback.id = "cb-pokemon-confirm"
    confirm_callback.data = f"menu:{SECTION_CONFIRM}:{confirm_session_id}"
    confirm_callback.message = sent_message
    confirm_callback.answer = AsyncMock()

    confirm_update = Mock(spec=Update)
    confirm_update.effective_user = user
    confirm_update.effective_chat = chat
    confirm_update.callback_query = confirm_callback
    confirm_update.effective_message = sent_message

    await handle_admin_callback_query(confirm_update, context)

    db.admin_grant_pokemon.assert_awaited_once_with(target_user_id=77, pokemon_id=25)
    edited_text = _extract_edited_text(sent_message.edit_text.call_args)
    assert "ID экземпляра" in edited_text


@pytest.mark.asyncio
async def test_admin_create_pokemon_flow_from_buttons_to_confirm() -> None:
    set_admin_settings_for_tests(_allowed_settings())
    register_admin_routes()

    update, user, chat, _ = _private_update()
    sent_message = Mock(spec=Message)
    sent_message.message_id = 101
    sent_message.chat_id = chat.id
    sent_message.message_thread_id = None
    sent_message.edit_reply_markup = AsyncMock()
    sent_message.edit_text = AsyncMock()
    chat.send_message = AsyncMock(return_value=sent_message)

    db = AsyncMock()
    db.admin_create_pokemon_species = AsyncMock(return_value=999)
    application = Mock()
    application.bot_data = {"db": db}
    context = Mock(spec=ContextTypes.DEFAULT_TYPE)
    context.application = application

    await menu_admin_command(update, context)
    root_session_id = next(iter(admin_session_store._sessions.keys()))

    catalog_callback = Mock(spec=CallbackQuery)
    catalog_callback.id = "cb-catalog"
    catalog_callback.data = f"menu:{SECTION_POKEMON}:{root_session_id}"
    catalog_callback.message = sent_message
    catalog_callback.answer = AsyncMock()

    catalog_update = Mock(spec=Update)
    catalog_update.effective_user = user
    catalog_update.effective_chat = chat
    catalog_update.callback_query = catalog_callback
    catalog_update.effective_message = sent_message

    await handle_admin_callback_query(catalog_update, context)

    catalog_session_id = list(admin_session_store._sessions.keys())[-1]
    create_callback = Mock(spec=CallbackQuery)
    create_callback.id = "cb-create-pokemon"
    create_callback.data = f"menu:{SECTION_CREATE_POKEMON}:{catalog_session_id}"
    create_callback.message = sent_message
    create_callback.answer = AsyncMock()

    create_update = Mock(spec=Update)
    create_update.effective_user = user
    create_update.effective_chat = chat
    create_update.callback_query = create_callback
    create_update.effective_message = sent_message

    await handle_admin_callback_query(create_update, context)

    for value in ["999", "Testmon", "-", "Epic", "80", "95", "70", "88"]:
        field_message = Mock(spec=Message)
        field_message.chat = chat
        field_message.chat_id = chat.id
        field_message.from_user = user
        field_message.text = value
        field_message.message_thread_id = None

        field_update = Mock(spec=Update)
        field_update.effective_user = user
        field_update.effective_chat = chat
        field_update.effective_message = field_message

        await handle_admin_text_input(field_update, context)

    confirm_session_id = list(admin_session_store._sessions.keys())[-1]
    confirm_callback = Mock(spec=CallbackQuery)
    confirm_callback.id = "cb-confirm-create-pokemon"
    confirm_callback.data = f"menu:{SECTION_CONFIRM}:{confirm_session_id}"
    confirm_callback.message = sent_message
    confirm_callback.answer = AsyncMock()

    confirm_update = Mock(spec=Update)
    confirm_update.effective_user = user
    confirm_update.effective_chat = chat
    confirm_update.callback_query = confirm_callback
    confirm_update.effective_message = sent_message

    await handle_admin_callback_query(confirm_update, context)

    db.admin_create_pokemon_species.assert_awaited_once_with(
        pokemon_id=999,
        name="Testmon",
        pokemon_type=None,
        rarity="Epic",
        base_hp=80,
        base_attack=95,
        base_defense=70,
        base_stamina=88,
    )
    edited_text = _extract_edited_text(sent_message.edit_text.call_args)
    assert "Создан покемон" in edited_text


@pytest.mark.asyncio
async def test_admin_image_upload_flow_from_media_to_confirm() -> None:
    set_admin_settings_for_tests(_allowed_settings())
    register_admin_routes()

    update, user, chat, _ = _private_update()
    sent_message = Mock(spec=Message)
    sent_message.message_id = 101
    sent_message.chat_id = chat.id
    sent_message.message_thread_id = None
    sent_message.edit_reply_markup = AsyncMock()
    sent_message.edit_text = AsyncMock()
    chat.send_message = AsyncMock(return_value=sent_message)

    db = AsyncMock()
    db.get_pokemon_catalog_entry_by_id = AsyncMock(
        return_value=PokemonSearchEntry(
            pokemon_id=91,
            name="Cloyster",
            rarity="Rare",
            pokemon_type="Water",
            base_hp=50,
            base_attack=95,
            base_defense=180,
            base_stamina=70,
            image_credit_id=None,
        )
    )
    db.admin_attach_image_variant = AsyncMock(return_value=5555)
    application = Mock()
    application.bot_data = {"db": db}
    bot = Mock()
    telegram_file = Mock()
    telegram_file.download_as_bytearray = AsyncMock(return_value=bytearray(b"image-bytes"))
    bot.get_file = AsyncMock(return_value=telegram_file)
    context = Mock(spec=ContextTypes.DEFAULT_TYPE)
    context.application = application
    context.bot = bot

    await menu_admin_command(update, context)
    root_session_id = next(iter(admin_session_store._sessions.keys()))

    images_callback = Mock(spec=CallbackQuery)
    images_callback.id = "cb-images"
    images_callback.data = f"menu:{SECTION_IMAGES}:{root_session_id}"
    images_callback.message = sent_message
    images_callback.answer = AsyncMock()

    images_update = Mock(spec=Update)
    images_update.effective_user = user
    images_update.effective_chat = chat
    images_update.callback_query = images_callback
    images_update.effective_message = sent_message

    await handle_admin_callback_query(images_update, context)

    images_session_id = list(admin_session_store._sessions.keys())[-1]
    upload_callback = Mock(spec=CallbackQuery)
    upload_callback.id = "cb-upload"
    upload_callback.data = f"menu:{SECTION_IMAGE_UPLOAD_VARIANT}:{images_session_id}"
    upload_callback.message = sent_message
    upload_callback.answer = AsyncMock()

    upload_update = Mock(spec=Update)
    upload_update.effective_user = user
    upload_update.effective_chat = chat
    upload_update.callback_query = upload_callback
    upload_update.effective_message = sent_message

    await handle_admin_callback_query(upload_update, context)

    media_message = Mock(spec=Message)
    media_message.chat = chat
    media_message.chat_id = chat.id
    media_message.from_user = user
    media_message.message_thread_id = None
    media_message.photo = [
        PhotoSize(file_id="file-1", file_unique_id="uniq-1", width=100, height=100, file_size=1234)
    ]
    media_message.document = None

    media_update = Mock(spec=Update)
    media_update.effective_user = user
    media_update.effective_chat = chat
    media_update.effective_message = media_message

    await handle_admin_media_input(media_update, context)

    for value in ["91", "https://example.com/art/cloyster", "2", "да"]:
        text_message = Mock(spec=Message)
        text_message.chat = chat
        text_message.chat_id = chat.id
        text_message.from_user = user
        text_message.text = value
        text_message.message_thread_id = None

        text_update = Mock(spec=Update)
        text_update.effective_user = user
        text_update.effective_chat = chat
        text_update.effective_message = text_message

        await handle_admin_text_input(text_update, context)

    confirm_session_id = list(admin_session_store._sessions.keys())[-1]
    confirm_callback = Mock(spec=CallbackQuery)
    confirm_callback.id = "cb-image-confirm"
    confirm_callback.data = f"menu:{SECTION_CONFIRM}:{confirm_session_id}"
    confirm_callback.message = sent_message
    confirm_callback.answer = AsyncMock()

    confirm_update = Mock(spec=Update)
    confirm_update.effective_user = user
    confirm_update.effective_chat = chat
    confirm_update.callback_query = confirm_callback
    confirm_update.effective_message = sent_message

    with patch("bot.admin.handlers.upload_admin_image_bytes", new=AsyncMock(return_value=("pokemon-assets", "pokemon/91/cloyster-uniq-1.jpg", "etag-1"))):
        await handle_admin_callback_query(confirm_update, context)

    bot.get_file.assert_awaited_once_with("file-1")
    db.admin_attach_image_variant.assert_awaited_once_with(
        pokemon_id=91,
        storage_bucket="pokemon-assets",
        object_key="pokemon/91/cloyster-uniq-1.jpg",
        content_type="image/jpeg",
        etag="etag-1",
        source="https://example.com/art/cloyster",
        display_order=2,
        is_default=True,
    )
    edited_text = _extract_edited_text(sent_message.edit_text.call_args)
    assert "Добавлен variant" in edited_text


@pytest.mark.asyncio
async def test_admin_image_source_edit_flow() -> None:
    set_admin_settings_for_tests(_allowed_settings())
    register_admin_routes()

    update, user, chat, _ = _private_update()
    sent_message = Mock(spec=Message)
    sent_message.message_id = 101
    sent_message.chat_id = chat.id
    sent_message.message_thread_id = None
    sent_message.edit_reply_markup = AsyncMock()
    sent_message.edit_text = AsyncMock()
    chat.send_message = AsyncMock(return_value=sent_message)

    db = AsyncMock()
    db.admin_update_image_source = AsyncMock(return_value=777)
    application = Mock()
    application.bot_data = {"db": db}
    context = Mock(spec=ContextTypes.DEFAULT_TYPE)
    context.application = application

    await menu_admin_command(update, context)
    root_session_id = next(iter(admin_session_store._sessions.keys()))

    images_callback = Mock(spec=CallbackQuery)
    images_callback.id = "cb-images-source"
    images_callback.data = f"menu:{SECTION_IMAGES}:{root_session_id}"
    images_callback.message = sent_message
    images_callback.answer = AsyncMock()

    images_update = Mock(spec=Update)
    images_update.effective_user = user
    images_update.effective_chat = chat
    images_update.callback_query = images_callback
    images_update.effective_message = sent_message

    await handle_admin_callback_query(images_update, context)

    images_session_id = list(admin_session_store._sessions.keys())[-1]
    edit_callback = Mock(spec=CallbackQuery)
    edit_callback.id = "cb-edit-source"
    edit_callback.data = f"menu:{SECTION_IMAGE_EDIT_SOURCE}:{images_session_id}"
    edit_callback.message = sent_message
    edit_callback.answer = AsyncMock()

    edit_update = Mock(spec=Update)
    edit_update.effective_user = user
    edit_update.effective_chat = chat
    edit_update.callback_query = edit_callback
    edit_update.effective_message = sent_message

    await handle_admin_callback_query(edit_update, context)

    for value in ["777", "https://example.com/new-source"]:
        text_message = Mock(spec=Message)
        text_message.chat = chat
        text_message.chat_id = chat.id
        text_message.from_user = user
        text_message.text = value
        text_message.message_thread_id = None

        text_update = Mock(spec=Update)
        text_update.effective_user = user
        text_update.effective_chat = chat
        text_update.effective_message = text_message

        await handle_admin_text_input(text_update, context)

    confirm_session_id = list(admin_session_store._sessions.keys())[-1]
    confirm_callback = Mock(spec=CallbackQuery)
    confirm_callback.id = "cb-source-confirm"
    confirm_callback.data = f"menu:{SECTION_CONFIRM}:{confirm_session_id}"
    confirm_callback.message = sent_message
    confirm_callback.answer = AsyncMock()

    confirm_update = Mock(spec=Update)
    confirm_update.effective_user = user
    confirm_update.effective_chat = chat
    confirm_update.callback_query = confirm_callback
    confirm_update.effective_message = sent_message

    await handle_admin_callback_query(confirm_update, context)

    db.admin_update_image_source.assert_awaited_once_with(
        image_credit_id=777,
        source="https://example.com/new-source",
    )
    edited_text = _extract_edited_text(sent_message.edit_text.call_args)
    assert "Обновлён source" in edited_text


@pytest.mark.asyncio
async def test_admin_image_variant_metadata_edit_flow() -> None:
    set_admin_settings_for_tests(_allowed_settings())
    register_admin_routes()

    update, user, chat, _ = _private_update()
    sent_message = Mock(spec=Message)
    sent_message.message_id = 101
    sent_message.chat_id = chat.id
    sent_message.message_thread_id = None
    sent_message.edit_reply_markup = AsyncMock()
    sent_message.edit_text = AsyncMock()
    chat.send_message = AsyncMock(return_value=sent_message)

    db = AsyncMock()
    db.get_pokemon_catalog_entry_by_id = AsyncMock(
        return_value=PokemonSearchEntry(
            pokemon_id=91,
            name="Cloyster",
            rarity="Rare",
            pokemon_type="Water",
            base_hp=50,
            base_attack=95,
            base_defense=180,
            base_stamina=70,
            image_credit_id=None,
        )
    )
    db.admin_update_image_variant_metadata = AsyncMock(return_value=777)
    application = Mock()
    application.bot_data = {"db": db}
    context = Mock(spec=ContextTypes.DEFAULT_TYPE)
    context.application = application

    await menu_admin_command(update, context)
    root_session_id = next(iter(admin_session_store._sessions.keys()))

    images_callback = Mock(spec=CallbackQuery)
    images_callback.id = "cb-images-variant"
    images_callback.data = f"menu:{SECTION_IMAGES}:{root_session_id}"
    images_callback.message = sent_message
    images_callback.answer = AsyncMock()

    images_update = Mock(spec=Update)
    images_update.effective_user = user
    images_update.effective_chat = chat
    images_update.callback_query = images_callback
    images_update.effective_message = sent_message

    await handle_admin_callback_query(images_update, context)

    images_session_id = list(admin_session_store._sessions.keys())[-1]
    edit_callback = Mock(spec=CallbackQuery)
    edit_callback.id = "cb-edit-variant"
    edit_callback.data = f"menu:{SECTION_IMAGE_EDIT_VARIANT}:{images_session_id}"
    edit_callback.message = sent_message
    edit_callback.answer = AsyncMock()

    edit_update = Mock(spec=Update)
    edit_update.effective_user = user
    edit_update.effective_chat = chat
    edit_update.callback_query = edit_callback
    edit_update.effective_message = sent_message

    await handle_admin_callback_query(edit_update, context)

    for value in ["91", "777", "3", "нет"]:
        text_message = Mock(spec=Message)
        text_message.chat = chat
        text_message.chat_id = chat.id
        text_message.from_user = user
        text_message.text = value
        text_message.message_thread_id = None

        text_update = Mock(spec=Update)
        text_update.effective_user = user
        text_update.effective_chat = chat
        text_update.effective_message = text_message

        await handle_admin_text_input(text_update, context)

    confirm_session_id = list(admin_session_store._sessions.keys())[-1]
    confirm_callback = Mock(spec=CallbackQuery)
    confirm_callback.id = "cb-variant-confirm"
    confirm_callback.data = f"menu:{SECTION_CONFIRM}:{confirm_session_id}"
    confirm_callback.message = sent_message
    confirm_callback.answer = AsyncMock()

    confirm_update = Mock(spec=Update)
    confirm_update.effective_user = user
    confirm_update.effective_chat = chat
    confirm_update.callback_query = confirm_callback
    confirm_update.effective_message = sent_message

    await handle_admin_callback_query(confirm_update, context)

    db.admin_update_image_variant_metadata.assert_awaited_once_with(
        pokemon_id=91,
        image_credit_id=777,
        display_order=3,
        is_default=False,
    )
    edited_text = _extract_edited_text(sent_message.edit_text.call_args)
    assert "Обновлён вариант" in edited_text
