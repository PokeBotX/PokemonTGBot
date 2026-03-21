"""Group-chat pokemon encounter handlers."""

from __future__ import annotations

from pathlib import Path
from typing import Optional

import structlog
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Message, Update
from telegram.error import BadRequest, TelegramError, TimedOut
from telegram.ext import CallbackContext, ContextTypes

from bot.db.database import (
    CHAT_ENCOUNTER_TIMEOUT_SECONDS,
    CHAT_ENCOUNTER_EXPIRED_TEXT,
    CHAT_ENCOUNTER_TEXT,
    CollectionEntry,
    MASTERBALL_CODE,
    MASTERBALL_PRICE,
    REGULAR_POKEBALL_CODE,
    ULTRABALL_CODE,
    ULTRABALL_PRICE,
    ChatEncounter,
    ChatEncounterAttemptResult,
    Database,
)
from bot.handlers.sections.market import build_market_entry_payload, resolve_market_card_action
from bot.navigation.session import session_store
from bot.ui.pokemon_cards import (
    PokemonCardData,
    build_pokemon_card_keyboard,
    render_pokemon_card_caption,
    send_captioned_image,
    send_pokemon_card,
)

logger = structlog.get_logger()
FALLBACK_IMAGE_PATH = Path("image.png")
ENCOUNTER_CALLBACK_PREFIX = "enc"
ENCOUNTER_VIEW_CARD_ACTION = "card"
BALL_BUTTONS = (
    (REGULAR_POKEBALL_CODE, "⚪️ Обыч покебол"),
    (ULTRABALL_CODE, "🟡 Ультрабол"),
    (MASTERBALL_CODE, "🟣 Мастербол"),
)
BALL_LABELS = dict(BALL_BUTTONS)


def build_encounter_keyboard(encounter_id: int) -> InlineKeyboardMarkup:
    """Build the shared encounter keyboard."""
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(text, callback_data=f"{ENCOUNTER_CALLBACK_PREFIX}:{encounter_id}:{ball_code}")
                for ball_code, text in BALL_BUTTONS[:2]
            ],
            [
                InlineKeyboardButton(
                    BALL_BUTTONS[2][1],
                    callback_data=f"{ENCOUNTER_CALLBACK_PREFIX}:{encounter_id}:{BALL_BUTTONS[2][0]}",
                )
            ],
        ]
    )


def build_caught_encounter_keyboard(encounter_id: int) -> InlineKeyboardMarkup:
    """Build the resolved encounter keyboard."""
    return InlineKeyboardMarkup(
        [[InlineKeyboardButton("📘 Посмотреть карточку", callback_data=f"{ENCOUNTER_CALLBACK_PREFIX}:{encounter_id}:{ENCOUNTER_VIEW_CARD_ACTION}")]]
    )


async def maybe_spawn_encounter_from_message(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> Optional[Message]:
    """Check group chat activity and spawn an encounter if eligible."""
    if not update.effective_chat or update.effective_chat.type not in {"group", "supergroup"}:
        return None
    if not update.effective_message or not update.effective_user or getattr(update.effective_user, "is_bot", False):
        return None

    db = _get_db(context)
    if not db:
        return None

    encounter = await db.note_chat_message(
        update.effective_chat.id,
        getattr(update.effective_message, "message_thread_id", None),
    )
    if not encounter:
        return None
    return await publish_encounter_message(update, context, encounter)


async def maybe_spawn_encounter_from_find(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> Optional[Message]:
    """Try to spawn an encounter via /find in a group chat."""
    if not update.effective_chat or update.effective_chat.type not in {"group", "supergroup"}:
        if update.effective_chat:
            await update.effective_chat.send_message("Эта команда работает только в чатах.")
        return None

    db = _get_db(context)
    if not db:
        return None

    encounter = await db.trigger_find_encounter(
        update.effective_chat.id,
        getattr(update.effective_message, "message_thread_id", None),
    )
    if not encounter:
        await update.effective_chat.send_message(
            "Пока никого не видно.",
            message_thread_id=getattr(update.effective_message, "message_thread_id", None),
        )
        return None
    return await publish_encounter_message(update, context, encounter)


async def publish_encounter_message(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    encounter: ChatEncounter,
) -> Message:
    """Send the encounter message to the chat and bind it in the database."""
    db = _get_db(context)
    caption = CHAT_ENCOUNTER_TEXT
    keyboard = build_encounter_keyboard(encounter.encounter_id)
    try:
        sent_message = await send_captioned_image(
            context,
            chat_id=update.effective_chat.id,
            message_thread_id=encounter.message_thread_id,
            caption=caption,
            reply_markup=keyboard,
            image_credit_id=encounter.image_credit_id,
            image_path=FALLBACK_IMAGE_PATH,
        )
        await db.attach_chat_encounter_message(encounter.encounter_id, sent_message.message_id)
        job_queue = getattr(context, "job_queue", None)
        if job_queue:
            job_queue.run_once(
                expire_encounter_job,
                when=CHAT_ENCOUNTER_TIMEOUT_SECONDS,
                data={
                    "encounter_id": encounter.encounter_id,
                    "chat_id": encounter.chat_id,
                    "message_id": sent_message.message_id,
                    "message_thread_id": encounter.message_thread_id,
                },
                name=f"encounter-timeout-{encounter.encounter_id}",
            )
        logger.info(
            "chat_encounter_message_sent",
            chat_id=encounter.chat_id,
            encounter_id=encounter.encounter_id,
            message_id=sent_message.message_id,
        )
        return sent_message
    except Exception:
        await db.cancel_chat_encounter(encounter.encounter_id)
        raise


async def handle_encounter_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle catch attempts from any chat participant."""
    query = update.callback_query
    try:
        _, encounter_id_text, ball_code = query.data.split(":", maxsplit=2)
        encounter_id = int(encounter_id_text)
    except Exception:
        await query.answer("Некорректная кнопка.", show_alert=False)
        return

    db = _get_db(context)
    if not db:
        await query.answer("Система ловли временно недоступна.", show_alert=False)
        return

    try:
        if ball_code == ENCOUNTER_VIEW_CARD_ACTION:
            await _handle_view_card(query, context, db, encounter_id)
            return

        result = await db.attempt_chat_encounter(
            chat_id=query.message.chat.id,
            encounter_message_id=query.message.message_id,
            telegram_id=update.effective_user.id,
            username=getattr(update.effective_user, "username", None),
            catcher_label=_display_user(update),
            ball_code=ball_code,
        )
        await _resolve_attempt_result(query, context, result, _display_user(update))
    except BadRequest as exc:
        logger.warning("chat_encounter_callback_error", error="bad_request", error_message=str(exc))
    except TelegramError as exc:
        logger.error("chat_encounter_callback_error", error="telegram_api", error_message=str(exc))
    except Exception as exc:
        logger.error("chat_encounter_callback_error", error="unexpected", error_message=str(exc))
        await query.answer("Не удалось обработать попытку.", show_alert=False)


async def expire_encounter_job(context: CallbackContext) -> None:
    """Expire a pending encounter after timeout."""
    data = context.job.data or {}
    encounter_id = data.get("encounter_id")
    chat_id = data.get("chat_id")
    message_id = data.get("message_id")
    message_thread_id = data.get("message_thread_id")
    db = _get_db(context)
    if not db or encounter_id is None or chat_id is None or message_id is None:
        return

    encounter = await db.expire_chat_encounter(int(encounter_id))
    if not encounter:
        return

    await _edit_encounter_message_by_ids(
        context,
        chat_id=int(chat_id),
        message_id=int(message_id),
        message_thread_id=message_thread_id,
        text=CHAT_ENCOUNTER_EXPIRED_TEXT,
    )
    logger.info("chat_encounter_expired", chat_id=chat_id, encounter_id=encounter_id, message_id=message_id)


async def _resolve_attempt_result(
    query,
    context: ContextTypes.DEFAULT_TYPE,
    result: ChatEncounterAttemptResult,
    user_label: str,
) -> None:
    if result.status == "missing":
        await query.answer("Покемона уже нет.", show_alert=False)
        return
    if result.status == "stale":
        await query.answer("Это уже старый encounter.", show_alert=False)
        return
    if result.status == "expired":
        await _edit_query_encounter_message(query, CHAT_ENCOUNTER_EXPIRED_TEXT)
        await query.answer("Покемон убежал.", show_alert=False)
        return
    if result.status == "already_attempted":
        await query.answer("Ты уже пытался поймать этого покемона.", show_alert=False)
        return
    if result.status == "no_ball":
        await query.answer("У тебя нет такого покебола.", show_alert=False)
        return
    if result.status == "failed" and result.encounter:
        await _send_failed_attempt_message(query, result.encounter, user_label, result.ball_code)
        await query.answer("Не получилось поймать.", show_alert=False)
        return
    if result.status == "caught" and result.encounter:
        await _send_caught_message(query, result.encounter, result.catcher_label)
        await _edit_query_encounter_message(
            query,
            f"✨ <b>{result.encounter.name}</b> пойман!\nПоймал: <b>{result.catcher_label}</b>",
            reply_markup=build_caught_encounter_keyboard(result.encounter.encounter_id),
        )
        await query.answer("Пойман!", show_alert=False)
        return
    await query.answer("Не удалось обработать попытку.", show_alert=False)


async def _edit_query_encounter_message(
    query,
    text: str,
    reply_markup: Optional[InlineKeyboardMarkup] = None,
) -> None:
    message = query.message
    if getattr(message, "photo", None):
        await query.edit_message_caption(caption=text, parse_mode="HTML", reply_markup=reply_markup)
    else:
        await query.edit_message_text(text=text, parse_mode="HTML", reply_markup=reply_markup)


async def _edit_encounter_message_by_ids(
    context: ContextTypes.DEFAULT_TYPE,
    chat_id: int,
    message_id: int,
    message_thread_id: Optional[int],
    text: str,
) -> None:
    try:
        await context.bot.edit_message_caption(
            chat_id=chat_id,
            message_id=message_id,
            caption=text,
            parse_mode="HTML",
            reply_markup=None,
        )
        return
    except TimedOut as exc:
        logger.warning(
            "chat_encounter_edit_timeout",
            chat_id=chat_id,
            message_id=message_id,
            operation="edit_caption",
            error_message=str(exc),
        )
        return
    except BadRequest as exc:
        error_text = str(exc).lower()
        if "message is not modified" in error_text:
            return
        if "there is no caption" not in error_text:
            raise
    except TelegramError:
        return

    try:
        await context.bot.edit_message_text(
            chat_id=chat_id,
            message_id=message_id,
            text=text,
            parse_mode="HTML",
            reply_markup=None,
        )
    except BadRequest as exc:
        error_text = str(exc).lower()
        if "message is not modified" in error_text or "there is no text in the message to edit" in error_text:
            return
        raise
    except TelegramError as exc:
        logger.warning(
            "chat_encounter_edit_failed",
            chat_id=chat_id,
            message_id=message_id,
            operation="edit_text",
            error_message=str(exc),
        )


async def _send_failed_attempt_message(
    query,
    encounter: ChatEncounter,
    user_label: str,
    ball_code: Optional[str],
) -> None:
    ball_label = BALL_LABELS.get(ball_code or "", "покебол")
    await query.message.reply_text(
        f"❌ {user_label} бросил {ball_label}, но поймать покемона не удалось.",
        parse_mode="HTML",
        message_thread_id=getattr(query.message, "message_thread_id", None),
    )


async def _send_caught_message(
    query,
    encounter: ChatEncounter,
    catcher_label: Optional[str],
) -> None:
    await query.message.reply_text(
        f"✨ <b>{catcher_label or 'Тренер'}</b> поймал <b>{encounter.name}</b>!",
        parse_mode="HTML",
        message_thread_id=getattr(query.message, "message_thread_id", None),
    )


async def _handle_view_card(
    query,
    context: ContextTypes.DEFAULT_TYPE,
    db: Database,
    encounter_id: int,
) -> None:
    encounter = await db.get_chat_encounter(encounter_id)
    if not encounter or encounter.status != "caught" or encounter.caught_user_pokemon_id is None:
        await query.answer("Карточка пока недоступна.", show_alert=False)
        return

    entry = await db.get_user_pokemon_entry(encounter.caught_user_pokemon_id)
    if not entry:
        await query.answer("Карточка не найдена.", show_alert=False)
        return

    await _send_encounter_card(
        context,
        query.message,
        entry,
        viewer_user_id=query.from_user.id if getattr(query, "from_user", None) else None,
        owner_user_id=encounter.caught_by_user_id,
    )
    await query.answer("Карточка открыта.", show_alert=False)


async def _send_encounter_card(
    context: ContextTypes.DEFAULT_TYPE,
    source_message: Message,
    entry: CollectionEntry,
    viewer_user_id: Optional[int] = None,
    owner_user_id: Optional[int] = None,
) -> Message:
    message = await send_pokemon_card(
        context,
        chat_id=source_message.chat.id,
        message_thread_id=getattr(source_message, "message_thread_id", None),
        card=PokemonCardData(
            pokemon_id=entry.pokemon_id,
            name=entry.name,
            rarity=entry.rarity,
            pokemon_type=entry.pokemon_type,
            base_hp=entry.base_hp,
            base_attack=entry.base_attack,
            base_defense=entry.base_defense,
            base_stamina=entry.base_stamina,
            user_pokemon_id=entry.sample_user_pokemon_id,
            image_credit_id=entry.image_credit_id,
        ),
    )
    if viewer_user_id is not None:
        viewer_is_owner = owner_user_id is not None and viewer_user_id == owner_user_id
        session_id = session_store.create_session(
            chat_id=source_message.chat.id,
            message_id=message.message_id,
            user_id=viewer_user_id,
            message_thread_id=getattr(source_message, "message_thread_id", None),
            data=build_market_entry_payload(
                action=resolve_market_card_action(viewer_is_owner),
                pokemon_id=entry.pokemon_id,
                pokemon_name=entry.name,
                user_pokemon_id=entry.sample_user_pokemon_id if viewer_is_owner else None,
            )
            | (
                {
                    "release_user_pokemon_id": entry.sample_user_pokemon_id,
                    "release_pokemon_name": entry.name,
                    "release_rarity": entry.rarity,
                }
                if viewer_is_owner
                else {}
            ),
        )
        await message.edit_reply_markup(
            reply_markup=build_pokemon_card_keyboard(
                session_id,
                include_market_button=True,
                include_release_button=viewer_is_owner,
                include_extra_button=viewer_is_owner,
            )
        )
    return message


def _render_encounter_card_caption(entry: CollectionEntry) -> str:
    return render_pokemon_card_caption(
        PokemonCardData(
            pokemon_id=entry.pokemon_id,
            name=entry.name,
            rarity=entry.rarity,
            pokemon_type=entry.pokemon_type,
            base_hp=entry.base_hp,
            base_attack=entry.base_attack,
            base_defense=entry.base_defense,
            base_stamina=entry.base_stamina,
            user_pokemon_id=entry.sample_user_pokemon_id,
            image_credit_id=entry.image_credit_id,
        )
    )


def _display_user(update: Optional[Update]) -> str:
    if update and update.effective_user:
        username = getattr(update.effective_user, "username", None)
        if username:
            return f"@{username}"
        first_name = getattr(update.effective_user, "first_name", None)
        if first_name:
            return first_name
    return "тренер"


def _get_db(context: ContextTypes.DEFAULT_TYPE) -> Optional[Database]:
    application = getattr(context, "application", None)
    if not application or not hasattr(application, "bot_data"):
        return None
    bot_data = getattr(application, "bot_data", None)
    if not isinstance(bot_data, dict):
        return None
    db = bot_data.get("db")
    if not db or not hasattr(db, "note_chat_message"):
        return None
    return db
