"""Unit tests for admin-bot action and confirmation behavior."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, Mock

import pytest
from telegram import CallbackQuery, Chat, Message, Update, User
from telegram.ext import ContextTypes

from bot.admin.config import AdminBotSettings
from bot.admin.handlers import (
    ADMIN_ACTION_CREATE_POKEMON,
    ADMIN_PENDING_CREATE_POKEMON_FIELD,
    ADMIN_PENDING_GRANT_POKEMON_ID,
    ADMIN_PENDING_GRANT_POKEMON_USERNAME,
    _confirm_pending_action,
    _execute_create_pokemon,
    _normalize_create_pokemon_field,
    _execute_update_pokemon_species,
    _cancel_pending_action,
    handle_admin_text_input,
    register_admin_routes,
    set_admin_settings_for_tests,
)
from bot.admin.pending import ADMIN_PENDING_ACTION_TTL_SECONDS, AdminPendingAction
from bot.admin.session import admin_session_store
from bot.admin.ui import build_admin_audit_export_text, get_admin_audit_text
from bot.db.database import AdminAuditRecord, _coerce_json_object
from bot.db.database import ShopError


@pytest.fixture(autouse=True)
def reset_admin_state():
    admin_session_store.reset()
    set_admin_settings_for_tests(None)
    yield
    admin_session_store.reset()
    set_admin_settings_for_tests(None)


def _allowed_settings() -> AdminBotSettings:
    return AdminBotSettings(token="token", allowed_ids=frozenset({12345}))


def _private_update(*, text: str = "/menu", user_id: int = 12345, username: str = "ash") -> tuple[Mock, Mock, Mock, Mock]:
    user = Mock(spec=User)
    user.id = user_id
    user.username = username

    chat = Mock(spec=Chat)
    chat.id = user_id
    chat.type = "private"
    chat.send_message = AsyncMock()

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


def test_pending_action_round_trip_and_expiry() -> None:
    action = AdminPendingAction(
        action_type="grant.currency",
        title="Выдать PokéCoin",
        description="Пользователь получит 10 PokéCoin.",
        input_payload={"amount": 10},
        target_username="misty",
        target_telegram_id=54321,
        target_user_id=77,
        created_at=datetime.now(UTC) - timedelta(seconds=ADMIN_PENDING_ACTION_TTL_SECONDS + 5),
    )

    restored = AdminPendingAction.from_session_payload(action.to_session_payload())

    assert restored is not None
    assert restored.target_username == "misty"
    assert restored.target_telegram_id == 54321
    assert restored.target_user_id == 77
    assert restored.input_payload == {"amount": 10}
    assert restored.is_expired() is True


def test_normalize_create_pokemon_field_rejects_invalid_rarity() -> None:
    with pytest.raises(ShopError, match="Редкость должна быть одной из"):
        _normalize_create_pokemon_field(field_key="rarity", raw_value="Mythic")


@pytest.mark.asyncio
async def test_handle_admin_text_input_reports_unknown_username() -> None:
    set_admin_settings_for_tests(_allowed_settings())
    register_admin_routes()

    update, user, chat, message = _private_update(text="@missing")
    admin_session_store.set_pending_input(
        action=ADMIN_PENDING_GRANT_POKEMON_USERNAME,
        chat_id=chat.id,
        user_id=user.id,
        source_message_id=99,
        data={"flow": "pokemon"},
    )

    db = AsyncMock()
    db.get_user_lookup_by_username = AsyncMock(side_effect=ShopError("Пользователь не найден."))

    application = Mock()
    application.bot_data = {"db": db}
    context = Mock(spec=ContextTypes.DEFAULT_TYPE)
    context.application = application

    await handle_admin_text_input(update, context)

    chat.send_message.assert_awaited()
    assert "Пользователь не найден" in chat.send_message.await_args.kwargs["text"]
    pending = admin_session_store.get_pending_input(chat_id=chat.id, user_id=user.id)
    assert pending is not None
    assert pending.action == ADMIN_PENDING_GRANT_POKEMON_USERNAME
    assert pending.source_message_id == 99
    assert message.text == "@missing"


@pytest.mark.asyncio
async def test_handle_admin_text_input_reports_unknown_pokemon_lookup() -> None:
    set_admin_settings_for_tests(_allowed_settings())
    register_admin_routes()

    update, user, chat, _ = _private_update(text="9999")
    admin_session_store.set_pending_input(
        action=ADMIN_PENDING_GRANT_POKEMON_ID,
        chat_id=chat.id,
        user_id=user.id,
        source_message_id=99,
        data={
            "target_user_id": 77,
            "target_telegram_id": 54321,
            "target_username": "misty",
        },
    )

    db = AsyncMock()
    db.get_pokemon_catalog_entry_by_id = AsyncMock(side_effect=ShopError("Покемон не найден."))

    application = Mock()
    application.bot_data = {"db": db}
    context = Mock(spec=ContextTypes.DEFAULT_TYPE)
    context.application = application

    await handle_admin_text_input(update, context)

    chat.send_message.assert_awaited()
    assert "Покемон не найден" in chat.send_message.await_args.kwargs["text"]
    pending = admin_session_store.get_pending_input(chat_id=chat.id, user_id=user.id)
    assert pending is not None
    assert pending.action == ADMIN_PENDING_GRANT_POKEMON_ID


@pytest.mark.asyncio
async def test_handle_admin_text_input_builds_create_pokemon_confirmation() -> None:
    set_admin_settings_for_tests(_allowed_settings())
    register_admin_routes()

    update, user, chat, _ = _private_update(text="120")
    admin_session_store.set_pending_input(
        action=ADMIN_PENDING_CREATE_POKEMON_FIELD,
        chat_id=chat.id,
        user_id=user.id,
        source_message_id=99,
        data={
            "field_index": 7,
            "draft": {
                "pokemon_id": 120,
                "name": "Staryu",
                "pokemon_type": "Water",
                "rarity": "Rare",
                "base_hp": 30,
                "base_attack": 45,
                "base_defense": 55,
            },
        },
    )

    db = AsyncMock()
    application = Mock()
    application.bot_data = {"db": db}
    context = Mock(spec=ContextTypes.DEFAULT_TYPE)
    context.application = application

    await handle_admin_text_input(update, context)

    pending_sessions = [
        session for session in admin_session_store._sessions.values()
        if session.data.get("screen") == "pending_action"
    ]
    assert len(pending_sessions) == 1
    pending_action = AdminPendingAction.from_session_payload(pending_sessions[0].data.get("pending_action"))
    assert pending_action is not None
    assert pending_action.action_type == ADMIN_ACTION_CREATE_POKEMON
    assert pending_action.input_payload["name"] == "Staryu"
    assert pending_action.input_payload["base_stamina"] == 120


@pytest.mark.asyncio
async def test_execute_create_pokemon_surfaces_duplicate_id_error() -> None:
    pending_action = AdminPendingAction(
        action_type=ADMIN_ACTION_CREATE_POKEMON,
        title="Создать покемона",
        description="Будет создан новый покемон.",
        input_payload={
            "pokemon_id": 25,
            "name": "Pikachu",
            "pokemon_type": "Electric",
            "rarity": "Rare",
            "base_hp": 35,
            "base_attack": 55,
            "base_defense": 40,
            "base_stamina": 90,
        },
    )

    db = AsyncMock()
    db.admin_create_pokemon_species = AsyncMock(side_effect=ShopError("Покемон с таким ID уже существует."))
    application = Mock()
    application.bot_data = {"db": db}
    context = Mock(spec=ContextTypes.DEFAULT_TYPE)
    context.application = application

    with pytest.raises(ShopError, match="уже существует"):
        await _execute_create_pokemon(Mock(spec=Update), context, pending_action)


@pytest.mark.asyncio
async def test_execute_update_pokemon_species_surfaces_validation_error() -> None:
    pending_action = AdminPendingAction(
        action_type="catalog.update_pokemon_species",
        title="Изменить вид покемона",
        description="Будет изменена редкость.",
        input_payload={
            "pokemon_id": 25,
            "field_key": "rarity",
            "field_label": "Редкость",
            "old_value": "Rare",
            "new_value": "Mythic",
        },
    )

    db = AsyncMock()
    db.admin_update_pokemon_species_field = AsyncMock(side_effect=ShopError("Редкость должна быть одной из: Common, Rare, Epic, Legendary."))
    application = Mock()
    application.bot_data = {"db": db}
    context = Mock(spec=ContextTypes.DEFAULT_TYPE)
    context.application = application

    with pytest.raises(ShopError, match="Редкость должна быть одной из"):
        await _execute_update_pokemon_species(Mock(spec=Update), context, pending_action)


@pytest.mark.asyncio
async def test_confirm_pending_action_expired_clears_session_and_audits() -> None:
    set_admin_settings_for_tests(_allowed_settings())
    register_admin_routes()

    update, user, chat, _ = _private_update()
    message = Mock(spec=Message)
    message.message_id = 101
    message.chat = chat
    message.chat_id = chat.id
    message.message_thread_id = None
    message.edit_text = AsyncMock()

    session_id = admin_session_store.create_session(
        chat_id=chat.id,
        message_id=message.message_id,
        user_id=user.id,
        data={
            "screen": "pending_action",
            "pending_action": AdminPendingAction(
                action_type="grant.currency",
                title="Выдать PokéCoin",
                description="Будет выдано 10 PokéCoin.",
                input_payload={"amount": 10},
                created_at=datetime.now(UTC) - timedelta(seconds=ADMIN_PENDING_ACTION_TTL_SECONDS + 1),
            ).to_session_payload(),
        },
    )
    session = admin_session_store.get_session(session_id)
    assert session is not None

    callback = Mock(spec=CallbackQuery)
    callback.id = "cb-expired"
    callback.data = f"menu:adc:{session_id}"
    callback.message = message
    callback.answer = AsyncMock()

    callback_update = Mock(spec=Update)
    callback_update.effective_user = user
    callback_update.effective_chat = chat
    callback_update.effective_message = message
    callback_update.callback_query = callback

    db = AsyncMock()
    application = Mock()
    application.bot_data = {"db": db}
    context = Mock(spec=ContextTypes.DEFAULT_TYPE)
    context.application = application

    await _confirm_pending_action(callback_update, context, session)

    callback.answer.assert_awaited()
    message.edit_text.assert_awaited()
    assert admin_session_store.get_session(session_id) is None
    db.record_admin_action_audit.assert_awaited_once()
    assert db.record_admin_action_audit.await_args.kwargs["status"] == "expired"


@pytest.mark.asyncio
async def test_cancel_pending_action_clears_session_and_audits() -> None:
    set_admin_settings_for_tests(_allowed_settings())
    register_admin_routes()

    update, user, chat, _ = _private_update()
    message = Mock(spec=Message)
    message.message_id = 101
    message.chat = chat
    message.chat_id = chat.id
    message.message_thread_id = None
    message.edit_text = AsyncMock()

    session_id = admin_session_store.create_session(
        chat_id=chat.id,
        message_id=message.message_id,
        user_id=user.id,
        data={
            "screen": "pending_action",
            "pending_action": AdminPendingAction(
                action_type="grant.pokemon",
                title="Выдать покемона",
                description="Будет выдан Cloyster.",
                input_payload={"pokemon_id": 91},
                target_username="misty",
            ).to_session_payload(),
        },
    )
    session = admin_session_store.get_session(session_id)
    assert session is not None

    callback = Mock(spec=CallbackQuery)
    callback.id = "cb-cancel"
    callback.message = message

    callback_update = Mock(spec=Update)
    callback_update.effective_user = user
    callback_update.effective_chat = chat
    callback_update.effective_message = message
    callback_update.callback_query = callback

    db = AsyncMock()
    application = Mock()
    application.bot_data = {"db": db}
    context = Mock(spec=ContextTypes.DEFAULT_TYPE)
    context.application = application

    await _cancel_pending_action(callback_update, context, session)

    message.edit_text.assert_awaited()
    assert admin_session_store.get_session(session_id) is None
    db.record_admin_action_audit.assert_awaited_once()
    assert db.record_admin_action_audit.await_args.kwargs["status"] == "canceled"


def test_admin_audit_text_empty_state() -> None:
    text = get_admin_audit_text([])
    assert "Записей пока нет" in text


def test_admin_audit_export_text_contains_record_payloads() -> None:
    record = AdminAuditRecord(
        audit_id=5,
        actor_user_id=1,
        actor_telegram_id=12345,
        actor_username="ash",
        action_type="grant.currency",
        target_user_id=2,
        target_telegram_id=54321,
        target_username="misty",
        status="success",
        input_payload={"amount": 500, "currency": "pokedollar"},
        result_payload={"balance": 1750},
        error_message=None,
        created_at=datetime(2026, 4, 29, 12, 0, tzinfo=UTC),
    )

    text = build_admin_audit_export_text([record])

    assert "Admin audit export" in text
    assert "action_type: grant.currency" in text
    assert '"amount": 500' in text
    assert '"balance": 1750' in text


def test_coerce_json_object_accepts_json_string_payload() -> None:
    payload = _coerce_json_object('{"amount": 500, "currency": "pokedollar"}')
    assert payload == {"amount": 500, "currency": "pokedollar"}
