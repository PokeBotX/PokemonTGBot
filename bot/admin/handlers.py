"""Handlers and callback flow for the separate admin bot."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from io import BytesIO
from typing import Optional

import structlog
from telegram import Document, InputFile, Message, PhotoSize, Update
from telegram.error import TelegramError
from telegram.ext import ContextTypes

from bot.admin.config import AdminBotSettings, load_admin_bot_settings
from bot.admin.pending import AdminPendingAction
from bot.admin.session import admin_session_store
from bot.admin.storage import build_admin_object_key, upload_admin_image_bytes
from bot.admin.ui import (
    ADMIN_SECTIONS,
    SECTION_AUDIT,
    SECTION_AUDIT_EXPORT,
    SECTION_CANCEL,
    SECTION_CONFIRM,
    SECTION_CREATE_POKEMON,
    SECTION_GRANT_POKECOIN,
    SECTION_GRANT_POKEDOLLAR,
    SECTION_GRANT_POKEMON,
    SECTION_GRANTS,
    SECTION_IMAGE_UPLOAD_VARIANT,
    SECTION_IMAGE_EDIT_SOURCE,
    SECTION_IMAGE_EDIT_VARIANT,
    SECTION_IMAGES,
    SECTION_POKEMON,
    SECTION_ROOT,
    build_admin_back_keyboard,
    build_admin_audit_export_text,
    build_admin_audit_keyboard,
    build_admin_confirmation_keyboard,
    build_admin_grants_keyboard,
    build_admin_images_keyboard,
    build_admin_pokemon_keyboard,
    build_admin_root_keyboard,
    get_access_denied_text,
    get_action_canceled_text,
    get_action_expired_text,
    get_admin_welcome_text,
    get_admin_audit_text,
    get_create_pokemon_field_prompt,
    get_create_pokemon_intro_text,
    get_create_pokemon_summary_text,
    get_grant_amount_prompt,
    get_grant_pokemon_prompt,
    get_grant_username_prompt,
    get_image_upload_default_prompt,
    get_image_upload_intro_text,
    get_image_upload_order_prompt,
    get_image_upload_pokemon_prompt,
    get_image_upload_source_prompt,
    get_image_upload_summary_text,
    get_image_credit_id_prompt,
    get_image_source_edit_prompt,
    get_image_source_update_summary_text,
    get_images_section_text,
    get_pending_action_text,
    get_placeholder_section_text,
    get_pokemon_section_text,
    get_private_only_text,
    get_grants_section_text,
    get_variant_default_prompt,
    get_variant_image_credit_id_prompt,
    get_variant_order_prompt,
    get_variant_pokemon_id_prompt,
    get_variant_update_summary_text,
)
from bot.db.database import POKECOIN_CODE, POKEDOLLAR_CODE, ShopError
from bot.navigation.router import NavigationRouter, parse_callback_data

logger = structlog.get_logger()

ADMIN_ERROR_INVALID_CALLBACK = "⚠️ Кнопка больше недоступна."
ADMIN_ERROR_NOT_YOUR_BUTTON = "⚠️ Это не ваша кнопка."
ADMIN_ERROR_STALE_MENU = "⚠️ Меню устарело."
ADMIN_ERROR_PROCESSING = "⏳ Действие уже обрабатывается."
ADMIN_ERROR_EXPIRED_ACTION = "⚠️ Окно подтверждения уже истекло."
ADMIN_ERROR_NOT_IMPLEMENTED = "🧩 Этот админ-действие ещё не подключено."
ADMIN_PENDING_GRANT_POKEDOLLAR_USERNAME = "grant_pokedollar_username"
ADMIN_PENDING_GRANT_POKECOIN_USERNAME = "grant_pokecoin_username"
ADMIN_PENDING_GRANT_POKEMON_USERNAME = "grant_pokemon_username"
ADMIN_PENDING_GRANT_POKEDOLLAR_AMOUNT = "grant_pokedollar_amount"
ADMIN_PENDING_GRANT_POKECOIN_AMOUNT = "grant_pokecoin_amount"
ADMIN_PENDING_GRANT_POKEMON_ID = "grant_pokemon_id"
ADMIN_PENDING_CREATE_POKEMON_FIELD = "create_pokemon_field"
ADMIN_PENDING_IMAGE_UPLOAD_FILE = "image_upload_file"
ADMIN_PENDING_IMAGE_UPLOAD_POKEMON_ID = "image_upload_pokemon_id"
ADMIN_PENDING_IMAGE_UPLOAD_SOURCE = "image_upload_source"
ADMIN_PENDING_IMAGE_UPLOAD_ORDER = "image_upload_order"
ADMIN_PENDING_IMAGE_UPLOAD_DEFAULT = "image_upload_default"
ADMIN_PENDING_IMAGE_SOURCE_EDIT_ID = "image_source_edit_id"
ADMIN_PENDING_IMAGE_SOURCE_EDIT_VALUE = "image_source_edit_value"
ADMIN_PENDING_IMAGE_VARIANT_POKEMON_ID = "image_variant_pokemon_id"
ADMIN_PENDING_IMAGE_VARIANT_CREDIT_ID = "image_variant_credit_id"
ADMIN_PENDING_IMAGE_VARIANT_ORDER = "image_variant_order"
ADMIN_PENDING_IMAGE_VARIANT_DEFAULT = "image_variant_default"
ADMIN_ACTION_GRANT_CURRENCY = "grant.currency"
ADMIN_ACTION_GRANT_POKEMON = "grant.pokemon"
ADMIN_ACTION_CREATE_POKEMON = "catalog.create_pokemon"
ADMIN_ACTION_ATTACH_IMAGE_VARIANT = "images.attach_variant"
ADMIN_ACTION_UPDATE_IMAGE_SOURCE = "images.update_source"
ADMIN_ACTION_UPDATE_IMAGE_VARIANT = "images.update_variant"
ADMIN_AUDIT_PREVIEW_LIMIT = 10
ADMIN_AUDIT_EXPORT_LIMIT = 200

CREATE_POKEMON_FIELDS: tuple[tuple[str, str, str], ...] = (
    ("pokemon_id", "ID", "Отправьте числовой id нового покемона."),
    ("name", "Имя", "Отправьте имя нового покемона."),
    ("pokemon_type", "Тип", "Отправьте тип покемона или <code>-</code>, если типа нет."),
    ("rarity", "Редкость", "Отправьте редкость: Common, Rare, Epic или Legendary."),
    ("base_hp", "HP", "Отправьте базовое значение HP."),
    ("base_attack", "ATK", "Отправьте базовое значение атаки."),
    ("base_defense", "DEF", "Отправьте базовое значение защиты."),
    ("base_stamina", "SPD", "Отправьте базовое значение скорости/стамины."),
)
CREATE_POKEMON_ALLOWED_RARITIES = {"Common", "Rare", "Epic", "Legendary"}

PendingExecutor = Callable[
    [Update, ContextTypes.DEFAULT_TYPE, AdminPendingAction],
    Awaitable[dict[str, object] | None],
]

admin_router = NavigationRouter()
_pending_executors: dict[str, PendingExecutor] = {}
_cached_settings: AdminBotSettings | None = None


def get_admin_settings() -> AdminBotSettings:
    """Return cached admin-bot settings."""
    global _cached_settings
    if _cached_settings is None:
        _cached_settings = load_admin_bot_settings()
    return _cached_settings


def set_admin_settings_for_tests(settings: AdminBotSettings | None) -> None:
    """Override cached settings for tests."""
    global _cached_settings
    _cached_settings = settings


def register_pending_executor(action_type: str, executor: PendingExecutor) -> None:
    """Register a pending-action executor."""
    _pending_executors[action_type] = executor


def unregister_pending_executor(action_type: str) -> None:
    """Remove a pending-action executor."""
    _pending_executors.pop(action_type, None)


def _db_from_context(context: ContextTypes.DEFAULT_TYPE):
    application = getattr(context, "application", None)
    return application.bot_data.get("db") if application and isinstance(application.bot_data, dict) else None


async def _send_chat_message(
    update: Update,
    text: str,
    *,
    reply_markup=None,
) -> Optional[Message]:
    """Send a message to the active chat if available."""
    chat = update.effective_chat
    if not chat:
        return None
    return await chat.send_message(text=text, parse_mode="HTML", reply_markup=reply_markup)


def _extract_text_argument(update: Update) -> str:
    message = update.effective_message
    return (message.text or "").strip() if message is not None and isinstance(message.text, str) else ""


async def _audit_admin_event(
    context: ContextTypes.DEFAULT_TYPE,
    *,
    actor_telegram_id: int,
    actor_username: str | None,
    action_type: str,
    status: str,
    input_payload: dict[str, object] | None = None,
    result_payload: dict[str, object] | None = None,
    error_message: str | None = None,
    target_user_id: int | None = None,
    target_telegram_id: int | None = None,
    target_username: str | None = None,
) -> None:
    """Write one admin audit record when DB is available."""
    db = _db_from_context(context)
    if db is None:
        return
    await db.record_admin_action_audit(
        actor_telegram_id=actor_telegram_id,
        actor_username=actor_username,
        action_type=action_type,
        status=status,
        input_payload=input_payload,
        result_payload=result_payload,
        error_message=error_message,
        target_user_id=target_user_id,
        target_telegram_id=target_telegram_id,
        target_username=target_username,
    )


async def ensure_admin_access(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    *,
    answer_callback: bool = False,
) -> bool:
    """Return True when the user is an allowed superadmin in a private chat."""
    user = update.effective_user
    chat = update.effective_chat
    if user is None or chat is None:
        return False

    if chat.type != "private":
        if update.callback_query and answer_callback:
            await update.callback_query.answer(get_private_only_text(), show_alert=True)
        else:
            await _send_chat_message(update, get_private_only_text())
        return False

    settings = get_admin_settings()
    if not settings.is_allowed(user.id):
        if update.callback_query and answer_callback:
            await update.callback_query.answer(get_access_denied_text(), show_alert=True)
        else:
            await _send_chat_message(update, get_access_denied_text())
        logger.warning("admin_access_denied", telegram_id=user.id, username=user.username)
        return False
    return True


def _create_session(message: Message, *, user_id: int, data: dict[str, object]) -> str:
    return admin_session_store.create_session(
        chat_id=message.chat_id,
        message_id=message.message_id,
        user_id=user_id,
        message_thread_id=getattr(message, "message_thread_id", None),
        data=data,
    )


def _session_allows_user(session, user_id: int) -> bool:
    return session.user_id == user_id


async def show_admin_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Send the root admin menu."""
    if not await ensure_admin_access(update, context):
        return
    user = update.effective_user
    sent_message = await _send_chat_message(
        update,
        get_admin_welcome_text(user.username if user else None),
    )
    if sent_message is None or user is None:
        return
    session_id = _create_session(
        sent_message,
        user_id=user.id,
        data={"screen": "root"},
    )
    await sent_message.edit_reply_markup(reply_markup=build_admin_root_keyboard(session_id))
    logger.info("admin_menu_sent", telegram_id=user.id, username=user.username)


async def start_admin_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /start for the admin bot."""
    await show_admin_menu(update, context)


async def menu_admin_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /menu for the admin bot."""
    await show_admin_menu(update, context)


async def show_pending_action_preview(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    *,
    pending_action: AdminPendingAction,
) -> Optional[str]:
    """Show a standard confirmation preview and stage the action in session storage."""
    if not await ensure_admin_access(update, context):
        return None
    user = update.effective_user
    sent_message = await _send_chat_message(
        update,
        get_pending_action_text(
            title=pending_action.title,
            description=pending_action.description,
        ),
    )
    if sent_message is None or user is None:
        return None

    session_id = _create_session(
        sent_message,
        user_id=user.id,
        data={
            "screen": "pending_action",
            "pending_action": pending_action.to_session_payload(),
        },
    )
    await sent_message.edit_reply_markup(reply_markup=build_admin_confirmation_keyboard(session_id))
    await _audit_admin_event(
        context,
        actor_telegram_id=user.id,
        actor_username=user.username,
        action_type=pending_action.action_type,
        status="pending",
        input_payload=pending_action.input_payload,
        target_user_id=pending_action.target_user_id,
        target_telegram_id=pending_action.target_telegram_id,
        target_username=pending_action.target_username,
    )
    return session_id


def _grants_back_session(update: Update, session) -> str:
    return admin_session_store.create_session(
        chat_id=session.chat_id,
        message_id=update.callback_query.message.message_id,
        message_thread_id=getattr(update.callback_query.message, "message_thread_id", None),
        user_id=session.user_id,
        data={"screen": SECTION_GRANTS},
    )


async def _show_grants_section(update: Update, context: ContextTypes.DEFAULT_TYPE, session) -> None:
    next_session_id = admin_session_store.create_session(
        chat_id=session.chat_id,
        message_id=update.callback_query.message.message_id,
        message_thread_id=getattr(update.callback_query.message, "message_thread_id", None),
        user_id=session.user_id,
        data={"screen": SECTION_GRANTS},
    )
    await update.callback_query.message.edit_text(
        get_grants_section_text(),
        parse_mode="HTML",
        reply_markup=build_admin_grants_keyboard(next_session_id),
    )


async def _show_pokemon_section(update: Update, context: ContextTypes.DEFAULT_TYPE, session) -> None:
    next_session_id = admin_session_store.create_session(
        chat_id=session.chat_id,
        message_id=update.callback_query.message.message_id,
        message_thread_id=getattr(update.callback_query.message, "message_thread_id", None),
        user_id=session.user_id,
        data={"screen": SECTION_POKEMON},
    )
    await update.callback_query.message.edit_text(
        get_pokemon_section_text(),
        parse_mode="HTML",
        reply_markup=build_admin_pokemon_keyboard(next_session_id),
    )


async def _show_images_section(update: Update, context: ContextTypes.DEFAULT_TYPE, session) -> None:
    next_session_id = admin_session_store.create_session(
        chat_id=session.chat_id,
        message_id=update.callback_query.message.message_id,
        message_thread_id=getattr(update.callback_query.message, "message_thread_id", None),
        user_id=session.user_id,
        data={"screen": SECTION_IMAGES},
    )
    await update.callback_query.message.edit_text(
        get_images_section_text(),
        parse_mode="HTML",
        reply_markup=build_admin_images_keyboard(next_session_id),
    )


async def _show_audit_section(update: Update, context: ContextTypes.DEFAULT_TYPE, session) -> None:
    db = _db_from_context(context)
    if db is None:
        await update.callback_query.message.edit_text(
            "⚠️ База данных недоступна.",
            parse_mode="HTML",
            reply_markup=build_admin_back_keyboard(
                admin_session_store.create_session(
                    chat_id=session.chat_id,
                    message_id=update.callback_query.message.message_id,
                    message_thread_id=getattr(update.callback_query.message, "message_thread_id", None),
                    user_id=session.user_id,
                    data={"screen": SECTION_ROOT},
                )
            ),
        )
        return
    records = await db.get_recent_admin_action_audit(limit=ADMIN_AUDIT_PREVIEW_LIMIT)
    next_session_id = admin_session_store.create_session(
        chat_id=session.chat_id,
        message_id=update.callback_query.message.message_id,
        message_thread_id=getattr(update.callback_query.message, "message_thread_id", None),
        user_id=session.user_id,
        data={"screen": SECTION_AUDIT},
    )
    await update.callback_query.message.edit_text(
        get_admin_audit_text(records),
        parse_mode="HTML",
        reply_markup=build_admin_audit_keyboard(next_session_id),
    )


async def _export_audit_section(update: Update, context: ContextTypes.DEFAULT_TYPE, session) -> None:
    db = _db_from_context(context)
    if db is None:
        await update.callback_query.answer("⚠️ База данных недоступна.", show_alert=True)
        return
    records = await db.get_recent_admin_action_audit(limit=ADMIN_AUDIT_EXPORT_LIMIT)
    export_text = build_admin_audit_export_text(records)
    filename = "admin-audit-export.txt"
    document = InputFile(BytesIO(export_text.encode("utf-8")), filename=filename)
    await update.effective_chat.send_document(
        document=document,
        caption=f"🧾 Экспорт аудита\n\nЗаписей: <b>{len(records)}</b>",
        parse_mode="HTML",
    )
    logger.info(
        "admin_audit_export_sent",
        actor_telegram_id=update.effective_user.id if update.effective_user else None,
        records=len(records),
    )


def _pokemon_back_session(update: Update, session) -> str:
    return admin_session_store.create_session(
        chat_id=session.chat_id,
        message_id=update.callback_query.message.message_id,
        message_thread_id=getattr(update.callback_query.message, "message_thread_id", None),
        user_id=session.user_id,
        data={"screen": SECTION_POKEMON},
    )


def _images_back_session(update: Update, session) -> str:
    return admin_session_store.create_session(
        chat_id=session.chat_id,
        message_id=update.callback_query.message.message_id,
        message_thread_id=getattr(update.callback_query.message, "message_thread_id", None),
        user_id=session.user_id,
        data={"screen": SECTION_IMAGES},
    )


def _build_create_pokemon_prompt(field_index: int) -> str:
    field_key, field_label, field_hint = CREATE_POKEMON_FIELDS[field_index]
    return get_create_pokemon_field_prompt(
        field_label=field_label,
        step=field_index + 1,
        total_steps=len(CREATE_POKEMON_FIELDS),
        hint=field_hint,
    )


async def _start_create_pokemon(update: Update, context: ContextTypes.DEFAULT_TYPE, session) -> None:
    admin_session_store.set_pending_input(
        action=ADMIN_PENDING_CREATE_POKEMON_FIELD,
        chat_id=session.chat_id,
        user_id=session.user_id,
        source_message_id=update.callback_query.message.message_id,
        source_message_thread_id=getattr(update.callback_query.message, "message_thread_id", None),
        data={"field_index": 0, "draft": {}},
    )
    await update.callback_query.message.edit_text(
        f"{get_create_pokemon_intro_text()}\n\n{_build_create_pokemon_prompt(0)}",
        parse_mode="HTML",
        reply_markup=build_admin_back_keyboard(_pokemon_back_session(update, session)),
    )


async def _start_image_upload_variant(update: Update, context: ContextTypes.DEFAULT_TYPE, session) -> None:
    admin_session_store.set_pending_input(
        action=ADMIN_PENDING_IMAGE_UPLOAD_FILE,
        chat_id=session.chat_id,
        user_id=session.user_id,
        source_message_id=update.callback_query.message.message_id,
        source_message_thread_id=getattr(update.callback_query.message, "message_thread_id", None),
        data={},
    )
    await update.callback_query.message.edit_text(
        get_image_upload_intro_text(),
        parse_mode="HTML",
        reply_markup=build_admin_back_keyboard(_images_back_session(update, session)),
    )


async def _start_image_source_edit(update: Update, context: ContextTypes.DEFAULT_TYPE, session) -> None:
    admin_session_store.set_pending_input(
        action=ADMIN_PENDING_IMAGE_SOURCE_EDIT_ID,
        chat_id=session.chat_id,
        user_id=session.user_id,
        source_message_id=update.callback_query.message.message_id,
        source_message_thread_id=getattr(update.callback_query.message, "message_thread_id", None),
        data={},
    )
    await update.callback_query.message.edit_text(
        get_image_credit_id_prompt("Изменение source"),
        parse_mode="HTML",
        reply_markup=build_admin_back_keyboard(_images_back_session(update, session)),
    )


async def _start_image_variant_edit(update: Update, context: ContextTypes.DEFAULT_TYPE, session) -> None:
    admin_session_store.set_pending_input(
        action=ADMIN_PENDING_IMAGE_VARIANT_POKEMON_ID,
        chat_id=session.chat_id,
        user_id=session.user_id,
        source_message_id=update.callback_query.message.message_id,
        source_message_thread_id=getattr(update.callback_query.message, "message_thread_id", None),
        data={},
    )
    await update.callback_query.message.edit_text(
        get_variant_pokemon_id_prompt(),
        parse_mode="HTML",
        reply_markup=build_admin_back_keyboard(_images_back_session(update, session)),
    )


async def _start_grant_username_flow(update: Update, context: ContextTypes.DEFAULT_TYPE, session, *, action: str, action_label: str, data: dict[str, object]) -> None:
    admin_session_store.set_pending_input(
        action=action,
        chat_id=session.chat_id,
        user_id=session.user_id,
        source_message_id=update.callback_query.message.message_id,
        source_message_thread_id=getattr(update.callback_query.message, "message_thread_id", None),
        data=data,
    )
    await update.callback_query.message.edit_text(
        get_grant_username_prompt(action_label),
        parse_mode="HTML",
        reply_markup=build_admin_back_keyboard(_grants_back_session(update, session)),
    )


async def _start_grant_pokedollar(update: Update, context: ContextTypes.DEFAULT_TYPE, session) -> None:
    await _start_grant_username_flow(
        update,
        context,
        session,
        action=ADMIN_PENDING_GRANT_POKEDOLLAR_USERNAME,
        action_label="Выдача PokéDollar",
        data={
            "currency_code": POKEDOLLAR_CODE,
            "currency_label": "PokéDollar",
        },
    )


async def _start_grant_pokecoin(update: Update, context: ContextTypes.DEFAULT_TYPE, session) -> None:
    await _start_grant_username_flow(
        update,
        context,
        session,
        action=ADMIN_PENDING_GRANT_POKECOIN_USERNAME,
        action_label="Выдача PokéCoin",
        data={
            "currency_code": POKECOIN_CODE,
            "currency_label": "PokéCoin",
        },
    )


async def _start_grant_pokemon(update: Update, context: ContextTypes.DEFAULT_TYPE, session) -> None:
    await _start_grant_username_flow(
        update,
        context,
        session,
        action=ADMIN_PENDING_GRANT_POKEMON_USERNAME,
        action_label="Выдача покемона",
        data={"flow": "pokemon"},
    )


async def _show_placeholder_section(update: Update, context: ContextTypes.DEFAULT_TYPE, session, section: str) -> None:
    admin_session_store.clear_pending_input(chat_id=session.chat_id, user_id=session.user_id)
    title = ADMIN_SECTIONS.get(section, "Раздел")
    next_session_id = admin_session_store.create_session(
        chat_id=session.chat_id,
        message_id=update.callback_query.message.message_id,
        message_thread_id=getattr(update.callback_query.message, "message_thread_id", None),
        user_id=session.user_id,
        data={"screen": section},
    )
    await update.callback_query.message.edit_text(
        get_placeholder_section_text(title),
        parse_mode="HTML",
        reply_markup=build_admin_back_keyboard(next_session_id),
    )


async def _return_to_root(update: Update, context: ContextTypes.DEFAULT_TYPE, session) -> None:
    admin_session_store.clear_pending_input(chat_id=session.chat_id, user_id=session.user_id)
    next_session_id = admin_session_store.create_session(
        chat_id=session.chat_id,
        message_id=update.callback_query.message.message_id,
        message_thread_id=getattr(update.callback_query.message, "message_thread_id", None),
        user_id=session.user_id,
        data={"screen": "root"},
    )
    await update.callback_query.message.edit_text(
        get_admin_welcome_text(update.effective_user.username if update.effective_user else None),
        parse_mode="HTML",
        reply_markup=build_admin_root_keyboard(next_session_id),
    )


async def _confirm_pending_action(update: Update, context: ContextTypes.DEFAULT_TYPE, session) -> None:
    pending_action = AdminPendingAction.from_session_payload(session.data.get("pending_action"))
    if pending_action is None:
        await update.callback_query.answer(ADMIN_ERROR_INVALID_CALLBACK, show_alert=True)
        return
    if pending_action.is_expired():
        admin_session_store.delete_session(session.session_id)
        await _audit_admin_event(
            context,
            actor_telegram_id=update.effective_user.id,
            actor_username=update.effective_user.username,
            action_type=pending_action.action_type,
            status="expired",
            input_payload=pending_action.input_payload,
            target_user_id=pending_action.target_user_id,
            target_telegram_id=pending_action.target_telegram_id,
            target_username=pending_action.target_username,
        )
        await update.callback_query.answer(ADMIN_ERROR_EXPIRED_ACTION, show_alert=True)
        await update.callback_query.message.edit_text(
            get_action_expired_text(pending_action.title),
            parse_mode="HTML",
        )
        return

    executor = _pending_executors.get(pending_action.action_type)
    if executor is None:
        await update.callback_query.answer(ADMIN_ERROR_NOT_IMPLEMENTED, show_alert=True)
        return

    try:
        result_payload = await executor(update, context, pending_action) or {}
    except Exception as exc:
        admin_session_store.delete_session(session.session_id)
        await _audit_admin_event(
            context,
            actor_telegram_id=update.effective_user.id,
            actor_username=update.effective_user.username,
            action_type=pending_action.action_type,
            status="failed",
            input_payload=pending_action.input_payload,
            error_message=str(exc),
            target_user_id=pending_action.target_user_id,
            target_telegram_id=pending_action.target_telegram_id,
            target_username=pending_action.target_username,
        )
        logger.exception(
            "admin_action_failed",
            action_type=pending_action.action_type,
            actor_telegram_id=update.effective_user.id,
        )
        await update.callback_query.message.edit_text(
            f"❌ Не удалось выполнить действие.\n\n<code>{pending_action.action_type}</code>\n{str(exc)}",
            parse_mode="HTML",
        )
        return

    admin_session_store.delete_session(session.session_id)
    await _audit_admin_event(
        context,
        actor_telegram_id=update.effective_user.id,
        actor_username=update.effective_user.username,
        action_type=pending_action.action_type,
        status="success",
        input_payload=pending_action.input_payload,
        result_payload=result_payload,
        target_user_id=pending_action.target_user_id,
        target_telegram_id=pending_action.target_telegram_id,
        target_username=pending_action.target_username,
    )
    result_suffix = ""
    summary_text = result_payload.get("summary_text") if isinstance(result_payload, dict) else None
    if isinstance(summary_text, str) and summary_text.strip():
        result_suffix = f"\n\n{summary_text}"
    await update.callback_query.message.edit_text(
        "✅ Действие выполнено.\n\n"
        f"<b>{pending_action.title}</b>{result_suffix}",
        parse_mode="HTML",
    )


async def _cancel_pending_action(update: Update, context: ContextTypes.DEFAULT_TYPE, session) -> None:
    pending_action = AdminPendingAction.from_session_payload(session.data.get("pending_action"))
    admin_session_store.delete_session(session.session_id)
    if pending_action is not None:
        await _audit_admin_event(
            context,
            actor_telegram_id=update.effective_user.id,
            actor_username=update.effective_user.username,
            action_type=pending_action.action_type,
            status="canceled",
            input_payload=pending_action.input_payload,
            target_user_id=pending_action.target_user_id,
            target_telegram_id=pending_action.target_telegram_id,
            target_username=pending_action.target_username,
        )
        await update.callback_query.message.edit_text(
            get_action_canceled_text(pending_action.title),
            parse_mode="HTML",
        )
        return
    await update.callback_query.message.edit_text("↩️ Действие отменено.", parse_mode="HTML")


async def _execute_currency_grant(update: Update, context: ContextTypes.DEFAULT_TYPE, pending_action: AdminPendingAction) -> dict[str, object]:
    db = _db_from_context(context)
    if db is None:
        raise ShopError("База данных недоступна.")

    input_payload = pending_action.input_payload
    target_user_id = pending_action.target_user_id
    currency_code = str(input_payload["currency_code"])
    amount = int(input_payload["amount"])
    balance = await db.admin_grant_currency(
        target_user_id=target_user_id,
        currency_code=currency_code,
        amount=amount,
    )
    currency_label = str(input_payload["currency_label"])
    target_label = f"@{pending_action.target_username}" if pending_action.target_username else "пользователю"
    return {
        "currency_code": currency_code,
        "amount": amount,
        "balance": balance,
        "summary_text": (
            f"Выдано: <b>{amount}</b> {currency_label}\n"
            f"Получатель: <code>{target_label}</code>\n"
            f"Новый баланс: <b>{balance}</b>"
        ),
    }


async def _execute_pokemon_grant(update: Update, context: ContextTypes.DEFAULT_TYPE, pending_action: AdminPendingAction) -> dict[str, object]:
    db = _db_from_context(context)
    if db is None:
        raise ShopError("База данных недоступна.")

    input_payload = pending_action.input_payload
    target_user_id = pending_action.target_user_id
    pokemon_id = int(input_payload["pokemon_id"])
    pokemon_name = str(input_payload["pokemon_name"])
    user_pokemon_id = await db.admin_grant_pokemon(
        target_user_id=target_user_id,
        pokemon_id=pokemon_id,
    )
    target_label = f"@{pending_action.target_username}" if pending_action.target_username else "пользователю"
    return {
        "pokemon_id": pokemon_id,
        "pokemon_name": pokemon_name,
        "user_pokemon_id": user_pokemon_id,
        "summary_text": (
            f"Выдан покемон: <b>{pokemon_name}</b> (#{pokemon_id})\n"
            f"Получатель: <code>{target_label}</code>\n"
            f"ID экземпляра: <code>{user_pokemon_id}</code>"
        ),
    }


async def _execute_create_pokemon(update: Update, context: ContextTypes.DEFAULT_TYPE, pending_action: AdminPendingAction) -> dict[str, object]:
    db = _db_from_context(context)
    if db is None:
        raise ShopError("База данных недоступна.")

    input_payload = pending_action.input_payload
    created_id = await db.admin_create_pokemon_species(
        pokemon_id=int(input_payload["pokemon_id"]),
        name=str(input_payload["name"]),
        pokemon_type=input_payload.get("pokemon_type") if isinstance(input_payload.get("pokemon_type"), str) else None,
        rarity=str(input_payload["rarity"]),
        base_hp=int(input_payload["base_hp"]),
        base_attack=int(input_payload["base_attack"]),
        base_defense=int(input_payload["base_defense"]),
        base_stamina=int(input_payload["base_stamina"]),
    )
    return {
        "pokemon_id": created_id,
        "name": str(input_payload["name"]),
        "summary_text": (
            f"Создан покемон: <b>{str(input_payload['name'])}</b>\n"
            f"ID: <code>{created_id}</code>"
        ),
    }


async def _execute_attach_image_variant(update: Update, context: ContextTypes.DEFAULT_TYPE, pending_action: AdminPendingAction) -> dict[str, object]:
    db = _db_from_context(context)
    if db is None:
        raise ShopError("База данных недоступна.")

    input_payload = pending_action.input_payload
    file_id = str(input_payload["telegram_file_id"])
    file_unique_id = str(input_payload["telegram_file_unique_id"])
    file_name = input_payload.get("file_name") if isinstance(input_payload.get("file_name"), str) else None
    content_type = input_payload.get("content_type") if isinstance(input_payload.get("content_type"), str) else None
    pokemon_id = int(input_payload["pokemon_id"])
    pokemon_name = str(input_payload["pokemon_name"])

    telegram_file = await context.bot.get_file(file_id)
    file_bytes = bytes(await telegram_file.download_as_bytearray())
    object_key = build_admin_object_key(
        pokemon_id=pokemon_id,
        pokemon_name=pokemon_name,
        file_unique_id=file_unique_id,
        file_name=file_name,
    )
    storage_bucket, object_key, etag = await upload_admin_image_bytes(
        object_key=object_key,
        file_bytes=file_bytes,
        content_type=content_type,
    )
    image_credit_id = await db.admin_attach_image_variant(
        pokemon_id=pokemon_id,
        storage_bucket=storage_bucket,
        object_key=object_key,
        content_type=content_type,
        etag=etag,
        source=input_payload.get("source") if isinstance(input_payload.get("source"), str) else None,
        display_order=int(input_payload["display_order"]),
        is_default=bool(input_payload["is_default"]),
    )
    return {
        "image_credit_id": image_credit_id,
        "pokemon_id": pokemon_id,
        "summary_text": (
            f"Добавлен variant для <b>{pokemon_name}</b> (#{pokemon_id})\n"
            f"image_credit_id: <code>{image_credit_id}</code>"
        ),
    }


async def _execute_update_image_source(update: Update, context: ContextTypes.DEFAULT_TYPE, pending_action: AdminPendingAction) -> dict[str, object]:
    db = _db_from_context(context)
    if db is None:
        raise ShopError("База данных недоступна.")
    input_payload = pending_action.input_payload
    image_credit_id = int(input_payload["image_credit_id"])
    source = input_payload.get("source") if isinstance(input_payload.get("source"), str) else None
    await db.admin_update_image_source(image_credit_id=image_credit_id, source=source)
    source_text = source or "—"
    return {
        "image_credit_id": image_credit_id,
        "summary_text": (
            f"Обновлён source для image_credit_id <code>{image_credit_id}</code>\n"
            f"Новый source: <code>{source_text}</code>"
        ),
    }


async def _execute_update_image_variant(update: Update, context: ContextTypes.DEFAULT_TYPE, pending_action: AdminPendingAction) -> dict[str, object]:
    db = _db_from_context(context)
    if db is None:
        raise ShopError("База данных недоступна.")
    input_payload = pending_action.input_payload
    image_credit_id = await db.admin_update_image_variant_metadata(
        pokemon_id=int(input_payload["pokemon_id"]),
        image_credit_id=int(input_payload["image_credit_id"]),
        display_order=int(input_payload["display_order"]),
        is_default=bool(input_payload["is_default"]),
    )
    return {
        "image_credit_id": image_credit_id,
        "summary_text": (
            f"Обновлён вариант <code>{image_credit_id}</code>\n"
            f"display_order: <b>{int(input_payload['display_order'])}</b>\n"
            f"default: <b>{'да' if bool(input_payload['is_default']) else 'нет'}</b>"
        ),
    }


def _normalize_create_pokemon_field(*, field_key: str, raw_value: str) -> object:
    normalized = raw_value.strip()
    if field_key in {"pokemon_id", "base_hp", "base_attack", "base_defense", "base_stamina"}:
        value = int(normalized)
        if value < 0:
            raise ShopError(f"{field_key} не может быть отрицательным.")
        return value
    if field_key == "pokemon_type":
        return None if normalized == "-" else normalized
    if field_key == "rarity":
        if normalized not in CREATE_POKEMON_ALLOWED_RARITIES:
            raise ShopError("Редкость должна быть одной из: Common, Rare, Epic, Legendary.")
        return normalized
    if not normalized:
        raise ShopError("Значение не может быть пустым.")
    return normalized


def _normalize_yes_no(raw_value: str) -> bool:
    normalized = raw_value.strip().lower()
    if normalized in {"да", "yes", "y", "true", "1"}:
        return True
    if normalized in {"нет", "no", "n", "false", "0"}:
        return False
    raise ShopError("Отправьте 'да' или 'нет'.")


def _resolve_admin_upload_media(message: Message) -> tuple[str, str, str | None, str | None]:
    photo = getattr(message, "photo", None)
    if isinstance(photo, (list, tuple)) and photo:
        largest = photo[-1]
        if not isinstance(largest, PhotoSize):
            raise ShopError("Не удалось прочитать Telegram photo.")
        return largest.file_id, largest.file_unique_id, f"{largest.file_unique_id}.jpg", "image/jpeg"

    document = getattr(message, "document", None)
    if isinstance(document, Document):
        mime_type = document.mime_type or ""
        if mime_type and not mime_type.startswith("image/"):
            raise ShopError("Document должен быть изображением.")
        return document.file_id, document.file_unique_id, document.file_name, mime_type or None

    raise ShopError("Отправьте изображение как photo или document.")


async def handle_admin_media_input(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Process photo/document input for staged admin image flows."""
    if not await ensure_admin_access(update, context):
        return

    user = update.effective_user
    chat = update.effective_chat
    message = update.effective_message
    if user is None or chat is None or message is None:
        return

    pending = admin_session_store.get_pending_input(chat_id=chat.id, user_id=user.id)
    if pending is None or pending.action != ADMIN_PENDING_IMAGE_UPLOAD_FILE:
        return

    try:
        file_id, file_unique_id, file_name, content_type = _resolve_admin_upload_media(message)
    except ShopError as exc:
        await _send_chat_message(update, f"⚠️ {exc}")
        return

    admin_session_store.set_pending_input(
        action=ADMIN_PENDING_IMAGE_UPLOAD_POKEMON_ID,
        chat_id=chat.id,
        user_id=user.id,
        source_message_id=pending.source_message_id,
        source_message_thread_id=pending.source_message_thread_id,
        data={
            "telegram_file_id": file_id,
            "telegram_file_unique_id": file_unique_id,
            "file_name": file_name,
            "content_type": content_type,
        },
    )
    await _send_chat_message(update, get_image_upload_pokemon_prompt())


async def handle_admin_text_input(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Process text input for staged admin flows."""
    if not await ensure_admin_access(update, context):
        return

    user = update.effective_user
    chat = update.effective_chat
    if user is None or chat is None:
        return

    pending = admin_session_store.get_pending_input(chat_id=chat.id, user_id=user.id)
    if pending is None:
        return

    db = _db_from_context(context)
    if db is None:
        admin_session_store.clear_pending_input(chat_id=chat.id, user_id=user.id)
        await _send_chat_message(update, "⚠️ База данных недоступна.")
        return

    text_value = _extract_text_argument(update)
    if not text_value:
        return

    try:
        if pending.action in {
            ADMIN_PENDING_GRANT_POKEDOLLAR_USERNAME,
            ADMIN_PENDING_GRANT_POKECOIN_USERNAME,
            ADMIN_PENDING_GRANT_POKEMON_USERNAME,
        }:
            lookup = await db.get_user_lookup_by_username(text_value)
            if pending.action == ADMIN_PENDING_GRANT_POKEMON_USERNAME:
                next_action = ADMIN_PENDING_GRANT_POKEMON_ID
                next_text = get_grant_pokemon_prompt(lookup.username or text_value)
            else:
                next_action = (
                    ADMIN_PENDING_GRANT_POKEDOLLAR_AMOUNT
                    if pending.action == ADMIN_PENDING_GRANT_POKEDOLLAR_USERNAME
                    else ADMIN_PENDING_GRANT_POKECOIN_AMOUNT
                )
                next_text = get_grant_amount_prompt(
                    str(pending.data.get("currency_label", "валюта")),
                    lookup.username or text_value,
                )

            admin_session_store.set_pending_input(
                action=next_action,
                chat_id=chat.id,
                user_id=user.id,
                source_message_id=pending.source_message_id,
                source_message_thread_id=pending.source_message_thread_id,
                data={
                    **pending.data,
                    "target_user_id": lookup.user_id,
                    "target_telegram_id": lookup.telegram_id,
                    "target_username": lookup.username or text_value.lstrip("@"),
                },
            )
            await _send_chat_message(update, next_text)
            return

        if pending.action in {ADMIN_PENDING_GRANT_POKEDOLLAR_AMOUNT, ADMIN_PENDING_GRANT_POKECOIN_AMOUNT}:
            amount = int(text_value)
            if amount <= 0:
                raise ShopError("Сумма должна быть больше нуля.")
            admin_session_store.clear_pending_input(chat_id=chat.id, user_id=user.id)
            target_username = str(pending.data["target_username"])
            currency_label = str(pending.data["currency_label"])
            pending_action = AdminPendingAction(
                action_type=ADMIN_ACTION_GRANT_CURRENCY,
                title=f"Выдать {currency_label}",
                description=(
                    f"Пользователь <code>@{target_username}</code> получит <b>{amount}</b> {currency_label}."
                ),
                input_payload={
                    "currency_code": pending.data["currency_code"],
                    "currency_label": currency_label,
                    "amount": amount,
                },
                target_user_id=int(pending.data["target_user_id"]),
                target_telegram_id=int(pending.data["target_telegram_id"]),
                target_username=target_username,
            )
            await show_pending_action_preview(update, context, pending_action=pending_action)
            return

        if pending.action == ADMIN_PENDING_GRANT_POKEMON_ID:
            pokemon_id = int(text_value)
            pokemon_entry = await db.get_pokemon_catalog_entry_by_id(pokemon_id)
            admin_session_store.clear_pending_input(chat_id=chat.id, user_id=user.id)
            target_username = str(pending.data["target_username"])
            pending_action = AdminPendingAction(
                action_type=ADMIN_ACTION_GRANT_POKEMON,
                title="Выдать покемона",
                description=(
                    f"Пользователь <code>@{target_username}</code> получит "
                    f"<b>{pokemon_entry.name}</b> (#{pokemon_entry.pokemon_id})."
                ),
                input_payload={
                    "pokemon_id": pokemon_entry.pokemon_id,
                    "pokemon_name": pokemon_entry.name,
                },
                target_user_id=int(pending.data["target_user_id"]),
                target_telegram_id=int(pending.data["target_telegram_id"]),
                target_username=target_username,
            )
            await show_pending_action_preview(update, context, pending_action=pending_action)
            return

        if pending.action == ADMIN_PENDING_CREATE_POKEMON_FIELD:
            field_index = int(pending.data.get("field_index", 0))
            if field_index < 0 or field_index >= len(CREATE_POKEMON_FIELDS):
                raise ShopError("Состояние создания покемона повреждено. Начните заново.")
            field_key = CREATE_POKEMON_FIELDS[field_index][0]
            draft = dict(pending.data.get("draft") or {})
            draft[field_key] = _normalize_create_pokemon_field(field_key=field_key, raw_value=text_value)

            next_index = field_index + 1
            if next_index < len(CREATE_POKEMON_FIELDS):
                admin_session_store.set_pending_input(
                    action=ADMIN_PENDING_CREATE_POKEMON_FIELD,
                    chat_id=chat.id,
                    user_id=user.id,
                    source_message_id=pending.source_message_id,
                    source_message_thread_id=pending.source_message_thread_id,
                    data={
                        "field_index": next_index,
                        "draft": draft,
                    },
                )
                await _send_chat_message(update, _build_create_pokemon_prompt(next_index))
                return

            admin_session_store.clear_pending_input(chat_id=chat.id, user_id=user.id)
            pending_action = AdminPendingAction(
                action_type=ADMIN_ACTION_CREATE_POKEMON,
                title="Создать покемона",
                description=get_create_pokemon_summary_text(
                    pokemon_id=int(draft["pokemon_id"]),
                    name=str(draft["name"]),
                    pokemon_type=draft.get("pokemon_type") if isinstance(draft.get("pokemon_type"), str) else None,
                    rarity=str(draft["rarity"]),
                    base_hp=int(draft["base_hp"]),
                    base_attack=int(draft["base_attack"]),
                    base_defense=int(draft["base_defense"]),
                    base_stamina=int(draft["base_stamina"]),
                ),
                input_payload=draft,
            )
            await show_pending_action_preview(update, context, pending_action=pending_action)
            return

        if pending.action == ADMIN_PENDING_IMAGE_UPLOAD_POKEMON_ID:
            pokemon_id = int(text_value)
            pokemon_entry = await db.get_pokemon_catalog_entry_by_id(pokemon_id)
            admin_session_store.set_pending_input(
                action=ADMIN_PENDING_IMAGE_UPLOAD_SOURCE,
                chat_id=chat.id,
                user_id=user.id,
                source_message_id=pending.source_message_id,
                source_message_thread_id=pending.source_message_thread_id,
                data={
                    **pending.data,
                    "pokemon_id": pokemon_entry.pokemon_id,
                    "pokemon_name": pokemon_entry.name,
                },
            )
            await _send_chat_message(
                update,
                get_image_upload_source_prompt(pokemon_entry.name, pokemon_entry.pokemon_id),
            )
            return

        if pending.action == ADMIN_PENDING_IMAGE_UPLOAD_SOURCE:
            admin_session_store.set_pending_input(
                action=ADMIN_PENDING_IMAGE_UPLOAD_ORDER,
                chat_id=chat.id,
                user_id=user.id,
                source_message_id=pending.source_message_id,
                source_message_thread_id=pending.source_message_thread_id,
                data={
                    **pending.data,
                    "source": None if text_value.strip() == "-" else text_value.strip(),
                },
            )
            await _send_chat_message(update, get_image_upload_order_prompt())
            return

        if pending.action == ADMIN_PENDING_IMAGE_UPLOAD_ORDER:
            display_order = int(text_value)
            if display_order <= 0:
                raise ShopError("display_order должен быть больше нуля.")
            admin_session_store.set_pending_input(
                action=ADMIN_PENDING_IMAGE_UPLOAD_DEFAULT,
                chat_id=chat.id,
                user_id=user.id,
                source_message_id=pending.source_message_id,
                source_message_thread_id=pending.source_message_thread_id,
                data={
                    **pending.data,
                    "display_order": display_order,
                },
            )
            await _send_chat_message(update, get_image_upload_default_prompt())
            return

        if pending.action == ADMIN_PENDING_IMAGE_UPLOAD_DEFAULT:
            is_default = _normalize_yes_no(text_value)
            admin_session_store.clear_pending_input(chat_id=chat.id, user_id=user.id)
            payload = {
                **pending.data,
                "is_default": is_default,
            }
            pending_action = AdminPendingAction(
                action_type=ADMIN_ACTION_ATTACH_IMAGE_VARIANT,
                title="Добавить image variant",
                description=get_image_upload_summary_text(
                    pokemon_id=int(payload["pokemon_id"]),
                    pokemon_name=str(payload["pokemon_name"]),
                    source=payload.get("source") if isinstance(payload.get("source"), str) else None,
                    display_order=int(payload["display_order"]),
                    is_default=is_default,
                    file_name=payload.get("file_name") if isinstance(payload.get("file_name"), str) else None,
                ),
                input_payload=payload,
            )
            await show_pending_action_preview(update, context, pending_action=pending_action)
            return

        if pending.action == ADMIN_PENDING_IMAGE_SOURCE_EDIT_ID:
            image_credit_id = int(text_value)
            admin_session_store.set_pending_input(
                action=ADMIN_PENDING_IMAGE_SOURCE_EDIT_VALUE,
                chat_id=chat.id,
                user_id=user.id,
                source_message_id=pending.source_message_id,
                source_message_thread_id=pending.source_message_thread_id,
                data={"image_credit_id": image_credit_id},
            )
            await _send_chat_message(update, get_image_source_edit_prompt(image_credit_id))
            return

        if pending.action == ADMIN_PENDING_IMAGE_SOURCE_EDIT_VALUE:
            admin_session_store.clear_pending_input(chat_id=chat.id, user_id=user.id)
            image_credit_id = int(pending.data["image_credit_id"])
            source = None if text_value.strip() == "-" else text_value.strip()
            pending_action = AdminPendingAction(
                action_type=ADMIN_ACTION_UPDATE_IMAGE_SOURCE,
                title="Изменить source",
                description=get_image_source_update_summary_text(
                    image_credit_id=image_credit_id,
                    source=source,
                ),
                input_payload={
                    "image_credit_id": image_credit_id,
                    "source": source,
                },
            )
            await show_pending_action_preview(update, context, pending_action=pending_action)
            return

        if pending.action == ADMIN_PENDING_IMAGE_VARIANT_POKEMON_ID:
            pokemon_id = int(text_value)
            await db.get_pokemon_catalog_entry_by_id(pokemon_id)
            admin_session_store.set_pending_input(
                action=ADMIN_PENDING_IMAGE_VARIANT_CREDIT_ID,
                chat_id=chat.id,
                user_id=user.id,
                source_message_id=pending.source_message_id,
                source_message_thread_id=pending.source_message_thread_id,
                data={"pokemon_id": pokemon_id},
            )
            await _send_chat_message(update, get_variant_image_credit_id_prompt(pokemon_id))
            return

        if pending.action == ADMIN_PENDING_IMAGE_VARIANT_CREDIT_ID:
            image_credit_id = int(text_value)
            admin_session_store.set_pending_input(
                action=ADMIN_PENDING_IMAGE_VARIANT_ORDER,
                chat_id=chat.id,
                user_id=user.id,
                source_message_id=pending.source_message_id,
                source_message_thread_id=pending.source_message_thread_id,
                data={
                    **pending.data,
                    "image_credit_id": image_credit_id,
                },
            )
            await _send_chat_message(update, get_variant_order_prompt())
            return

        if pending.action == ADMIN_PENDING_IMAGE_VARIANT_ORDER:
            display_order = int(text_value)
            if display_order <= 0:
                raise ShopError("display_order должен быть больше нуля.")
            admin_session_store.set_pending_input(
                action=ADMIN_PENDING_IMAGE_VARIANT_DEFAULT,
                chat_id=chat.id,
                user_id=user.id,
                source_message_id=pending.source_message_id,
                source_message_thread_id=pending.source_message_thread_id,
                data={
                    **pending.data,
                    "display_order": display_order,
                },
            )
            await _send_chat_message(update, get_variant_default_prompt())
            return

        if pending.action == ADMIN_PENDING_IMAGE_VARIANT_DEFAULT:
            is_default = _normalize_yes_no(text_value)
            admin_session_store.clear_pending_input(chat_id=chat.id, user_id=user.id)
            payload = {
                **pending.data,
                "is_default": is_default,
            }
            pending_action = AdminPendingAction(
                action_type=ADMIN_ACTION_UPDATE_IMAGE_VARIANT,
                title="Изменить параметры варианта",
                description=get_variant_update_summary_text(
                    pokemon_id=int(payload["pokemon_id"]),
                    image_credit_id=int(payload["image_credit_id"]),
                    display_order=int(payload["display_order"]),
                    is_default=is_default,
                ),
                input_payload=payload,
            )
            await show_pending_action_preview(update, context, pending_action=pending_action)
            return
    except (ShopError, ValueError) as exc:
        await _send_chat_message(update, f"⚠️ {exc}")
        return


def register_admin_routes() -> None:
    """Register admin callback routes."""
    admin_router.register(SECTION_ROOT, _return_to_root)
    admin_router.register(SECTION_GRANTS, _show_grants_section)
    admin_router.register(SECTION_GRANT_POKEDOLLAR, _start_grant_pokedollar)
    admin_router.register(SECTION_GRANT_POKECOIN, _start_grant_pokecoin)
    admin_router.register(SECTION_GRANT_POKEMON, _start_grant_pokemon)
    admin_router.register(SECTION_POKEMON, _show_pokemon_section)
    admin_router.register(SECTION_CREATE_POKEMON, _start_create_pokemon)
    admin_router.register(SECTION_IMAGES, _show_images_section)
    admin_router.register(SECTION_IMAGE_UPLOAD_VARIANT, _start_image_upload_variant)
    admin_router.register(SECTION_IMAGE_EDIT_SOURCE, _start_image_source_edit)
    admin_router.register(SECTION_IMAGE_EDIT_VARIANT, _start_image_variant_edit)
    admin_router.register(SECTION_AUDIT, _show_audit_section)
    admin_router.register(SECTION_AUDIT_EXPORT, _export_audit_section)
    admin_router.register(SECTION_CONFIRM, _confirm_pending_action)
    admin_router.register(SECTION_CANCEL, _cancel_pending_action)
    register_pending_executor(ADMIN_ACTION_GRANT_CURRENCY, _execute_currency_grant)
    register_pending_executor(ADMIN_ACTION_GRANT_POKEMON, _execute_pokemon_grant)
    register_pending_executor(ADMIN_ACTION_CREATE_POKEMON, _execute_create_pokemon)
    register_pending_executor(ADMIN_ACTION_ATTACH_IMAGE_VARIANT, _execute_attach_image_variant)
    register_pending_executor(ADMIN_ACTION_UPDATE_IMAGE_SOURCE, _execute_update_image_source)
    register_pending_executor(ADMIN_ACTION_UPDATE_IMAGE_VARIANT, _execute_update_image_variant)


async def handle_admin_callback_query(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle callback buttons for the admin bot."""
    query = update.callback_query
    if query is None:
        return

    if not await ensure_admin_access(update, context, answer_callback=True):
        return

    if admin_session_store.is_callback_locked(query.id):
        await query.answer(ADMIN_ERROR_PROCESSING, show_alert=False)
        return
    admin_session_store.lock_callback(query.id)

    callback = parse_callback_data(query.data)
    if callback is None:
        await query.answer(ADMIN_ERROR_INVALID_CALLBACK, show_alert=True)
        return

    session = admin_session_store.get_session(callback.session_id)
    if session is None:
        await query.answer(ADMIN_ERROR_STALE_MENU, show_alert=True)
        return

    if not _session_allows_user(session, update.effective_user.id):
        await query.answer(ADMIN_ERROR_NOT_YOUR_BUTTON, show_alert=False)
        return

    actual_thread_id = getattr(query.message, "message_thread_id", None)
    if not session.matches_context(update.effective_chat.id, query.message.message_id, actual_thread_id):
        await query.answer(ADMIN_ERROR_STALE_MENU, show_alert=True)
        return

    handler = admin_router.get_handler(callback.section)
    if handler is None:
        await query.answer(ADMIN_ERROR_INVALID_CALLBACK, show_alert=True)
        return

    try:
        await handler(update, context, session)
    finally:
        try:
            await query.answer()
        except TelegramError:
            pass
