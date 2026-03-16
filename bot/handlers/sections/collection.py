"""Collection section handler."""

from __future__ import annotations

from pathlib import Path
from typing import Optional

import structlog
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Message, Update
from telegram.error import BadRequest, TelegramError
from telegram.ext import ContextTypes

from bot.db.database import (
    CollectionEntry,
    CollectionFilterState,
    CollectionPage,
    Database,
)
from bot.navigation.context import extract_context
from bot.navigation.router import NavigationRouter, parse_callback_data
from bot.navigation.session import MenuSession, session_store
from bot.ui.menu import build_back_button

logger = structlog.get_logger()

COLLECTION_VIEW_MAIN = "main"
COLLECTION_VIEW_FILTERS = "filters"
FALLBACK_IMAGE_PATH = Path("image.png")
COLLECTION_RARITY_OPTIONS = ("Legendary", "Epic", "Rare", "Common")
COLLECTION_RARITY_CODES = {
    "Legendary": "L",
    "Epic": "E",
    "Rare": "R",
    "Common": "C",
}
COLLECTION_RARITY_CODES_REVERSE = {value: key for key, value in COLLECTION_RARITY_CODES.items()}
COLLECTION_TYPE_OPTIONS = (
    "normal",
    "fire",
    "water",
    "electric",
    "grass",
    "ice",
    "fighting",
    "poison",
    "ground",
    "flying",
    "psychic",
    "bug",
    "rock",
    "ghost",
    "dragon",
    "dark",
    "steel",
    "fairy",
)
COLLECTION_TYPE_CODES = {
    "normal": "no",
    "fire": "fi",
    "water": "wa",
    "electric": "el",
    "grass": "gr",
    "ice": "ic",
    "fighting": "fg",
    "poison": "po",
    "ground": "go",
    "flying": "fl",
    "psychic": "ps",
    "bug": "bu",
    "rock": "ro",
    "ghost": "gh",
    "dragon": "dr",
    "dark": "da",
    "steel": "st",
    "fairy": "fa",
}
COLLECTION_TYPE_CODES_REVERSE = {value: key for key, value in COLLECTION_TYPE_CODES.items()}
COLLECTION_ROUTE_SECTIONS = [
    "collection",
    "cfs",
    "cfb",
    "cfx",
    "cfd",
    "cpp",
    "cpn",
    "cd1",
    "cd2",
    "cd3",
    "cd4",
    "cd5",
    "cd6",
    "cd7",
    "cd8",
    "cd9",
    "cd10",
    "cd11",
    "cd12",
    "cfr_L",
    "cfr_E",
    "cfr_R",
    "cfr_C",
    *[f"cft_{code}" for code in COLLECTION_TYPE_CODES.values()],
]


def register_collection_routes(router: NavigationRouter) -> None:
    """Register all collection-related callback sections."""
    for section in COLLECTION_ROUTE_SECTIONS:
        router.register(section, collection_handler)


async def show_collection_screen(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    filter_state: Optional[CollectionFilterState] = None,
    screen: str = COLLECTION_VIEW_MAIN,
) -> Message:
    """Send a fresh collection message for direct commands like /collection."""
    msg_context = extract_context(update)
    db = _get_db(context)

    if not db:
        text = "📦 <b>Коллекция временно недоступна</b>\n\nБаза данных не подключена."
        sent_message = await update.effective_chat.send_message(
            text=text,
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

    active_filter_state = filter_state or CollectionFilterState()
    logger.info("collection_command_fetch_start", screen=screen, user_id=msg_context.user_id)
    collection_page = await db.get_collection_page(
        msg_context.user_id,
        update.effective_user.username if update.effective_user else None,
        active_filter_state,
    )
    logger.info("collection_command_fetch_done", screen=screen, user_id=msg_context.user_id)

    sent_message = await update.effective_chat.send_message(
        text=_render_collection_text(_display_user(update), collection_page, screen),
        parse_mode="HTML",
        message_thread_id=msg_context.message_thread_id,
    )
    session_id = session_store.create_session(
        chat_id=msg_context.chat_id,
        message_id=sent_message.message_id,
        user_id=msg_context.user_id,
        message_thread_id=msg_context.message_thread_id,
        data=_collection_session_data(collection_page, screen),
    )
    await sent_message.edit_reply_markup(
        reply_markup=_build_collection_keyboard(session_id, collection_page, screen)
    )
    logger.info("collection_command_sent", screen=screen, session_id=session_id, user_id=msg_context.user_id)
    return sent_message


async def collection_handler(update: Update, context: ContextTypes.DEFAULT_TYPE, session: MenuSession) -> None:
    """Handle collection screens, filters, pagination, and detail-card entry."""
    query = update.callback_query
    callback_data = parse_callback_data(query.data)
    section = callback_data.section if callback_data else "collection"

    try:
        logger.info("collection_handler_start", section=section, user_id=session.user_id, session_id=session.session_id)
        if section.startswith("cd"):
            await _handle_collection_detail(update, context, session, section)
            return

        db = _get_db(context)
        if not db:
            await _edit_collection_message(
                query,
                session,
                "📦 <b>Коллекция временно недоступна</b>\n\nБаза данных не подключена.",
                build_back_button(_create_session(session)),
            )
            return

        filter_state = CollectionFilterState.from_payload(session.data.get("collection_filters"))
        current_screen = str(session.data.get("collection_screen", COLLECTION_VIEW_MAIN))
        screen = current_screen

        if section == "collection":
            screen = COLLECTION_VIEW_MAIN
        elif section == "cfs":
            screen = COLLECTION_VIEW_FILTERS
        elif section == "cfb":
            screen = COLLECTION_VIEW_MAIN
        elif section == "cpp":
            filter_state = filter_state.with_page(max(1, filter_state.page - 1))
            screen = COLLECTION_VIEW_MAIN
        elif section == "cpn":
            filter_state = filter_state.with_page(filter_state.page + 1)
            screen = COLLECTION_VIEW_MAIN
        elif section == "cfd":
            filter_state = CollectionFilterState(
                rarities=filter_state.rarities,
                types=filter_state.types,
                duplicates_only=not filter_state.duplicates_only,
                page=1,
            )
            screen = COLLECTION_VIEW_FILTERS
        elif section == "cfx":
            filter_state = CollectionFilterState()
            screen = COLLECTION_VIEW_FILTERS
        elif section.startswith("cfr_"):
            rarity = COLLECTION_RARITY_CODES_REVERSE.get(section.removeprefix("cfr_"))
            if not rarity:
                return
            filter_state = _toggle_rarity_filter(filter_state, rarity)
            screen = COLLECTION_VIEW_FILTERS
        elif section.startswith("cft_"):
            pokemon_type = COLLECTION_TYPE_CODES_REVERSE.get(section.removeprefix("cft_"))
            if not pokemon_type:
                return
            filter_state = _toggle_type_filter(filter_state, pokemon_type)
            screen = COLLECTION_VIEW_FILTERS

        logger.info("collection_db_fetch_start", section=section, user_id=session.user_id, screen=screen)
        collection_page = await db.get_collection_page(
            session.user_id,
            update.effective_user.username if update.effective_user else None,
            filter_state,
        )
        logger.info("collection_db_fetch_done", section=section, user_id=session.user_id, screen=screen)
        next_session_id = _create_session(session, _collection_session_data(collection_page, screen))
        logger.info("collection_edit_start", section=section, user_id=session.user_id, screen=screen)
        await _edit_collection_message(
            query,
            session,
            _render_collection_text(_display_user(update), collection_page, screen),
            _build_collection_keyboard(next_session_id, collection_page, screen),
        )
        logger.info("collection_edit_done", section=section, user_id=session.user_id, screen=screen)

    except BadRequest as exc:
        logger.warning(
            "collection_handler_error",
            section=section,
            error="bad_request",
            error_message=str(exc),
            user_id=session.user_id,
            chat_id=session.chat_id,
        )
    except TelegramError as exc:
        logger.error(
            "collection_handler_error",
            section=section,
            error="telegram_api",
            error_message=str(exc),
            user_id=session.user_id,
        )
    except Exception as exc:
        logger.error(
            "collection_handler_error",
            section=section,
            error="unexpected",
            error_message=str(exc),
            user_id=session.user_id,
        )


def _get_db(context: ContextTypes.DEFAULT_TYPE) -> Optional[Database]:
    application = getattr(context, "application", None)
    if not application or not hasattr(application, "bot_data"):
        return None
    bot_data = getattr(application, "bot_data", None)
    if not isinstance(bot_data, dict):
        return None
    db = bot_data.get("db")
    if not db or not hasattr(db, "get_collection_page"):
        return None
    return db


def _display_user(update: Optional[Update]) -> str:
    if update and update.effective_user:
        username = getattr(update.effective_user, "username", None)
        if username:
            return f"@{username}"
        first_name = getattr(update.effective_user, "first_name", None)
        if first_name:
            return first_name
    return "тренер"


def _collection_session_data(collection_page: CollectionPage, screen: str) -> dict[str, object]:
    return {
        "collection_screen": screen,
        "collection_filters": collection_page.filter_state.to_session_payload(),
        "collection_entries": [entry.as_session_payload() for entry in collection_page.entries],
    }


def _create_session(session: MenuSession, data: Optional[dict[str, object]] = None) -> str:
    return session_store.create_session(
        chat_id=session.chat_id,
        message_id=session.message_id,
        user_id=session.user_id,
        message_thread_id=session.message_thread_id,
        data=data,
    )


def _toggle_rarity_filter(filter_state: CollectionFilterState, rarity: str) -> CollectionFilterState:
    rarities = list(filter_state.rarities)
    if rarity in rarities:
        rarities.remove(rarity)
    else:
        rarities.append(rarity)
    ordered_rarities = tuple(option for option in COLLECTION_RARITY_OPTIONS if option in rarities)
    return CollectionFilterState(
        rarities=ordered_rarities,
        types=filter_state.types,
        duplicates_only=filter_state.duplicates_only,
        page=1,
    )


def _toggle_type_filter(filter_state: CollectionFilterState, pokemon_type: str) -> CollectionFilterState:
    types = list(filter_state.types)
    if pokemon_type in types:
        types.remove(pokemon_type)
    elif len(types) < 2:
        types.append(pokemon_type)
    ordered_types = tuple(option for option in COLLECTION_TYPE_OPTIONS if option in types)
    return CollectionFilterState(
        rarities=filter_state.rarities,
        types=ordered_types,
        duplicates_only=filter_state.duplicates_only,
        page=1,
    )


def _rarity_marker(rarity: str) -> str:
    return {
        "Legendary": "🟠",
        "Epic": "🟣",
        "Rare": "🟢",
        "Common": "⚪️",
    }.get(rarity, "⚪️")


def _type_emoji(pokemon_type: str) -> str:
    return {
        "normal": "⚪️",
        "fire": "🔥",
        "water": "💧",
        "electric": "⚡️",
        "grass": "🍃",
        "ice": "❄️",
        "fighting": "🥊",
        "poison": "☠️",
        "ground": "🟫",
        "flying": "🕊",
        "psychic": "🔮",
        "bug": "🐛",
        "rock": "🪨",
        "ghost": "👻",
        "dragon": "🐉",
        "dark": "🌑",
        "steel": "⚙️",
        "fairy": "✨",
    }.get(pokemon_type, "•")


def _render_collection_text(user_label: str, collection_page: CollectionPage, screen: str) -> str:
    if screen == COLLECTION_VIEW_FILTERS:
        return _render_filter_screen_text(user_label, collection_page.filter_state)
    return _render_collection_screen_text(user_label, collection_page)


def _render_collection_screen_text(user_label: str, collection_page: CollectionPage) -> str:
    lines = [
        f"📦 {user_label}, ваша коллекция (страница {collection_page.current_page} / {collection_page.total_pages}):",
        "",
    ]
    if collection_page.entries:
        for entry in collection_page.entries:
            lines.append(_format_collection_entry_line(entry))
    else:
        lines.append("Совпадений не найдено.")

    lines.extend(
        [
            "",
            f"Найдено {collection_page.total_entries} покемонов",
        ]
    )
    filter_summary = _render_active_filter_summary(collection_page.filter_state)
    if filter_summary:
        lines.append(filter_summary)
    return "\n".join(lines)


def _render_filter_screen_text(user_label: str, filter_state: CollectionFilterState) -> str:
    rarity_summary = " ".join(_rarity_marker(rarity) for rarity in filter_state.rarities) or "не выбрано"
    type_summary = " ".join(f"{_type_emoji(pokemon_type)} {pokemon_type}" for pokemon_type in filter_state.types) or "не выбрано"
    duplicates_summary = "включено" if filter_state.duplicates_only else "выключено"
    return "\n".join(
        [
            f"⚙️ {user_label}, настройки фильтров:",
            f"💎 По редкости: {rarity_summary}",
            f"🌈 По стихиям: {type_summary}",
            f"🧬 Только дубликаты: {duplicates_summary}",
            "",
            "Можно выбрать до 2 стихий одновременно.",
            "Если выбраны две стихии, покемон должен содержать обе.",
        ]
    )


def _render_active_filter_summary(filter_state: CollectionFilterState) -> str:
    parts: list[str] = []
    if filter_state.rarities:
        parts.append("Редкости: " + ", ".join(filter_state.rarities))
    if filter_state.types:
        parts.append("Стихии: " + ", ".join(filter_state.types))
    if filter_state.duplicates_only:
        parts.append("Только дубликаты")
    if not parts:
        return ""
    return "Активные фильтры: " + " | ".join(parts)


def _format_collection_entry_line(entry: CollectionEntry) -> str:
    return f"{_rarity_marker(entry.rarity)} {entry.name} x{entry.quantity} | id: {entry.pokemon_id}"


def _build_collection_keyboard(
    session_id: str,
    collection_page: CollectionPage,
    screen: str,
) -> InlineKeyboardMarkup:
    keyboard: list[list[InlineKeyboardButton]] = []

    if screen == COLLECTION_VIEW_FILTERS:
        keyboard.append(
            [
                _build_toggle_button(
                    f"{_rarity_marker(rarity)} {rarity}",
                    rarity in collection_page.filter_state.rarities,
                        f"menu:cfr_{COLLECTION_RARITY_CODES[rarity]}:{session_id}",
                    )
                for rarity in COLLECTION_RARITY_OPTIONS
            ]
        )
        for index in range(0, len(COLLECTION_TYPE_OPTIONS), 3):
            row = []
            for pokemon_type in COLLECTION_TYPE_OPTIONS[index:index + 3]:
                row.append(
                    _build_toggle_button(
                        f"{_type_emoji(pokemon_type)} {pokemon_type}",
                        pokemon_type in collection_page.filter_state.types,
                        f"menu:cft_{COLLECTION_TYPE_CODES[pokemon_type]}:{session_id}",
                    )
                )
            keyboard.append(row)
        keyboard.append([
            _build_toggle_button(
                "🧬 Только дубликаты",
                collection_page.filter_state.duplicates_only,
                f"menu:cfd:{session_id}",
            )
        ])
        keyboard.append([
            InlineKeyboardButton("🧹 Сброс", callback_data=f"menu:cfx:{session_id}")
        ])
        keyboard.append([
            InlineKeyboardButton("🔙 Назад", callback_data=f"menu:cfb:{session_id}")
        ])
        return InlineKeyboardMarkup(keyboard)

    if collection_page.entries:
        for index in range(0, len(collection_page.entries), 4):
            row = []
            for entry_index, entry in enumerate(collection_page.entries[index:index + 4], start=index + 1):
                row.append(
                    InlineKeyboardButton(
                        f"🔎 {entry.pokemon_id}",
                        callback_data=f"menu:cd{entry_index}:{session_id}",
                    )
                )
            keyboard.append(row)

    nav_row: list[InlineKeyboardButton] = []
    if collection_page.has_previous():
        nav_row.append(InlineKeyboardButton("⬅️", callback_data=f"menu:cpp:{session_id}"))
    nav_row.append(InlineKeyboardButton("⚙️ Фильтры", callback_data=f"menu:cfs:{session_id}"))
    if collection_page.has_next():
        nav_row.append(InlineKeyboardButton("➡️", callback_data=f"menu:cpn:{session_id}"))
    keyboard.append(nav_row)
    keyboard.extend(build_back_button(session_id).inline_keyboard)
    return InlineKeyboardMarkup(keyboard)


def _build_toggle_button(text: str, enabled: bool, callback_data: str) -> InlineKeyboardButton:
    prefix = "✅ " if enabled else ""
    return InlineKeyboardButton(f"{prefix}{text}", callback_data=callback_data)


async def _edit_collection_message(
    query,
    session: MenuSession,
    text: str,
    reply_markup: InlineKeyboardMarkup,
) -> None:
    await query.edit_message_text(
        text=text,
        parse_mode="HTML",
        reply_markup=reply_markup,
    )


async def _handle_collection_detail(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    session: MenuSession,
    section: str,
) -> None:
    index = int(section.removeprefix("cd")) - 1
    entry_payloads = session.data.get("collection_entries")
    if not entry_payloads or not isinstance(entry_payloads, list) or index >= len(entry_payloads):
        raise ValueError("Collection detail is no longer available")
    entry = CollectionEntry.from_payload(entry_payloads[index])
    await _send_collection_card(context, session, entry, _display_user(update))
    logger.info("collection_detail_sent", user_id=session.user_id, pokemon_id=entry.pokemon_id, index=index + 1)


async def _send_collection_card(
    context: ContextTypes.DEFAULT_TYPE,
    session: MenuSession,
    entry: CollectionEntry,
    user_label: Optional[str] = None,
) -> Message:
    caption = _render_collection_card_caption(entry, user_label)
    if FALLBACK_IMAGE_PATH.exists():
        logger.info("collection_send_photo_start", user_id=session.user_id, pokemon_id=entry.pokemon_id)
        with FALLBACK_IMAGE_PATH.open("rb") as image_file:
            message = await context.bot.send_photo(
                chat_id=session.chat_id,
                message_thread_id=session.message_thread_id,
                photo=image_file,
                caption=caption,
                parse_mode="HTML",
            )
        logger.info("collection_send_photo_done", user_id=session.user_id, pokemon_id=entry.pokemon_id)
    else:
        logger.info("collection_send_message_start", user_id=session.user_id, pokemon_id=entry.pokemon_id)
        message = await context.bot.send_message(
            chat_id=session.chat_id,
            message_thread_id=session.message_thread_id,
            text=caption,
            parse_mode="HTML",
        )
        logger.info("collection_send_message_done", user_id=session.user_id, pokemon_id=entry.pokemon_id)
    return message


def _render_collection_card_caption(entry: CollectionEntry, user_label: Optional[str] = None) -> str:
    return "\n".join(
        line
        for line in [
            f"📘 <b>{entry.name}</b>",
            (f"Тренер: <b>{user_label}</b>" if user_label else ""),
            f"Редкость: <b>{entry.rarity}</b>",
            f"Тип: <b>{entry.pokemon_type or 'unknown'}</b>",
            f"Количество: <b>{entry.quantity}</b>",
            f"HP: <b>{entry.base_hp}</b>",
            f"ATK: <b>{entry.base_attack}</b>",
            f"DEF: <b>{entry.base_defense}</b>",
            f"SPD: <b>{entry.base_stamina}</b>",
            f"ID покемона: <b>{entry.pokemon_id}</b>",
            f"ID экземпляра: <b>{entry.sample_user_pokemon_id}</b>",
        ]
        if line
    )
