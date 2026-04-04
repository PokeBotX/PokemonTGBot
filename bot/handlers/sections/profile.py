"""Profile section handler."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Optional

import structlog
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Message, Update
from telegram.error import BadRequest, TelegramError
from telegram.ext import ContextTypes

from bot.db.database import Database, PokemonSearchEntry, ProfileCoverCandidate, ProfileReferral, ProfileSummary, ShopError
from bot.handlers.sections.market import build_market_entry_payload, resolve_market_card_action
from bot.navigation.context import extract_context
from bot.navigation.router import NavigationRouter, parse_callback_data
from bot.navigation.session import MenuSession, PendingInput, session_store
from bot.ui.html import display_name, escape_html
from bot.ui.menu import build_back_button
from bot.ui.pokemon_cards import send_captioned_image

logger = structlog.get_logger()

PROFILE_VIEW_ROOT = "root"
PROFILE_VIEW_SETTINGS = "settings"
PROFILE_VIEW_LANGUAGE = "language"
PROFILE_VIEW_REFERRAL = "referral"
PROFILE_VIEW_TEAM = "team"
PROFILE_VIEW_VIP = "vip"

PROFILE_ROUTE_SECTIONS = [
    "profile",
    "prs",
    "prl",
    "prlr",
    "prle",
    "prn",
    "prc",
    "prcd1",
    "prcd2",
    "prcd3",
    "prcd4",
    "prcd5",
    "psc1",
    "psc2",
    "psc3",
    "psc4",
    "psc5",
    "prr",
    "prt",
    "prv",
]

PROFILE_PENDING_ACTION_COVER = "profile_cover"
PROFILE_SEARCH_RESULT_LIMIT = 5
FALLBACK_IMAGE_PATH = Path("image.png")
DEFAULT_PROFILE_IMAGE_PATH = Path("image_profile.png")
SUPPORTED_IMAGE_SUFFIXES = (".png", ".jpg", ".jpeg", ".webp")


def register_profile_routes(router: NavigationRouter) -> None:
    """Register all profile-related callback sections."""
    for section in PROFILE_ROUTE_SECTIONS:
        router.register(section, profile_handler)


async def show_profile_screen(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    *,
    summary: Optional[ProfileSummary] = None,
    user_label: Optional[str] = None,
    allow_manage: bool = True,
) -> Message:
    """Send a fresh profile message for direct `/profile` command usage."""
    msg_context = extract_context(update)
    db = _get_db(context)

    if not db:
        sent_message = await update.effective_chat.send_message(
            text="👤 <b>Профиль временно недоступен</b>\n\nБаза данных не подключена.",
            parse_mode="HTML",
            message_thread_id=msg_context.message_thread_id,
        )
        session_id = session_store.create_session(
            chat_id=msg_context.chat_id,
            message_id=sent_message.message_id,
            user_id=msg_context.user_id,
            message_thread_id=msg_context.message_thread_id,
        )
        await sent_message.edit_reply_markup(reply_markup=build_back_button(session_id))
        return sent_message

    if summary is None:
        summary = await db.get_profile_summary(msg_context.user_id, update.effective_user.username if update.effective_user else None)
    if user_label is None:
        user_label = _display_self_profile_owner(update, summary) if summary.telegram_id == msg_context.user_id else _display_profile_owner(summary)
    logger.info(
        "profile_render_start",
        user_id=msg_context.user_id,
        chat_id=msg_context.chat_id,
        source="command",
        target_telegram_id=summary.telegram_id,
        target_label=user_label,
    )
    sent_message = await _send_profile_message(
        update,
        context,
        chat_id=msg_context.chat_id,
        message_thread_id=msg_context.message_thread_id,
        text=_render_profile_text(summary, user_label),
        summary=summary,
    )
    session_id = session_store.create_session(
        chat_id=msg_context.chat_id,
        message_id=sent_message.message_id,
        user_id=msg_context.user_id,
        message_thread_id=msg_context.message_thread_id,
    )
    await sent_message.edit_reply_markup(
        reply_markup=_build_profile_keyboard(session_id) if allow_manage else build_back_button(session_id)
    )
    logger.info("profile_command_sent", session_id=session_id, user_id=msg_context.user_id)
    return sent_message


async def handle_profile_text_input(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle pending profile text input such as cover search."""
    if not update.effective_chat or not update.effective_user or not update.effective_message:
        return

    pending = session_store.get_pending_input(
        chat_id=update.effective_chat.id,
        user_id=update.effective_user.id,
    )
    if not pending:
        return

    db = _get_db(context)
    if not db:
        session_store.clear_pending_input(chat_id=update.effective_chat.id, user_id=update.effective_user.id)
        return

    if pending.action == PROFILE_PENDING_ACTION_COVER:
        await _handle_profile_cover_search_input(update, context, db, pending)
        return


async def profile_handler(update: Update, context: ContextTypes.DEFAULT_TYPE, session: MenuSession) -> None:
    """Handle profile root and nested profile screens."""
    query = update.callback_query
    callback_data = parse_callback_data(query.data)
    section = callback_data.section if callback_data else "profile"

    try:
        logger.info("profile_handler_start", section=section, user_id=session.user_id, session_id=session.session_id)
        db = _get_db(context)
        if not db:
            await _edit_profile_message(
                query,
                session,
                "👤 <b>Профиль временно недоступен</b>\n\nБаза данных не подключена.",
                build_back_button(_create_session(session)),
            )
            return

        username = update.effective_user.username if update.effective_user else None

        if section == "profile":
            session_store.clear_pending_input(chat_id=session.chat_id, user_id=session.user_id)
            summary = await db.get_profile_summary(session.user_id, username)
            user_label = _display_self_profile_owner(update, summary)
            logger.info("profile_render_start", section=section, user_id=session.user_id, chat_id=session.chat_id, source="callback")
            if _message_supports_caption(getattr(query, "message", None)):
                await _edit_profile_message(
                    query,
                    session,
                    _render_profile_text(summary, user_label),
                    _build_profile_keyboard(_create_session(session)),
                )
            else:
                await show_profile_screen(update, context, summary=summary, user_label=user_label, allow_manage=True)
            return

        if section == "prs":
            session_store.clear_pending_input(chat_id=session.chat_id, user_id=session.user_id)
            summary = await db.get_profile_summary(session.user_id, username)
            user_label = _display_self_profile_owner(update, summary)
            await _edit_profile_message(
                query,
                session,
                _render_settings_text(summary, user_label),
                _build_settings_keyboard(_create_session(session)),
            )
            return

        if section == "prl":
            session_store.clear_pending_input(chat_id=session.chat_id, user_id=session.user_id)
            summary = await db.get_profile_summary(session.user_id, username)
            user_label = _display_self_profile_owner(update, summary)
            await _edit_profile_message(
                query,
                session,
                _render_language_text(summary, user_label),
                _build_language_keyboard(_create_session(session), summary.language),
            )
            return

        if section in {"prlr", "prle"}:
            session_store.clear_pending_input(chat_id=session.chat_id, user_id=session.user_id)
            language = "ru" if section == "prlr" else "en"
            saved_language = await db.update_profile_language(session.user_id, username, language)
            summary = await db.get_profile_summary(session.user_id, username)
            user_label = _display_self_profile_owner(update, summary)
            await _edit_profile_message(
                query,
                session,
                _render_settings_text(
                    summary,
                    user_label,
                    status_text=f"🌐 Язык сохранён: <b>{_language_label(saved_language)}</b>\n\nПока это меняется только в базе данных.",
                ),
                _build_settings_keyboard(_create_session(session)),
            )
            return

        if section == "prr":
            session_store.clear_pending_input(chat_id=session.chat_id, user_id=session.user_id)
            referral = await db.get_profile_referral(session.user_id, username, _extract_bot_username(update))
            summary = await db.get_profile_summary(session.user_id, username)
            user_label = _display_self_profile_owner(update, summary)
            await _edit_profile_message(
                query,
                session,
                _render_referral_text(user_label, referral),
                _build_nested_profile_keyboard(_create_session(session), back_section="profile"),
            )
            return

        if section == "prt":
            session_store.clear_pending_input(chat_id=session.chat_id, user_id=session.user_id)
            await _edit_profile_message(
                query,
                session,
                "🛡 <b>Боевая команда</b>\n\nЭтот раздел пока в разработке.",
                _build_nested_profile_keyboard(_create_session(session), back_section="profile"),
            )
            return

        if section == "prv":
            session_store.clear_pending_input(chat_id=session.chat_id, user_id=session.user_id)
            await _edit_profile_message(
                query,
                session,
                "⭐ <b>VIP</b>\n\nЭтот раздел пока в разработке.",
                _build_nested_profile_keyboard(_create_session(session), back_section="profile"),
            )
            return

        if section == "prn":
            summary = await db.get_profile_summary(session.user_id, username)
            user_label = _display_self_profile_owner(update, summary)
            await _edit_profile_message(
                query,
                session,
                _render_settings_text(
                    summary,
                    user_label,
                    status_text=(
                        "✏️ <b>Смена ника</b>\n\n"
                        "Используйте команду:\n"
                        "<code>/changename Артём</code>\n\n"
                        "Подставьте туда ваш новый ник."
                    ),
                ),
                _build_nickname_prompt_keyboard(_create_session(session)),
            )
            return

        if section == "prc":
            summary = await db.get_profile_summary(session.user_id, username)
            user_label = _display_self_profile_owner(update, summary)
            session_store.set_pending_input(
                action=PROFILE_PENDING_ACTION_COVER,
                chat_id=session.chat_id,
                user_id=session.user_id,
                source_message_id=session.message_id,
                source_message_thread_id=session.message_thread_id,
            )
            await _edit_profile_message(
                query,
                session,
                _render_settings_text(
                    summary,
                    user_label,
                    status_text=(
                        "🖼 <b>Обложка</b>\n\n"
                        "Отправьте следующим сообщением имя покемона.\n"
                        "Я поищу только среди ваших покемонов с доступной картинкой."
                    ),
                ),
                _build_cover_prompt_keyboard(_create_session(session)),
            )
            logger.info("profile_cover_prompt_opened", user_id=session.user_id, chat_id=session.chat_id)
            return

        if section.startswith("prcd"):
            session_store.clear_pending_input(chat_id=session.chat_id, user_id=session.user_id)
            index = int(section.removeprefix("prcd")) - 1
            candidate_payloads = session.data.get("cover_candidates")
            if not candidate_payloads or not isinstance(candidate_payloads, list) or index >= len(candidate_payloads):
                raise ShopError("Список вариантов обложки устарел.")
            candidate = ProfileCoverCandidate.from_payload(candidate_payloads[index])
            await db.update_profile_cover(
                session.user_id,
                username,
                image_credit_id=candidate.image_credit_id,
            )
            logger.info(
                "profile_cover_selected",
                user_id=session.user_id,
                chat_id=session.chat_id,
                pokemon_id=candidate.pokemon_id,
                image_credit_id=candidate.image_credit_id,
            )
            summary = await db.get_profile_summary(session.user_id, username)
            user_label = _display_self_profile_owner(update, summary)
            await _edit_profile_message(
                query,
                session,
                _render_settings_text(
                    summary,
                    user_label,
                    status_text=f"🖼 Обложка сохранена: <b>{candidate.name}</b>",
                ),
                _build_settings_keyboard(_create_session(session)),
            )
            return

        if section.startswith("psc"):
            index = int(section.removeprefix("psc")) - 1
            result_payloads = session.data.get("search_results")
            if not result_payloads or not isinstance(result_payloads, list) or index >= len(result_payloads):
                raise ShopError("Список результатов поиска устарел.")
            entry = PokemonSearchEntry.from_payload(result_payloads[index])
            await _send_pokemon_search_card(context, session, entry)
            return

        summary = await db.get_profile_summary(session.user_id, username)
        user_label = _display_self_profile_owner(update, summary)
        await _edit_profile_message(
            query,
            session,
            _render_profile_text(summary, user_label, "⚠️ Неизвестное действие профиля."),
            _build_profile_keyboard(_create_session(session)),
        )

    except ShopError as exc:
        logger.warning("profile_handler_error", section=section, error="profile", error_message=str(exc), user_id=session.user_id)
        try:
            await query.answer(str(exc), show_alert=False)
        except TelegramError:
            pass
    except BadRequest as exc:
        logger.warning(
            "profile_handler_error",
            section=section,
            error="bad_request",
            error_message=str(exc),
            user_id=session.user_id,
            chat_id=session.chat_id,
        )
    except TelegramError as exc:
        logger.error(
            "profile_handler_error",
            section=section,
            error="telegram_api",
            error_message=str(exc),
            user_id=session.user_id,
        )
    except Exception as exc:
        logger.error(
            "profile_handler_error",
            section=section,
            error="unexpected",
            error_message=str(exc),
            user_id=session.user_id,
        )


def _render_profile_text(summary: ProfileSummary, user_label: str, status_text: Optional[str] = None) -> str:
    rarity_lines = [
        f"{_rarity_emoji(progress.rarity)} {escape_html(progress.rarity)}: <b>{progress.owned_unique}</b> из <b>{progress.total_catalog}</b> ({progress.percent}%)"
        for progress in summary.rarity_progress
        if progress.total_catalog > 0
    ]

    lines = [
        f"👤 <b>{escape_html(user_label)}</b>, ваш профиль:",
        f"🆔 <code>{summary.telegram_id}</code>",
        "",
        f"📦 У вас <b>{summary.total_unique_owned}</b> уникальных покемонов из <b>{summary.total_catalog}</b> ({summary.total_unique_percent}%)",
        *rarity_lines,
        "",
        f"⏳ Возраст аккаунта: <b>{_humanize_account_age(summary.created_at)}</b>",
    ]
    if status_text:
        lines.extend(["", status_text])
    return "\n".join(lines)


def _render_settings_text(summary: ProfileSummary, user_label: str, status_text: Optional[str] = None) -> str:
    lines = [
        f"⚙️ <b>{escape_html(user_label)}</b>, настройки профиля:",
        "",
        f"🌐 Язык в БД: <b>{_language_label(summary.language)}</b>",
        f"🖼 Обложка: <b>{'кастомная' if summary.profile_pic_credit_id else 'image_profile.png'}</b>",
        f"✏️ Ник в профиле: <b>{escape_html(summary.nickname or user_label)}</b>",
    ]
    if status_text:
        lines.extend(["", status_text])
    return "\n".join(lines)


def _render_language_text(summary: ProfileSummary, user_label: str) -> str:
    return "\n".join(
        [
            f"🌐 <b>{escape_html(user_label)}</b>, выберите язык:",
            "",
            f"Сейчас в БД сохранено: <b>{_language_label(summary.language)}</b>",
            "",
            "Пока это меняет только сохранённое значение, без полного перевода интерфейса.",
        ]
    )


def _render_referral_text(user_label: str, referral: ProfileReferral) -> str:
    return "\n".join(
        [
            f"🔗 <b>{escape_html(user_label)}</b>, ваша реферальная ссылка:",
            "",
            f"<code>{escape_html(referral.referral_link)}</code>",
        ]
    )


def _render_cover_candidates_text(user_label: str, candidates: list[ProfileCoverCandidate]) -> str:
    lines = [
        f"🖼 <b>{escape_html(user_label)}</b>, варианты обложки:",
        "",
    ]
    for index, candidate in enumerate(candidates, start=1):
        lines.append(
            f"{index}. <b>{escape_html(candidate.name)}</b> | {escape_html(candidate.rarity)} | id: <code>{candidate.pokemon_id}</code>"
        )
    lines.extend(["", "Выберите подходящий вариант:"])
    return "\n".join(lines)


def _render_search_results_text(user_label: str, results: list[PokemonSearchEntry]) -> str:
    lines = [
        f"🔎 <b>{escape_html(user_label)}</b>, найдено несколько вариантов:",
        "",
    ]
    for index, entry in enumerate(results, start=1):
        lines.append(
            f"{index}. <b>{escape_html(entry.name)}</b> | {escape_html(entry.rarity)} | id: <code>{entry.pokemon_id}</code>"
        )
    lines.extend(["", "Выберите покемона из списка:"])
    return "\n".join(lines)


def _build_profile_keyboard(session_id: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("⚙️ Настройки", callback_data=f"menu:prs:{session_id}"),
                InlineKeyboardButton("🔗 Рефка", callback_data=f"menu:prr:{session_id}"),
            ],
            build_back_button(session_id).inline_keyboard[0],
        ]
    )


def _build_settings_keyboard(session_id: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("🌐 Язык", callback_data=f"menu:prl:{session_id}"),
            ],
            [
                InlineKeyboardButton("✏️ Смена ника", callback_data=f"menu:prn:{session_id}"),
            ],
            [
                InlineKeyboardButton("🔙 Назад в профиль", callback_data=f"menu:profile:{session_id}"),
            ],
        ]
    )


def _build_language_keyboard(session_id: str, current_language: str) -> InlineKeyboardMarkup:
    ru_label = "✅ Русский" if current_language == "ru" else "Русский"
    en_label = "✅ English" if current_language == "en" else "English"
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(ru_label, callback_data=f"menu:prlr:{session_id}"),
                InlineKeyboardButton(en_label, callback_data=f"menu:prle:{session_id}"),
            ],
            [
                InlineKeyboardButton("🔙 Назад в настройки", callback_data=f"menu:prs:{session_id}"),
            ],
        ]
    )


def _build_nickname_prompt_keyboard(session_id: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("🔙 Назад в настройки", callback_data=f"menu:prs:{session_id}")],
        ]
    )


def _build_cover_prompt_keyboard(session_id: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("🔙 Назад в настройки", callback_data=f"menu:prs:{session_id}")],
        ]
    )


def _build_cover_candidates_keyboard(session_id: str, candidates: list[ProfileCoverCandidate]) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []
    for index, candidate in enumerate(candidates[:5], start=1):
        rows.append(
            [
                InlineKeyboardButton(
                    f"🖼 {candidate.name}",
                    callback_data=f"menu:prcd{index}:{session_id}",
                )
            ]
        )
    rows.append([InlineKeyboardButton("🔙 Назад в настройки", callback_data=f"menu:prs:{session_id}")])
    return InlineKeyboardMarkup(rows)


def _build_search_results_keyboard(session_id: str, results: list[PokemonSearchEntry]) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []
    for index, entry in enumerate(results[:PROFILE_SEARCH_RESULT_LIMIT], start=1):
        rows.append(
            [
                InlineKeyboardButton(
                    f"🔎 {entry.pokemon_id}",
                    callback_data=f"menu:psc{index}:{session_id}",
                )
            ]
        )
    rows.append([InlineKeyboardButton("🔙 Назад в меню", callback_data=f"menu:back:{session_id}")])
    return InlineKeyboardMarkup(rows)


def _build_nested_profile_keyboard(session_id: str, *, back_section: str) -> InlineKeyboardMarkup:
    back_label = "🔙 Назад в профиль" if back_section == "profile" else "🔙 Назад"
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton(back_label, callback_data=f"menu:{back_section}:{session_id}")],
        ]
    )


async def _send_pokemon_search_card(
    context: ContextTypes.DEFAULT_TYPE,
    session: MenuSession,
    entry: PokemonSearchEntry,
    user_label: Optional[str] = None,
) -> Message:
    # Keep profile search card local for now until profile UI is revisited.
    caption = _render_pokemon_search_card_caption(entry, user_label)
    message = await send_captioned_image(
        context,
        chat_id=session.chat_id,
        message_thread_id=session.message_thread_id,
        caption=caption,
        image_credit_id=entry.image_credit_id,
        image_path=FALLBACK_IMAGE_PATH,
    )

    detail_session_id = session_store.create_session(
        chat_id=session.chat_id,
        message_id=message.message_id,
        user_id=session.user_id,
        message_thread_id=session.message_thread_id,
        data=build_market_entry_payload(
            action=resolve_market_card_action(False),
            pokemon_id=entry.pokemon_id,
            pokemon_name=entry.name,
        ),
    )
    await message.edit_reply_markup(
        reply_markup=InlineKeyboardMarkup(
            [[InlineKeyboardButton("🏪 Рынок", callback_data=f"menu:mce:{detail_session_id}")]]
        )
    )
    return message


async def _send_profile_message(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    *,
    chat_id: int,
    message_thread_id: Optional[int],
    text: str,
    summary: ProfileSummary,
) -> Message:
    image_path = _resolve_profile_image_path(summary)
    if image_path.exists():
        with image_path.open("rb") as image_file:
            return await context.bot.send_photo(
                chat_id=chat_id,
                message_thread_id=message_thread_id,
                photo=image_file,
                caption=text,
                parse_mode="HTML",
            )
    return await context.bot.send_message(
        chat_id=chat_id,
        message_thread_id=message_thread_id,
        text=text,
        parse_mode="HTML",
    )


def _render_pokemon_search_card_caption(entry: PokemonSearchEntry, user_label: Optional[str] = None) -> str:
    return "\n".join(
        line
        for line in [
            f"📘 <b>{escape_html(entry.name)}</b>",
            (f"Тренер: <b>{escape_html(user_label)}</b>" if user_label else ""),
            f"Редкость: <b>{escape_html(entry.rarity)}</b>",
            f"Тип: <b>{escape_html(entry.pokemon_type or 'unknown')}</b>",
            f"HP: <b>{entry.base_hp}</b>",
            f"ATK: <b>{entry.base_attack}</b>",
            f"DEF: <b>{entry.base_defense}</b>",
            f"SPD: <b>{entry.base_stamina}</b>",
            f"ID покемона: <b>{entry.pokemon_id}</b>",
        ]
        if line
    )


async def _edit_profile_message(
    query,
    session: MenuSession,
    text: str,
    reply_markup: InlineKeyboardMarkup,
) -> None:
    if _message_supports_caption(getattr(query, "message", None)):
        await query.edit_message_caption(
            caption=text,
            parse_mode="HTML",
            reply_markup=reply_markup,
        )
    else:
        await query.edit_message_text(
            text=text,
            parse_mode="HTML",
            reply_markup=reply_markup,
        )
    logger.info("profile_screen_edited", session_id=session.session_id, chat_id=session.chat_id, message_id=session.message_id)


async def _edit_profile_message_by_ids(
    context: ContextTypes.DEFAULT_TYPE,
    pending: PendingInput,
    text: str,
    reply_markup: InlineKeyboardMarkup,
) -> None:
    try:
        await context.bot.edit_message_caption(
            chat_id=pending.chat_id,
            message_id=int(pending.source_message_id),
            caption=text,
            parse_mode="HTML",
            reply_markup=reply_markup,
        )
    except BadRequest as exc:
        if "There is no caption in the message to edit" not in str(exc):
            raise
        await context.bot.edit_message_text(
            chat_id=pending.chat_id,
            message_id=int(pending.source_message_id),
            text=text,
            parse_mode="HTML",
            reply_markup=reply_markup,
        )
    logger.info(
        "profile_screen_edited_by_ids",
        chat_id=pending.chat_id,
        message_id=pending.source_message_id,
        action=pending.action,
    )


async def _handle_profile_cover_search_input(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    db: Database,
    pending: PendingInput,
) -> None:
    query_text = (update.effective_message.text or "").strip()
    logger.info("profile_cover_search_received", user_id=update.effective_user.id, chat_id=update.effective_chat.id, query=query_text)
    if not query_text:
        await update.effective_chat.send_message(
            "🖼 Отправь имя покемона одним обычным сообщением.",
            message_thread_id=getattr(update.effective_message, "message_thread_id", None),
        )
        return

    candidates = await db.search_profile_cover_candidates(
        update.effective_user.id,
        update.effective_user.username,
        query_text,
    )
    if not candidates:
        await update.effective_chat.send_message(
            "⚠️ Я не нашёл подходящих покемонов среди ваших с доступной картинкой.",
            message_thread_id=getattr(update.effective_message, "message_thread_id", None),
        )
        return

    if len(candidates) == 1:
        candidate = candidates[0]
        await db.update_profile_cover(
            update.effective_user.id,
            update.effective_user.username,
            image_credit_id=candidate.image_credit_id,
        )
        logger.info(
            "profile_cover_selected",
            user_id=update.effective_user.id,
            chat_id=update.effective_chat.id,
            pokemon_id=candidate.pokemon_id,
            image_credit_id=candidate.image_credit_id,
        )
        session_store.clear_pending_input(chat_id=update.effective_chat.id, user_id=update.effective_user.id)
        summary = await db.get_profile_summary(update.effective_user.id, update.effective_user.username)
        if pending.source_message_id is not None:
            await _edit_profile_message_by_ids(
                context,
                pending,
                _render_settings_text(
                    summary,
                    _display_user(update),
                    status_text=f"🖼 Обложка сохранена: <b>{candidate.name}</b>",
                ),
                _build_settings_keyboard(
                    session_store.create_session(
                        chat_id=pending.chat_id,
                        message_id=pending.source_message_id,
                        user_id=pending.user_id,
                        message_thread_id=pending.source_message_thread_id,
                    )
                ),
            )
        await update.effective_chat.send_message(
            f"🖼 Обложка сохранена: <b>{candidate.name}</b>",
            parse_mode="HTML",
            message_thread_id=getattr(update.effective_message, "message_thread_id", None),
        )
        return

    session_store.clear_pending_input(chat_id=update.effective_chat.id, user_id=update.effective_user.id)
    if pending.source_message_id is None:
        return
    result_session_id = session_store.create_session(
        chat_id=pending.chat_id,
        message_id=pending.source_message_id,
        user_id=pending.user_id,
        message_thread_id=pending.source_message_thread_id,
        data={"cover_candidates": [candidate.as_session_payload() for candidate in candidates]},
    )
    await _edit_profile_message_by_ids(
        context,
        pending,
        _render_cover_candidates_text(_display_user(update), candidates),
        _build_cover_candidates_keyboard(result_session_id, candidates),
    )


async def handle_pokemon_search_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /search command for pokemon-name lookup."""
    if not update.effective_chat or not update.effective_user or not update.effective_message:
        return

    db = _get_db(context)
    if not db:
        await update.effective_chat.send_message(
            "🔎 Поиск временно недоступен.",
            message_thread_id=getattr(update.effective_message, "message_thread_id", None),
        )
        return

    query_text = _extract_command_argument(update.effective_message.text or "")
    if not query_text:
        await update.effective_chat.send_message(
            "🔎 Использование: <code>/search имя_покемона</code> или <code>/search id</code>",
            parse_mode="HTML",
            message_thread_id=getattr(update.effective_message, "message_thread_id", None),
        )
        return

    numeric_query = query_text.strip()
    if numeric_query.isdigit():
        entry = await db.get_pokemon_catalog_entry(int(numeric_query))
        if entry is not None:
            await _send_pokemon_search_card(
                context,
                MenuSession(
                    session_id="search",
                    chat_id=update.effective_chat.id,
                    message_id=update.effective_message.message_id,
                    user_id=update.effective_user.id,
                    message_thread_id=getattr(update.effective_message, "message_thread_id", None),
                ),
                entry,
            )
            return

    results = await db.search_pokemon_catalog(query_text, limit=PROFILE_SEARCH_RESULT_LIMIT)
    if not results:
        await update.effective_chat.send_message(
            "⚠️ Ничего не найдено.",
            message_thread_id=getattr(update.effective_message, "message_thread_id", None),
        )
        return

    if len(results) == 1:
        await _send_pokemon_search_card(
            context,
            MenuSession(
                session_id="search",
                chat_id=update.effective_chat.id,
                message_id=update.effective_message.message_id,
                user_id=update.effective_user.id,
                message_thread_id=getattr(update.effective_message, "message_thread_id", None),
            ),
            results[0],
        )
        return

    sent_message = await update.effective_chat.send_message(
        text=_render_search_results_text(_display_user(update), results),
        parse_mode="HTML",
        message_thread_id=getattr(update.effective_message, "message_thread_id", None),
    )
    session_id = session_store.create_session(
        chat_id=update.effective_chat.id,
        message_id=sent_message.message_id,
        user_id=update.effective_user.id,
        message_thread_id=getattr(update.effective_message, "message_thread_id", None),
        data={"search_results": [entry.as_session_payload() for entry in results]},
    )
    await sent_message.edit_reply_markup(reply_markup=_build_search_results_keyboard(session_id, results))


def _create_session(session: MenuSession) -> str:
    return session_store.create_session(
        chat_id=session.chat_id,
        message_id=session.message_id,
        user_id=session.user_id,
        message_thread_id=session.message_thread_id,
    )


def _get_db(context: ContextTypes.DEFAULT_TYPE) -> Optional[Database]:
    return getattr(context, "application", None).bot_data.get("db") if getattr(context, "application", None) else None


def _display_user(update: Update) -> str:
    user = update.effective_user
    if not user:
        return "тренер"
    return display_name(getattr(user, "username", None), getattr(user, "first_name", None))


def _display_self_profile_owner(update: Update, summary: ProfileSummary) -> str:
    if summary.nickname:
        return summary.nickname
    user = update.effective_user
    if user:
        if user.first_name:
            return user.first_name
        if user.username:
            return f"@{user.username}"
    if summary.tg_username:
        return f"@{summary.tg_username}"
    return f"id {summary.telegram_id}"


def _display_profile_owner(summary: ProfileSummary) -> str:
    if summary.nickname:
        return summary.nickname
    if summary.tg_username:
        return f"@{summary.tg_username}"
    return f"id {summary.telegram_id}"


def _humanize_account_age(created_at: datetime) -> str:
    now = datetime.now(UTC)
    delta_days = max(0, (now - created_at.astimezone(UTC)).days)
    if delta_days == 0:
        return "меньше дня"
    if delta_days < 30:
        return _pluralize_days(delta_days)
    months = delta_days // 30
    if months < 12:
        return _pluralize_months(months)
    years = months // 12
    return _pluralize_years(years)


def _pluralize_days(value: int) -> str:
    return f"{value} {_pluralize_ru(value, 'день', 'дня', 'дней')}"


def _pluralize_months(value: int) -> str:
    return f"{value} {_pluralize_ru(value, 'месяц', 'месяца', 'месяцев')}"


def _pluralize_years(value: int) -> str:
    return f"{value} {_pluralize_ru(value, 'год', 'года', 'лет')}"


def _pluralize_ru(value: int, one: str, few: str, many: str) -> str:
    value = abs(value)
    if value % 10 == 1 and value % 100 != 11:
        return one
    if 2 <= value % 10 <= 4 and not 12 <= value % 100 <= 14:
        return few
    return many


def _rarity_emoji(rarity: str) -> str:
    return {
        "Legendary": "🟠",
        "Epic": "🟣",
        "Rare": "🔵",
        "Common": "⚪️",
    }.get(rarity, "▫️")


def _language_label(language: str) -> str:
    return {"ru": "Русский", "en": "English"}.get(language, language)


def _extract_command_argument(text: str) -> str:
    parts = text.split(maxsplit=1)
    if len(parts) < 2:
        return ""
    return parts[1].strip()


def _extract_bot_username(update: Update) -> Optional[str]:
    bot_username = getattr(getattr(update, "_bot", None), "username", None)
    if not bot_username:
        bot_username = getattr(getattr(update, "get_bot", lambda: None)(), "username", None)
    if not bot_username and update.callback_query and update.callback_query.message:
        bot_username = getattr(update.callback_query.message.get_bot(), "username", None)
    return bot_username


def _message_supports_caption(message: Optional[Message]) -> bool:
    return bool(message and getattr(message, "photo", None))


def _resolve_profile_image_path(summary: ProfileSummary) -> Path:
    if summary.cover_pokemon_name:
        candidate = _find_local_pokemon_image(summary.cover_pokemon_name)
        if candidate is not None:
            return candidate
    return DEFAULT_PROFILE_IMAGE_PATH if DEFAULT_PROFILE_IMAGE_PATH.exists() else FALLBACK_IMAGE_PATH


def _find_local_pokemon_image(pokemon_name: str) -> Optional[Path]:
    pokemon_dir = Path("assets/pokemon") / pokemon_name
    if not pokemon_dir.exists() or not pokemon_dir.is_dir():
        return None
    for child in sorted(pokemon_dir.iterdir()):
        if child.is_file() and child.suffix.lower() in SUPPORTED_IMAGE_SUFFIXES:
            return child
    return None
