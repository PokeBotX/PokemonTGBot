"""Collection section handler."""

from __future__ import annotations

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
    POKEMON_RELEASE_REWARDS,
)
from bot.navigation.context import extract_context
from bot.navigation.router import NavigationRouter, parse_callback_data
from bot.navigation.session import MenuSession, session_store
from bot.handlers.sections.market import build_market_entry_payload, resolve_market_card_action
from bot.ui.html import display_name, escape_html
from bot.ui.menu import build_back_button
from bot.ui.pokemon_cards import (
    EXTRA_CARD_SECTION,
    PokemonCardData,
    build_pokemon_card_keyboard,
    RELEASE_CARD_SECTION,
    render_pokemon_card_caption,
    send_pokemon_card,
)

logger = structlog.get_logger()

COLLECTION_VIEW_MAIN = "main"
COLLECTION_VIEW_FILTERS = "filters"
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
    EXTRA_CARD_SECTION,
    RELEASE_CARD_SECTION,
    "pkb",
    "pkl",
    "pkv",
    "pkrc",
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
    "cei1",
    "cei2",
    "cei3",
    "cei4",
    "cei5",
    "cei6",
    "cei7",
    "cei8",
    "cei9",
    "cei10",
    "cei11",
    "cei12",
    "cfr_L",
    "cfr_E",
    "cfr_R",
    "cfr_C",
    *[f"cft_{code}" for code in COLLECTION_TYPE_CODES.values()],
]

COLLECTION_INSTANCE_SELECT_ROUTES = {
    "cei1": 0,
    "cei2": 1,
    "cei3": 2,
    "cei4": 3,
    "cei5": 4,
    "cei6": 5,
    "cei7": 6,
    "cei8": 7,
    "cei9": 8,
    "cei10": 9,
    "cei11": 10,
    "cei12": 11,
}


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
        if section == RELEASE_CARD_SECTION:
            await _handle_release_prompt(update, context, session)
            return

        if section == EXTRA_CARD_SECTION:
            await _handle_extra_actions_prompt(update, context, session)
            return

        if section == "pkb":
            await _handle_card_return(update, context, session)
            return

        if section == "pkl":
            await _handle_lock_toggle(update, context, session)
            return

        if section == "pkv":
            await _handle_set_cover(update, context, session)
            return

        if section == "pkrc":
            await _handle_release_confirm(update, context, session)
            return

        if section.startswith("cd"):
            await _handle_collection_detail(update, context, session, section)
            return

        if section in COLLECTION_INSTANCE_SELECT_ROUTES:
            await _handle_collection_instance_select(update, context, session, section)
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
        return display_name(
            getattr(update.effective_user, "username", None),
            getattr(update.effective_user, "first_name", None),
        )
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
        f"📦 {escape_html(user_label)}, ваша коллекция (страница {collection_page.current_page} / {collection_page.total_pages}):",
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
            f"⚙️ {escape_html(user_label)}, настройки фильтров:",
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
    message = getattr(query, "message", None)
    if getattr(message, "photo", None):
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
    if entry.quantity > 1:
        db = _get_db(context)
        if db:
            instances = await db.get_user_pokemon_instances_for_species(
                session.user_id,
                update.effective_user.username if update.effective_user else None,
                pokemon_id=entry.pokemon_id,
            )
            if len(instances) > 1:
                await _send_collection_instance_picker(context, session, entry, instances)
                logger.info(
                    "collection_instance_picker_sent",
                    user_id=session.user_id,
                    pokemon_id=entry.pokemon_id,
                    instance_count=len(instances),
                )
                return
    await _send_collection_card(context, session, entry, _display_user(update))
    logger.info("collection_detail_sent", user_id=session.user_id, pokemon_id=entry.pokemon_id, index=index + 1)


async def _send_collection_instance_picker(
    context: ContextTypes.DEFAULT_TYPE,
    session: MenuSession,
    summary_entry: CollectionEntry,
    instances: list[CollectionEntry],
) -> Message:
    message = await context.bot.send_message(
        chat_id=session.chat_id,
        text=_render_instance_picker_text(summary_entry, instances),
        parse_mode="HTML",
        message_thread_id=session.message_thread_id,
    )
    picker_session_id = session_store.create_session(
        chat_id=session.chat_id,
        message_id=message.message_id,
        user_id=session.user_id,
        message_thread_id=session.message_thread_id,
        data={"collection_instance_entries": [entry.as_session_payload() for entry in instances]},
    )
    await message.edit_reply_markup(reply_markup=_build_instance_picker_keyboard(picker_session_id, instances))
    return message


async def _handle_collection_instance_select(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    session: MenuSession,
    section: str,
) -> None:
    index = COLLECTION_INSTANCE_SELECT_ROUTES[section]
    payloads = session.data.get("collection_instance_entries")
    if not isinstance(payloads, list) or index >= len(payloads):
        raise ValueError("Collection instance selection is no longer available")
    entry = CollectionEntry.from_payload(payloads[index])
    await _send_collection_card(context, session, entry, _display_user(update))
    logger.info(
        "collection_instance_selected",
        user_id=session.user_id,
        pokemon_id=entry.pokemon_id,
        user_pokemon_id=entry.sample_user_pokemon_id,
    )


async def _send_collection_card(
    context: ContextTypes.DEFAULT_TYPE,
    session: MenuSession,
    entry: CollectionEntry,
    user_label: Optional[str] = None,
) -> Message:
    logger.info("collection_send_card_start", user_id=session.user_id, pokemon_id=entry.pokemon_id)
    db = _get_db(context)
    has_active_trade = bool(db and await db.get_active_trade_for_user(session.user_id, None))
    message = await send_pokemon_card(
        context,
        chat_id=session.chat_id,
        message_thread_id=session.message_thread_id,
        card=PokemonCardData(
            pokemon_id=entry.pokemon_id,
            name=entry.name,
            rarity=entry.rarity,
            pokemon_type=entry.pokemon_type,
            quantity=entry.quantity,
            base_hp=entry.base_hp,
            base_attack=entry.base_attack,
            base_defense=entry.base_defense,
            base_stamina=entry.base_stamina,
            trainer_label=user_label,
            user_pokemon_id=entry.sample_user_pokemon_id,
            image_credit_id=entry.image_credit_id,
        ),
    )
    detail_session_id = session_store.create_session(
        chat_id=session.chat_id,
        message_id=message.message_id,
        user_id=session.user_id,
        message_thread_id=session.message_thread_id,
        data=build_market_entry_payload(
            action=resolve_market_card_action(True),
            pokemon_id=entry.pokemon_id,
            pokemon_name=entry.name,
            user_pokemon_id=entry.sample_user_pokemon_id,
        )
        | {
            "release_user_pokemon_id": entry.sample_user_pokemon_id,
            "release_pokemon_name": entry.name,
            "release_rarity": entry.rarity,
        },
    )
    await message.edit_reply_markup(
        reply_markup=build_pokemon_card_keyboard(
            detail_session_id,
            include_market_button=True,
            include_trade_button=has_active_trade,
            include_release_button=True,
            include_extra_button=True,
        )
    )
    logger.info("collection_send_card_done", user_id=session.user_id, pokemon_id=entry.pokemon_id)
    return message


async def _handle_release_prompt(update: Update, context: ContextTypes.DEFAULT_TYPE, session: MenuSession) -> None:
    query = update.callback_query
    user_pokemon_id = session.data.get("release_user_pokemon_id")
    if user_pokemon_id is None:
        raise ValueError("Release payload is missing")

    entry = await _load_owned_card_entry(update, context, session)
    if not entry:
        await query.answer("Карточка больше недоступна.", show_alert=False)
        return

    reward = POKEMON_RELEASE_REWARDS.get(entry.rarity, 32)
    next_session_id = _create_session(session, dict(session.data))
    await _edit_collection_message(
        query,
        session,
        "\n".join(
            [
                "🕊 <b>Отпустить покемона?</b>",
                "",
                f"Покемон: <b>{escape_html(entry.name)}</b>",
                f"Экземпляр: <code>{int(user_pokemon_id)}</code>",
                f"Награда: 🪙 <b>{reward}</b>",
            ]
        ),
        InlineKeyboardMarkup(
            [
                [InlineKeyboardButton("✅ Отпустить", callback_data=f"menu:pkrc:{next_session_id}")],
                [InlineKeyboardButton("❌ Отмена", callback_data=f"menu:back:{next_session_id}")],
            ]
        ),
    )


async def _handle_extra_actions_prompt(update: Update, context: ContextTypes.DEFAULT_TYPE, session: MenuSession) -> None:
    query = update.callback_query
    db = _get_db(context)
    if not db:
        await query.answer("Коллекция временно недоступна.", show_alert=False)
        return

    entry = await _load_owned_card_entry(update, context, session)
    if not entry:
        await query.answer("Карточка больше недоступна.", show_alert=False)
        return

    source_url = await _resolve_entry_source_url(db, entry)
    next_session_id = _create_session(session, dict(session.data))
    await _edit_collection_message(
        query,
        session,
        _render_extra_actions_text(entry),
        _build_extra_actions_keyboard(next_session_id, entry.is_locked, source_url=source_url),
    )


async def _handle_card_return(update: Update, context: ContextTypes.DEFAULT_TYPE, session: MenuSession) -> None:
    query = update.callback_query
    db = _get_db(context)
    entry = await _load_owned_card_entry(update, context, session)
    if not entry:
        await query.answer("Карточка больше недоступна.", show_alert=False)
        return
    await _edit_collection_card_message(query, session, entry, db)


async def _handle_lock_toggle(update: Update, context: ContextTypes.DEFAULT_TYPE, session: MenuSession) -> None:
    query = update.callback_query
    db = _get_db(context)
    if not db:
        await query.answer("Коллекция временно недоступна.", show_alert=False)
        return

    user_pokemon_id = session.data.get("release_user_pokemon_id")
    if user_pokemon_id is None:
        await query.answer("Карточка больше недоступна.", show_alert=False)
        return

    try:
        result = await db.toggle_user_pokemon_lock(
            session.user_id,
            update.effective_user.username if update.effective_user else None,
            user_pokemon_id=int(user_pokemon_id),
        )
    except Exception as exc:
        error_message = str(exc) or "Не удалось изменить статус покемона."
        await query.answer(error_message, show_alert=False)
        return

    entry = await _load_owned_card_entry(update, context, session)
    if not entry:
        await query.answer("Статус изменён, но карточка больше недоступна.", show_alert=False)
        return

    next_session_id = _create_session(session, dict(session.data))
    status_text = "🔒 Покемон залочен." if result.is_locked else "🔓 Покемон разблокирован."
    source_url = await _resolve_entry_source_url(db, entry)
    await _edit_collection_message(
        query,
        session,
        _render_extra_actions_text(entry, status_text=status_text),
        _build_extra_actions_keyboard(next_session_id, result.is_locked, source_url=source_url),
    )
    await query.answer(status_text, show_alert=False)


async def _handle_set_cover(update: Update, context: ContextTypes.DEFAULT_TYPE, session: MenuSession) -> None:
    query = update.callback_query
    db = _get_db(context)
    if not db:
        await query.answer("Профиль временно недоступен.", show_alert=False)
        return

    entry = await _load_owned_card_entry(update, context, session)
    if not entry:
        await query.answer("Карточка больше недоступна.", show_alert=False)
        return
    if entry.image_credit_id is None:
        await query.answer("У этого покемона нет картинки для обложки.", show_alert=False)
        return

    try:
        await db.update_profile_cover(
            session.user_id,
            update.effective_user.username if update.effective_user else None,
            image_credit_id=int(entry.image_credit_id),
        )
    except Exception as exc:
        error_message = str(exc) or "Не удалось обновить обложку."
        await query.answer(error_message, show_alert=False)
        return

    next_session_id = _create_session(session, dict(session.data))
    status_text = f"🖼 Обложка обновлена: <b>{entry.name}</b>."
    source_url = await _resolve_entry_source_url(db, entry)
    await _edit_collection_message(
        query,
        session,
        _render_extra_actions_text(entry, status_text=status_text),
        _build_extra_actions_keyboard(next_session_id, entry.is_locked, source_url=source_url),
    )
    await query.answer("Обложка обновлена.", show_alert=False)


async def _handle_release_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE, session: MenuSession) -> None:
    query = update.callback_query
    db = _get_db(context)
    if not db:
        await query.answer("Коллекция временно недоступна.", show_alert=False)
        return

    user_pokemon_id = session.data.get("release_user_pokemon_id")
    if user_pokemon_id is None:
        raise ValueError("Release confirmation payload is missing")

    result = await db.release_user_pokemon(
        session.user_id,
        update.effective_user.username if update.effective_user else None,
        user_pokemon_id=int(user_pokemon_id),
    )
    next_session_id = _create_session(session)
    await _edit_collection_message(
        query,
        session,
        "\n".join(
            [
                "✅ <b>Покемон отпущен</b>",
                "",
                f"Покемон: <b>{escape_html(result.name)}</b>",
                f"Редкость: <b>{escape_html(result.rarity)}</b>",
                f"Получено: 🪙 <b>{result.reward_amount}</b>",
            ]
        ),
        build_back_button(next_session_id),
    )
    await query.answer("Покемон отпущен.", show_alert=False)


async def _load_owned_card_entry(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    session: MenuSession,
) -> Optional[CollectionEntry]:
    db = _get_db(context)
    if not db:
        return None
    user_pokemon_id = session.data.get("release_user_pokemon_id")
    if user_pokemon_id is None:
        return None
    entry = await db.get_user_pokemon_entry(int(user_pokemon_id))
    if not entry:
        return None
    return entry


async def _resolve_entry_source_url(db: Database, entry: CollectionEntry) -> Optional[str]:
    if entry.image_credit_id is None:
        return None
    image_credit = await db.get_image_credit(int(entry.image_credit_id))
    source = getattr(image_credit, "source", None) if image_credit else None
    if not isinstance(source, str):
        return None
    source = source.strip()
    if not source.startswith(("http://", "https://")):
        return None
    return source


async def _edit_collection_card_message(
    query,
    session: MenuSession,
    entry: CollectionEntry,
    db: Optional[Database],
) -> None:
    next_session_id = _create_session(
        session,
        build_market_entry_payload(
            action=resolve_market_card_action(True),
            pokemon_id=entry.pokemon_id,
            pokemon_name=entry.name,
            user_pokemon_id=entry.sample_user_pokemon_id,
        )
        | {
            "release_user_pokemon_id": entry.sample_user_pokemon_id,
            "release_pokemon_name": entry.name,
            "release_rarity": entry.rarity,
        },
    )
    await _edit_collection_message(
        query,
        session,
        _render_collection_card_caption(entry),
        build_pokemon_card_keyboard(
            next_session_id,
            include_market_button=True,
            include_trade_button=bool(db and await db.get_active_trade_for_user(session.user_id, None)),
            include_release_button=True,
            include_extra_button=True,
        ),
    )


def _render_extra_actions_text(entry: CollectionEntry, *, status_text: Optional[str] = None) -> str:
    lock_line = "🔒 Статус: <b>залочен</b>" if entry.is_locked else "🔓 Статус: <b>не залочен</b>"
    lines = [
        "⚙️ <b>Дополнительно</b>",
        "",
        f"Покемон: <b>{escape_html(entry.name)}</b>",
        f"Экземпляр: <code>{entry.sample_user_pokemon_id}</code>",
        lock_line,
    ]
    if status_text:
        lines.extend(["", status_text])
    return "\n".join(lines)


def _render_instance_picker_text(summary_entry: CollectionEntry, instances: list[CollectionEntry]) -> str:
    lines = [
        "🧬 <b>Выберите экземпляр покемона</b>",
        "",
        f"Покемон: <b>{escape_html(summary_entry.name)}</b>",
        f"Найдено экземпляров: <b>{len(instances)}</b>",
        "",
    ]
    for index, entry in enumerate(instances, start=1):
        lock_marker = " 🔒" if entry.is_locked else ""
        lines.append(f"{index}. <code>{entry.sample_user_pokemon_id}</code>{lock_marker}")
    return "\n".join(lines)


def _build_instance_picker_keyboard(session_id: str, instances: list[CollectionEntry]) -> InlineKeyboardMarkup:
    keyboard: list[list[InlineKeyboardButton]] = []
    for route, index in COLLECTION_INSTANCE_SELECT_ROUTES.items():
        if index >= len(instances):
            break
        entry = instances[index]
        label = f"#{entry.sample_user_pokemon_id}"
        if entry.is_locked:
            label += " 🔒"
        keyboard.append([InlineKeyboardButton(label, callback_data=f"menu:{route}:{session_id}")])
    keyboard.extend(build_back_button(session_id).inline_keyboard)
    return InlineKeyboardMarkup(keyboard)


def _build_extra_actions_keyboard(session_id: str, is_locked: bool, *, source_url: Optional[str] = None) -> InlineKeyboardMarkup:
    lock_label = "🔓 Разлочить" if is_locked else "🔒 Залочить"
    rows = [
        [InlineKeyboardButton(lock_label, callback_data=f"menu:pkl:{session_id}")],
        [InlineKeyboardButton("🖼 На обложку", callback_data=f"menu:pkv:{session_id}")],
    ]
    if source_url:
        rows.append([InlineKeyboardButton("🔗 Источник", url=source_url)])
    rows.append([InlineKeyboardButton("🔙 К карточке", callback_data=f"menu:pkb:{session_id}")])
    return InlineKeyboardMarkup(rows)


def _render_collection_card_caption(entry: CollectionEntry, user_label: Optional[str] = None) -> str:
    return render_pokemon_card_caption(
        PokemonCardData(
            pokemon_id=entry.pokemon_id,
            name=entry.name,
            rarity=entry.rarity,
            pokemon_type=entry.pokemon_type,
            quantity=entry.quantity,
            base_hp=entry.base_hp,
            base_attack=entry.base_attack,
            base_defense=entry.base_defense,
            base_stamina=entry.base_stamina,
            trainer_label=user_label,
            user_pokemon_id=entry.sample_user_pokemon_id,
            image_credit_id=entry.image_credit_id,
        )
    )
