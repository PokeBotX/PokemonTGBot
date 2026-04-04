"""Market section handlers."""

from __future__ import annotations

from typing import Optional

import structlog
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Message, Update
from telegram.error import BadRequest, TelegramError
from telegram.ext import ContextTypes

from bot.db.database import (
    Database,
    MarketBuyRequestSummary,
    MarketListingSummary,
    MarketBrowsePage,
    MarketBrowseState,
    MARKET_SORT_CHEAPEST,
    MARKET_SORT_NEWEST,
    ShopError,
)
from bot.navigation.context import extract_context
from bot.navigation.router import NavigationRouter, parse_callback_data
from bot.navigation.session import MenuSession, PendingInput, session_store
from bot.ui.html import display_name, escape_html
from bot.ui.menu import build_back_button

logger = structlog.get_logger()

MARKET_ROUTE_ROOT = "market"
MARKET_ROUTE_BUY = "mrb"
MARKET_ROUTE_SELL = "mrs"
MARKET_ROUTE_MY_LISTINGS = "mrl"
MARKET_ROUTE_MY_REQUESTS = "mrq"
MARKET_ROUTE_CARD_ENTRY = "mce"
MARKET_ROUTE_FILTERS = "mrf"
MARKET_ROUTE_BACK = "mrbk"
MARKET_ROUTE_SORT_NEWEST = "mrsn"
MARKET_ROUTE_SORT_CHEAPEST = "mrsc"
MARKET_ROUTE_AFFORDABLE = "mraf"
MARKET_ROUTE_BUY_PAGE_PREV = "mrbp"
MARKET_ROUTE_BUY_PAGE_NEXT = "mrbn"
MARKET_ROUTE_BUY_SELECT_1 = "mbs1"
MARKET_ROUTE_BUY_SELECT_2 = "mbs2"
MARKET_ROUTE_BUY_SELECT_3 = "mbs3"
MARKET_ROUTE_BUY_SELECT_4 = "mbs4"
MARKET_ROUTE_BUY_SELECT_5 = "mbs5"
MARKET_ROUTE_BUY_SELECT_6 = "mbs6"
MARKET_ROUTE_BUY_SELECT_7 = "mbs7"
MARKET_ROUTE_BUY_SELECT_8 = "mbs8"
MARKET_ROUTE_BUY_SELECT_9 = "mbs9"
MARKET_ROUTE_BUY_SELECT_10 = "mbs10"
MARKET_ROUTE_CONFIRM_BUY = "mcb"
MARKET_ROUTE_CONFIRM_SELL = "mcs"
MARKET_ROUTE_CONFIRM_REQUEST = "mcr"
MARKET_ROUTE_CONFIRM_FULFILL = "mcf"
MARKET_ROUTE_CANCEL = "mca"
MARKET_ROUTE_START_SELL_PRICE = "msp"
MARKET_ROUTE_START_BUY_PRICE = "mbp"
MARKET_ROUTE_REMOVE_LISTING_1 = "mlr1"
MARKET_ROUTE_REMOVE_LISTING_2 = "mlr2"
MARKET_ROUTE_CANCEL_REQUEST_1 = "mqc1"
MARKET_ROUTE_CANCEL_REQUEST_2 = "mqc2"
MARKET_ROUTE_CANCEL_REQUEST_3 = "mqc3"
MARKET_ROUTE_CANCEL_REQUEST_4 = "mqc4"
MARKET_ROUTE_CANCEL_REQUEST_5 = "mqc5"
MARKET_ROUTE_FULFILL_REQUEST_1 = "mrf1"
MARKET_ROUTE_FULFILL_REQUEST_2 = "mrf2"
MARKET_ROUTE_FULFILL_REQUEST_3 = "mrf3"
MARKET_ROUTE_FULFILL_REQUEST_4 = "mrf4"
MARKET_ROUTE_FULFILL_REQUEST_5 = "mrf5"
MARKET_PENDING_ACTION_SELL_PRICE = "market_sell_price"
MARKET_PENDING_ACTION_BUY_PRICE = "market_buy_price"
MARKET_CARD_ACTION_SELL = "sell"
MARKET_CARD_ACTION_REQUEST = "buy_request"
MARKET_VIEW_ROOT = "root"
MARKET_VIEW_BUY = "buy"
MARKET_RARITY_OPTIONS = ("Legendary", "Epic", "Rare", "Common")
MARKET_RARITY_CODES = {
    "Legendary": "L",
    "Epic": "E",
    "Rare": "R",
    "Common": "C",
}
MARKET_RARITY_CODES_REVERSE = {value: key for key, value in MARKET_RARITY_CODES.items()}
MARKET_ROUTE_SECTIONS = [
    MARKET_ROUTE_ROOT,
    MARKET_ROUTE_BUY,
    MARKET_ROUTE_SELL,
    MARKET_ROUTE_MY_LISTINGS,
    MARKET_ROUTE_MY_REQUESTS,
    MARKET_ROUTE_CARD_ENTRY,
    MARKET_ROUTE_FILTERS,
    MARKET_ROUTE_BACK,
    MARKET_ROUTE_SORT_NEWEST,
    MARKET_ROUTE_SORT_CHEAPEST,
    MARKET_ROUTE_AFFORDABLE,
    MARKET_ROUTE_BUY_PAGE_PREV,
    MARKET_ROUTE_BUY_PAGE_NEXT,
    MARKET_ROUTE_BUY_SELECT_1,
    MARKET_ROUTE_BUY_SELECT_2,
    MARKET_ROUTE_BUY_SELECT_3,
    MARKET_ROUTE_BUY_SELECT_4,
    MARKET_ROUTE_BUY_SELECT_5,
    MARKET_ROUTE_BUY_SELECT_6,
    MARKET_ROUTE_BUY_SELECT_7,
    MARKET_ROUTE_BUY_SELECT_8,
    MARKET_ROUTE_BUY_SELECT_9,
    MARKET_ROUTE_BUY_SELECT_10,
    MARKET_ROUTE_CONFIRM_BUY,
    MARKET_ROUTE_CONFIRM_SELL,
    MARKET_ROUTE_CONFIRM_REQUEST,
    MARKET_ROUTE_CONFIRM_FULFILL,
    MARKET_ROUTE_CANCEL,
    MARKET_ROUTE_START_SELL_PRICE,
    MARKET_ROUTE_START_BUY_PRICE,
    MARKET_ROUTE_REMOVE_LISTING_1,
    MARKET_ROUTE_REMOVE_LISTING_2,
    MARKET_ROUTE_CANCEL_REQUEST_1,
    MARKET_ROUTE_CANCEL_REQUEST_2,
    MARKET_ROUTE_CANCEL_REQUEST_3,
    MARKET_ROUTE_CANCEL_REQUEST_4,
    MARKET_ROUTE_CANCEL_REQUEST_5,
    MARKET_ROUTE_FULFILL_REQUEST_1,
    MARKET_ROUTE_FULFILL_REQUEST_2,
    MARKET_ROUTE_FULFILL_REQUEST_3,
    MARKET_ROUTE_FULFILL_REQUEST_4,
    MARKET_ROUTE_FULFILL_REQUEST_5,
    *[f"mrr_{code}" for code in MARKET_RARITY_CODES.values()],
]


MARKET_BUY_SELECT_ROUTES = {
    MARKET_ROUTE_BUY_SELECT_1: 0,
    MARKET_ROUTE_BUY_SELECT_2: 1,
    MARKET_ROUTE_BUY_SELECT_3: 2,
    MARKET_ROUTE_BUY_SELECT_4: 3,
    MARKET_ROUTE_BUY_SELECT_5: 4,
    MARKET_ROUTE_BUY_SELECT_6: 5,
    MARKET_ROUTE_BUY_SELECT_7: 6,
    MARKET_ROUTE_BUY_SELECT_8: 7,
    MARKET_ROUTE_BUY_SELECT_9: 8,
    MARKET_ROUTE_BUY_SELECT_10: 9,
}
MARKET_CANCEL_REQUEST_ROUTES = {
    MARKET_ROUTE_CANCEL_REQUEST_1: 0,
    MARKET_ROUTE_CANCEL_REQUEST_2: 1,
    MARKET_ROUTE_CANCEL_REQUEST_3: 2,
    MARKET_ROUTE_CANCEL_REQUEST_4: 3,
    MARKET_ROUTE_CANCEL_REQUEST_5: 4,
}
MARKET_FULFILL_REQUEST_ROUTES = {
    MARKET_ROUTE_FULFILL_REQUEST_1: 0,
    MARKET_ROUTE_FULFILL_REQUEST_2: 1,
    MARKET_ROUTE_FULFILL_REQUEST_3: 2,
    MARKET_ROUTE_FULFILL_REQUEST_4: 3,
    MARKET_ROUTE_FULFILL_REQUEST_5: 4,
}


def register_market_routes(router: NavigationRouter) -> None:
    """Register all market callback sections."""
    for section in MARKET_ROUTE_SECTIONS:
        router.register(section, market_handler)


def resolve_market_card_action(user_owns_pokemon: bool) -> str:
    """Decide the first market branch from a pokemon card."""
    return MARKET_CARD_ACTION_SELL if user_owns_pokemon else MARKET_CARD_ACTION_REQUEST


def build_market_entry_payload(
    *,
    action: str,
    pokemon_id: int,
    pokemon_name: str,
    user_pokemon_id: int | None = None,
) -> dict[str, object]:
    """Serialize card-entry context into session data."""
    return {
        "market_entry_action": action,
        "market_entry_pokemon_id": pokemon_id,
        "market_entry_pokemon_name": pokemon_name,
        "market_entry_user_pokemon_id": user_pokemon_id,
    }


async def show_market_screen(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    *,
    screen: str = MARKET_VIEW_ROOT,
    filter_state: Optional[MarketBrowseState] = None,
) -> Message:
    """Send a fresh market message for direct commands like /market."""
    msg_context = extract_context(update)
    db = _get_db(context)
    if not db:
        text = "🏪 <b>Рынок временно недоступен</b>\n\nБаза данных не подключена."
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

    if screen == MARKET_VIEW_BUY:
        page = await db.get_market_listings_page(
            msg_context.user_id,
            update.effective_user.username if update.effective_user else None,
            filter_state or MarketBrowseState(),
        )
        sent_message = await update.effective_chat.send_message(
            text=_render_market_buy_text(_display_user(update), page),
            parse_mode="HTML",
            message_thread_id=msg_context.message_thread_id,
        )
        session_id = session_store.create_session(
            chat_id=msg_context.chat_id,
            message_id=sent_message.message_id,
            user_id=msg_context.user_id,
            message_thread_id=msg_context.message_thread_id,
            data=_market_buy_session_data(page),
        )
        await sent_message.edit_reply_markup(reply_markup=_build_market_buy_keyboard(session_id, page))
        return sent_message

    sent_message = await update.effective_chat.send_message(
        text=_render_market_root_text(_display_user(update)),
        parse_mode="HTML",
        message_thread_id=msg_context.message_thread_id,
    )
    session_id = session_store.create_session(
        chat_id=msg_context.chat_id,
        message_id=sent_message.message_id,
        user_id=msg_context.user_id,
        message_thread_id=msg_context.message_thread_id,
    )
    await sent_message.edit_reply_markup(reply_markup=_build_market_root_keyboard(session_id))
    return sent_message


async def market_handler(update: Update, context: ContextTypes.DEFAULT_TYPE, session: MenuSession) -> None:
    """Handle market root, buy browse, and card-entry branch screens."""
    query = update.callback_query
    callback_data = parse_callback_data(query.data)
    section = callback_data.section if callback_data else MARKET_ROUTE_ROOT
    db = _get_db(context)

    try:
        if section == MARKET_ROUTE_CARD_ENTRY:
            await _handle_market_card_entry(query, session)
            return

        if section == MARKET_ROUTE_START_SELL_PRICE:
            if not db:
                raise ValueError("Database is required for sell-price flow")
            await _handle_market_start_sell_price(query, session, db)
            return

        if section == MARKET_ROUTE_START_BUY_PRICE:
            if not db:
                raise ValueError("Database is required for buy-price flow")
            await _handle_market_start_buy_price(query, session, db)
            return

        if section == MARKET_ROUTE_CONFIRM_SELL:
            if not db:
                raise ValueError("Database is required for sell confirmation")
            await _handle_market_confirm_sell(query, context, session, db)
            return

        if section == MARKET_ROUTE_CONFIRM_BUY:
            if not db:
                raise ValueError("Database is required for buy confirmation")
            await _handle_market_confirm_buy(query, session, db)
            return

        if section == MARKET_ROUTE_CONFIRM_REQUEST:
            if not db:
                raise ValueError("Database is required for request confirmation")
            await _handle_market_confirm_request(query, session, db)
            return

        if section == MARKET_ROUTE_CONFIRM_FULFILL:
            if not db:
                raise ValueError("Database is required for request fulfillment")
            await _handle_market_confirm_fulfill(query, session, db)
            return

        if section in {MARKET_ROUTE_REMOVE_LISTING_1, MARKET_ROUTE_REMOVE_LISTING_2}:
            if not db:
                raise ValueError("Database is required for listing removal")
            await _handle_market_remove_listing(query, session, db, section)
            return

        if section in MARKET_CANCEL_REQUEST_ROUTES:
            if not db:
                raise ValueError("Database is required for request cancel")
            await _handle_market_cancel_request(query, session, db, section)
            return

        if section in MARKET_BUY_SELECT_ROUTES:
            if not db:
                raise ValueError("Database is required for buy selection")
            await _handle_market_buy_select(query, session, db, section)
            return

        if section in MARKET_FULFILL_REQUEST_ROUTES:
            if not db:
                raise ValueError("Database is required for request selection")
            await _handle_market_fulfill_select(query, session, db, section)
            return

        if section in {MARKET_ROUTE_ROOT, MARKET_ROUTE_BACK}:
            next_session_id = _create_session(session)
            await _edit_market_message(
                query,
                _render_market_root_text(_display_user(update)),
                _build_market_root_keyboard(next_session_id),
            )
            logger.info("market_root_rendered", user_id=session.user_id, session_id=next_session_id)
            return

        if not db:
            await _edit_market_message(
                query,
                "🏪 <b>Рынок временно недоступен</b>\n\nБаза данных не подключена.",
                build_back_button(_create_session(session)),
            )
            return

        if section in {
            MARKET_ROUTE_BUY,
            MARKET_ROUTE_SORT_NEWEST,
            MARKET_ROUTE_SORT_CHEAPEST,
            MARKET_ROUTE_AFFORDABLE,
            MARKET_ROUTE_BUY_PAGE_PREV,
            MARKET_ROUTE_BUY_PAGE_NEXT,
        } or section.startswith("mrr_"):
            await _handle_market_buy(query, context, session, db, section)
            return

        if section == MARKET_ROUTE_SELL:
            requests = await db.get_sellable_market_buy_requests(
                session.user_id,
                query.from_user.username if getattr(query, "from_user", None) else None,
            )
            next_session_id = session_store.create_session(
                chat_id=session.chat_id,
                message_id=session.message_id,
                user_id=session.user_id,
                message_thread_id=session.message_thread_id,
                data={
                    "market_sell_request_ids": [entry.request_id for entry in requests[:5]],
                    "market_sell_request_pokemon_ids": [entry.matching_user_pokemon_id for entry in requests[:5]],
                },
            )
            await _edit_market_message(
                query,
                _render_market_sell_requests_text(_display_user(update), requests),
                _build_market_sell_requests_keyboard(next_session_id, requests),
            )
            return

        if section == MARKET_ROUTE_MY_LISTINGS:
            listings = await db.get_my_market_listings(
                session.user_id,
                query.from_user.username if getattr(query, "from_user", None) else None,
            )
            next_session_id = session_store.create_session(
                chat_id=session.chat_id,
                message_id=session.message_id,
                user_id=session.user_id,
                message_thread_id=session.message_thread_id,
                data={"my_market_listings": [entry.listing_id for entry in listings[:2]]},
            )
            await _edit_market_message(
                query,
                _render_my_market_listings_text(_display_user(update), listings),
                _build_my_market_listings_keyboard(next_session_id, listings),
            )
            return

        if section == MARKET_ROUTE_MY_REQUESTS:
            requests = await db.get_my_market_buy_requests(
                session.user_id,
                query.from_user.username if getattr(query, "from_user", None) else None,
            )
            next_session_id = session_store.create_session(
                chat_id=session.chat_id,
                message_id=session.message_id,
                user_id=session.user_id,
                message_thread_id=session.message_thread_id,
                data={"my_market_request_ids": [entry.request_id for entry in requests[:5]]},
            )
            await _edit_market_message(
                query,
                _render_my_market_requests_text(_display_user(update), requests),
                _build_my_market_requests_keyboard(next_session_id, requests),
            )
            return

        next_session_id = _create_session(session)
        await _edit_market_message(
            query,
            _render_market_root_text(_display_user(update)),
            _build_market_root_keyboard(next_session_id),
        )

    except ShopError as e:
        logger.warning(
            "market_handler_error",
            section=section,
            error="market_rule",
            error_message=str(e),
            user_id=session.user_id,
        )
        await query.answer(f"⚠️ {e}", show_alert=False)
    except ValueError as e:
        logger.warning(
            "market_handler_error",
            section=section,
            error="stale_view",
            error_message=str(e),
            user_id=session.user_id,
        )
        await query.answer("⚠️ Экран устарел, откройте рынок заново.", show_alert=False)
    except BadRequest as e:
        logger.warning(
            "market_handler_error",
            section=section,
            error="bad_request",
            error_message=str(e),
            user_id=session.user_id,
            chat_id=session.chat_id,
        )
    except TelegramError as e:
        logger.error(
            "market_handler_error",
            section=section,
            error="telegram_api",
            error_message=str(e),
            user_id=session.user_id,
        )
    except Exception as e:
        logger.error(
            "market_handler_error",
            section=section,
            error="unexpected",
            error_message=str(e),
            user_id=session.user_id,
        )


async def _handle_market_buy(
    query,
    context: ContextTypes.DEFAULT_TYPE,
    session: MenuSession,
    db: Database,
    section: str,
) -> None:
    filter_state = MarketBrowseState.from_payload(session.data.get("market_buy_filters"))
    if section == MARKET_ROUTE_SORT_NEWEST:
        filter_state = MarketBrowseState(
            rarities=filter_state.rarities,
            affordable_only=filter_state.affordable_only,
            sort_mode=MARKET_SORT_NEWEST,
            page=1,
        )
    elif section == MARKET_ROUTE_SORT_CHEAPEST:
        filter_state = MarketBrowseState(
            rarities=filter_state.rarities,
            affordable_only=filter_state.affordable_only,
            sort_mode=MARKET_SORT_CHEAPEST,
            page=1,
        )
    elif section == MARKET_ROUTE_AFFORDABLE:
        filter_state = MarketBrowseState(
            rarities=filter_state.rarities,
            affordable_only=not filter_state.affordable_only,
            sort_mode=filter_state.sort_mode,
            page=1,
        )
    elif section == MARKET_ROUTE_BUY_PAGE_PREV:
        filter_state = filter_state.with_page(max(1, filter_state.page - 1))
    elif section == MARKET_ROUTE_BUY_PAGE_NEXT:
        filter_state = filter_state.with_page(filter_state.page + 1)
    elif section.startswith("mrr_"):
        rarity = MARKET_RARITY_CODES_REVERSE.get(section.removeprefix("mrr_"))
        if rarity:
            filter_state = _toggle_market_rarity(filter_state, rarity)

    page = await db.get_market_listings_page(
        session.user_id,
        query.from_user.username if getattr(query, "from_user", None) else None,
        filter_state,
    )
    next_session_id = session_store.create_session(
        chat_id=session.chat_id,
        message_id=session.message_id,
        user_id=session.user_id,
        message_thread_id=session.message_thread_id,
        data=_market_buy_session_data(page),
    )
    await _edit_market_message(
        query,
        _render_market_buy_text(query.from_user.first_name if getattr(query, "from_user", None) else "тренер", page),
        _build_market_buy_keyboard(next_session_id, page),
    )
    logger.info(
        "market_buy_rendered",
        user_id=session.user_id,
        session_id=next_session_id,
        page=page.current_page,
        total_entries=page.total_entries,
        sort_mode=page.filter_state.sort_mode,
        affordable_only=page.filter_state.affordable_only,
        rarities=page.filter_state.rarities,
    )


async def _handle_market_buy_select(
    query,
    session: MenuSession,
    db: Database,
    section: str,
) -> None:
    listing_ids = session.data.get("market_buy_listing_ids")
    if not isinstance(listing_ids, list):
        raise ValueError("Market buy listing ids are missing from session")
    index = MARKET_BUY_SELECT_ROUTES[section]
    if index >= len(listing_ids):
        raise ValueError("Requested market listing is unavailable")

    listing_id = int(listing_ids[index])
    page = await db.get_market_listings_page(
        session.user_id,
        query.from_user.username if getattr(query, "from_user", None) else None,
        MarketBrowseState.from_payload(session.data.get("market_buy_filters")),
    )
    selected = next((entry for entry in page.entries if entry.listing_id == listing_id), None)
    if not selected:
        raise ShopError("Этот лот уже недоступен.")

    confirmation_data = dict(session.data)
    confirmation_data["market_selected_listing_id"] = listing_id
    confirmation_data["market_selected_listing_price"] = selected.price
    next_session_id = session_store.create_session(
        chat_id=session.chat_id,
        message_id=session.message_id,
        user_id=session.user_id,
        message_thread_id=session.message_thread_id,
        data=confirmation_data,
    )
    await _edit_market_message(
        query,
        _render_market_buy_confirmation_text(selected, page.current_balance),
        _build_market_buy_confirmation_keyboard(next_session_id),
    )
    logger.info(
        "market_buy_selected",
        user_id=session.user_id,
        listing_id=listing_id,
        price=selected.price,
    )


async def _handle_market_confirm_buy(query, session: MenuSession, db: Database) -> None:
    listing_id = session.data.get("market_selected_listing_id")
    if listing_id is None:
        raise ValueError("Buy confirmation payload is missing")
    listing_price = session.data.get("market_selected_listing_price")
    precheck_error = await db.get_market_buy_listing_precheck_error(
        session.user_id,
        query.from_user.username if getattr(query, "from_user", None) else None,
        listing_id=int(listing_id),
    )
    if precheck_error:
        await query.answer(f"⚠️ {precheck_error}", show_alert=False)
        return
    if listing_price is not None and getattr(query, "from_user", None):
        shop_view = await db.get_shop_view(query.from_user.id, query.from_user.username)
        if shop_view.pokecoin_balance < int(listing_price):
            await query.answer("🪙 Не хватает pokecoin для покупки.", show_alert=False)
            return

    result = await db.purchase_market_listing(
        session.user_id,
        query.from_user.username if getattr(query, "from_user", None) else None,
        listing_id=int(listing_id),
    )
    next_session_id = _create_session(session)
    await _edit_market_message(
        query,
        "\n".join(
            [
                "✅ <b>Покупка завершена</b>",
                "",
                f"Покемон: <b>{result.listing.name}</b>",
                f"Цена: 🪙 <b>{result.price}</b>",
                f"Экземпляр: <code>{result.listing.user_pokemon_id}</code>",
            ]
        ),
        build_back_button(next_session_id),
    )
    logger.info(
        "market_buy_confirmed",
        user_id=session.user_id,
        listing_id=result.listing.listing_id,
        seller_user_id=result.seller_user_id,
        price=result.price,
    )


async def _handle_market_card_entry(query, session: MenuSession) -> None:
    """Open the first market branch directly from a pokemon card."""
    action = str(session.data.get("market_entry_action") or "")
    pokemon_id = session.data.get("market_entry_pokemon_id")
    pokemon_name = str(session.data.get("market_entry_pokemon_name") or "покемон")
    user_pokemon_id = session.data.get("market_entry_user_pokemon_id")
    if action not in {MARKET_CARD_ACTION_SELL, MARKET_CARD_ACTION_REQUEST} or pokemon_id is None:
        raise ValueError("Market card entry payload is missing")

    next_session_id = session_store.create_session(
        chat_id=session.chat_id,
        message_id=session.message_id,
        user_id=session.user_id,
        message_thread_id=session.message_thread_id,
        data=dict(session.data),
    )
    await _edit_market_message(
        query,
        _render_market_card_entry_text(
            action=action,
            pokemon_name=pokemon_name,
            pokemon_id=int(pokemon_id),
            user_pokemon_id=int(user_pokemon_id) if user_pokemon_id is not None else None,
        ),
        _build_market_card_entry_keyboard(next_session_id, action),
    )
    logger.info(
        "market_card_entry_opened",
        session_id=next_session_id,
        user_id=session.user_id,
        action=action,
        pokemon_id=int(pokemon_id),
        user_pokemon_id=user_pokemon_id,
    )


async def _handle_market_start_sell_price(query, session: MenuSession, db: Database) -> None:
    action = str(session.data.get("market_entry_action") or "")
    if action != MARKET_CARD_ACTION_SELL:
        raise ValueError("Sell-price flow requires owned pokemon entry")
    sell_block_reason = await _get_market_sell_block_reason(query, session, db)
    if sell_block_reason:
        await query.answer(f"⚠️ {sell_block_reason}", show_alert=False)
        return
    session_store.set_pending_input(
        action=MARKET_PENDING_ACTION_SELL_PRICE,
        chat_id=session.chat_id,
        user_id=session.user_id,
        source_message_id=session.message_id,
        source_message_thread_id=session.message_thread_id,
        data=dict(session.data),
    )
    next_session_id = _create_session(session)
    user_pokemon_id = session.data.get("market_entry_user_pokemon_id")
    await _edit_market_message(
        query,
        "\n".join(
            [
                "🏪 <b>Создание лота</b>",
                "",
                "Укажи цену командой:",
                f"<code>/sellprice \"цена\" {int(user_pokemon_id)}</code>" if user_pokemon_id is not None else "<code>/sellprice \"цена\" ID</code>",
                "",
                "После этого бот покажет короткое подтверждение.",
            ]
        ),
        build_back_button(next_session_id),
    )
    logger.info("market_sell_price_requested", session_id=next_session_id, user_id=session.user_id)


async def _handle_market_start_buy_price(query, session: MenuSession, db: Database) -> None:
    action = str(session.data.get("market_entry_action") or "")
    if action != MARKET_CARD_ACTION_REQUEST:
        raise ValueError("Buy-price flow requires request entry")
    request_block_reason = await _get_market_buy_request_block_reason(query, session, db)
    if request_block_reason:
        await query.answer(f"⚠️ {request_block_reason}", show_alert=False)
        return
    session_store.set_pending_input(
        action=MARKET_PENDING_ACTION_BUY_PRICE,
        chat_id=session.chat_id,
        user_id=session.user_id,
        source_message_id=session.message_id,
        source_message_thread_id=session.message_thread_id,
        data=dict(session.data),
    )
    next_session_id = _create_session(session)
    pokemon_id = session.data.get("market_entry_pokemon_id")
    await _edit_market_message(
        query,
        "\n".join(
            [
                "🏪 <b>Создание заявки</b>",
                "",
                "Укажи цену командой:",
                f"<code>/buyprice \"цена\" {int(pokemon_id)}</code>" if pokemon_id is not None else "<code>/buyprice \"цена\" ID</code>",
                "",
                "После этого бот покажет короткое подтверждение.",
            ]
        ),
        build_back_button(next_session_id),
    )
    logger.info("market_buy_price_requested", session_id=next_session_id, user_id=session.user_id)


async def handle_market_price_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    *,
    action: str,
) -> None:
    """Handle command-based market price input."""
    if not update.effective_chat or not update.effective_user or not update.effective_message:
        return

    db = _get_db(context)
    if not db:
        await update.effective_chat.send_message(
            "🏪 Рынок временно недоступен.",
            message_thread_id=getattr(update.effective_message, "message_thread_id", None),
        )
        return

    command_text = update.effective_message.text or ""
    parts = command_text.split(maxsplit=2)
    if len(parts) < 3 or not parts[1].strip().isdigit() or not parts[2].strip().isdigit():
        usage = (
            "/sellprice \"цена\" 1234"
            if action == MARKET_PENDING_ACTION_SELL_PRICE
            else "/buyprice \"цена\" 25"
        )
        await update.effective_chat.send_message(
            f"⚠️ Использование: <code>{usage}</code>",
            parse_mode="HTML",
            message_thread_id=getattr(update.effective_message, "message_thread_id", None),
        )
        return

    price = int(parts[1].strip())
    target_id = int(parts[2].strip())
    if price <= 0:
        await update.effective_chat.send_message(
            "⚠️ Цена должна быть больше нуля.",
            message_thread_id=getattr(update.effective_message, "message_thread_id", None),
        )
        return

    pending = session_store.get_pending_input(chat_id=update.effective_chat.id, user_id=update.effective_user.id)

    if action == MARKET_PENDING_ACTION_SELL_PRICE:
        await _handle_market_sell_price_input(update, context, db, pending, price, target_id)
        return

    if action == MARKET_PENDING_ACTION_BUY_PRICE:
        await _handle_market_buy_price_input(update, context, db, pending, price, target_id)
        return

    await update.effective_chat.send_message(
        "⚠️ Рыночный ввод устарел. Откройте карточку покемона заново.",
        message_thread_id=getattr(update.effective_message, "message_thread_id", None),
    )


async def _handle_market_sell_price_input(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    db: Database,
    pending: PendingInput | None,
    price: int,
    user_pokemon_id: int,
) -> None:
    if pending:
        session_store.clear_pending_input(chat_id=update.effective_chat.id, user_id=update.effective_user.id)

    entry = await db.get_user_pokemon_entry(user_pokemon_id)
    if not entry:
        await update.effective_chat.send_message(
            "⚠️ Экземпляр покемона не найден.",
            message_thread_id=getattr(update.effective_message, "message_thread_id", None),
        )
        return
    sell_block_reason = await _get_market_sell_block_reason_from_context(
        update,
        db,
        user_pokemon_id=user_pokemon_id,
    )
    if sell_block_reason:
        await update.effective_chat.send_message(
            f"⚠️ {sell_block_reason}",
            message_thread_id=getattr(update.effective_message, "message_thread_id", None),
        )
        return

    shop_view = await db.get_shop_view(update.effective_user.id, update.effective_user.username)
    commission = _calculate_sale_commission(price)
    enough_for_commission = shop_view.pokecoin_balance >= commission
    confirmation_data = build_market_entry_payload(
        action=resolve_market_card_action(True),
        pokemon_id=entry.pokemon_id,
        pokemon_name=entry.name,
        user_pokemon_id=entry.sample_user_pokemon_id,
    )
    confirmation_data["market_sell_price"] = price
    confirmation_text = _render_market_sell_confirmation_text(
        pokemon_name=entry.name,
        pokemon_id=entry.pokemon_id,
        user_pokemon_id=entry.sample_user_pokemon_id,
        price=price,
        commission=commission,
        balance=shop_view.pokecoin_balance,
        enough_for_commission=enough_for_commission,
    )
    if pending and pending.action == MARKET_PENDING_ACTION_SELL_PRICE and int(pending.data.get("market_entry_user_pokemon_id") or -1) == user_pokemon_id:
        confirmation_session_id = session_store.create_session(
            chat_id=pending.chat_id,
            message_id=int(pending.source_message_id),
            user_id=pending.user_id,
            message_thread_id=pending.source_message_thread_id,
            data=confirmation_data,
        )
        await _edit_market_message_by_ids(
            context,
            pending,
            confirmation_text,
            _build_market_sell_confirmation_keyboard(confirmation_session_id),
        )
    else:
        sent_message = await update.effective_chat.send_message(
            text=confirmation_text,
            parse_mode="HTML",
            message_thread_id=getattr(update.effective_message, "message_thread_id", None),
        )
        confirmation_session_id = session_store.create_session(
            chat_id=update.effective_chat.id,
            message_id=sent_message.message_id,
            user_id=update.effective_user.id,
            message_thread_id=getattr(update.effective_message, "message_thread_id", None),
            data=confirmation_data,
        )
        await sent_message.edit_reply_markup(reply_markup=_build_market_sell_confirmation_keyboard(confirmation_session_id))
    await update.effective_chat.send_message(
        "✅ Цена принята. Подтвердите создание лота в карточке выше.",
        message_thread_id=getattr(update.effective_message, "message_thread_id", None),
    )


async def _handle_market_confirm_sell(
    query,
    context: ContextTypes.DEFAULT_TYPE,
    session: MenuSession,
    db: Database,
) -> None:
    pokemon_name = str(session.data.get("market_entry_pokemon_name") or "покемон")
    user_pokemon_id = session.data.get("market_entry_user_pokemon_id")
    price = session.data.get("market_sell_price")
    if user_pokemon_id is None or price is None:
        raise ValueError("Sell confirmation payload is missing")

    result = await db.create_market_listing(
        session.user_id,
        query.from_user.username if getattr(query, "from_user", None) else None,
        user_pokemon_id=int(user_pokemon_id),
        price=int(price),
    )
    next_session_id = _create_session(session)
    await _edit_market_message(
        query,
        "\n".join(
            [
                "✅ <b>Лот создан</b>",
                "",
                f"Покемон: <b>{pokemon_name}</b>",
                f"Цена: 🪙 <b>{result.price}</b>",
                f"Лот ID: <code>{result.listing_id}</code>",
                f"Дней жизни: <b>{result.days_remaining}</b>",
            ]
        ),
        build_back_button(next_session_id),
    )
    logger.info(
        "market_sell_confirmed",
        user_id=session.user_id,
        listing_id=result.listing_id,
        user_pokemon_id=result.user_pokemon_id,
        price=result.price,
    )


async def _handle_market_buy_price_input(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    db: Database,
    pending: PendingInput | None,
    price: int,
    pokemon_id: int,
) -> None:
    if pending:
        session_store.clear_pending_input(chat_id=update.effective_chat.id, user_id=update.effective_user.id)

    entry = await db.get_pokemon_catalog_entry(pokemon_id)
    if not entry:
        await update.effective_chat.send_message(
            "⚠️ Покемон не найден.",
            message_thread_id=getattr(update.effective_message, "message_thread_id", None),
        )
        return
    request_block_reason = await _get_market_buy_request_block_reason_from_context(
        update,
        db,
        pokemon_id=pokemon_id,
    )
    if request_block_reason:
        await update.effective_chat.send_message(
            f"⚠️ {request_block_reason}",
            message_thread_id=getattr(update.effective_message, "message_thread_id", None),
        )
        return

    shop_view = await db.get_shop_view(update.effective_user.id, update.effective_user.username)
    enough_for_request = shop_view.pokecoin_balance >= price
    confirmation_data = build_market_entry_payload(
        action=resolve_market_card_action(False),
        pokemon_id=entry.pokemon_id,
        pokemon_name=entry.name,
    )
    confirmation_data["market_buy_price"] = price
    confirmation_text = _render_market_buy_request_confirmation_text(
        pokemon_name=entry.name,
        pokemon_id=entry.pokemon_id,
        price=price,
        balance=shop_view.pokecoin_balance,
        enough_for_request=enough_for_request,
    )
    if pending and pending.action == MARKET_PENDING_ACTION_BUY_PRICE and int(pending.data.get("market_entry_pokemon_id") or -1) == pokemon_id:
        confirmation_session_id = session_store.create_session(
            chat_id=pending.chat_id,
            message_id=int(pending.source_message_id),
            user_id=pending.user_id,
            message_thread_id=pending.source_message_thread_id,
            data=confirmation_data,
        )
        await _edit_market_message_by_ids(
            context,
            pending,
            confirmation_text,
            _build_market_buy_request_confirmation_keyboard(confirmation_session_id),
        )
    else:
        sent_message = await update.effective_chat.send_message(
            text=confirmation_text,
            parse_mode="HTML",
            message_thread_id=getattr(update.effective_message, "message_thread_id", None),
        )
        confirmation_session_id = session_store.create_session(
            chat_id=update.effective_chat.id,
            message_id=sent_message.message_id,
            user_id=update.effective_user.id,
            message_thread_id=getattr(update.effective_message, "message_thread_id", None),
            data=confirmation_data,
        )
        await sent_message.edit_reply_markup(reply_markup=_build_market_buy_request_confirmation_keyboard(confirmation_session_id))
    await update.effective_chat.send_message(
        "✅ Цена принята. Подтвердите создание заявки в карточке выше.",
        message_thread_id=getattr(update.effective_message, "message_thread_id", None),
    )


async def _handle_market_confirm_request(query, session: MenuSession, db: Database) -> None:
    pokemon_id = session.data.get("market_entry_pokemon_id")
    pokemon_name = str(session.data.get("market_entry_pokemon_name") or "покемон")
    price = session.data.get("market_buy_price")
    if pokemon_id is None or price is None:
        raise ValueError("Buy-request confirmation payload is missing")

    result = await db.create_market_buy_request(
        session.user_id,
        query.from_user.username if getattr(query, "from_user", None) else None,
        pokemon_id=int(pokemon_id),
        price=int(price),
    )
    next_session_id = _create_session(session)
    await _edit_market_message(
        query,
        "\n".join(
            [
                "✅ <b>Заявка создана</b>",
                "",
                f"Покемон: <b>{pokemon_name}</b>",
                f"Цена: 🪙 <b>{result.price}</b>",
                f"Заявка ID: <code>{result.request_id}</code>",
            ]
        ),
        build_back_button(next_session_id),
    )
    logger.info(
        "market_request_confirmed",
        user_id=session.user_id,
        request_id=result.request_id,
        pokemon_id=result.pokemon_id,
        price=result.price,
    )


async def _handle_market_remove_listing(query, session: MenuSession, db: Database, section: str) -> None:
    listing_ids = session.data.get("my_market_listings")
    if not isinstance(listing_ids, list):
        raise ValueError("My listings session data is missing")
    index = 0 if section == MARKET_ROUTE_REMOVE_LISTING_1 else 1
    if index >= len(listing_ids):
        raise ValueError("Listing removal target is unavailable")
    listing_id = int(listing_ids[index])
    await db.remove_market_listing(
        session.user_id,
        query.from_user.username if getattr(query, "from_user", None) else None,
        listing_id=listing_id,
    )
    refreshed = await db.get_my_market_listings(
        session.user_id,
        query.from_user.username if getattr(query, "from_user", None) else None,
    )
    next_session_id = session_store.create_session(
        chat_id=session.chat_id,
        message_id=session.message_id,
        user_id=session.user_id,
        message_thread_id=session.message_thread_id,
        data={"my_market_listings": [entry.listing_id for entry in refreshed[:2]]},
    )
    await _edit_market_message(
        query,
        _render_my_market_listings_text(
            query.from_user.first_name if getattr(query, "from_user", None) else "тренер",
            refreshed,
        ),
        _build_my_market_listings_keyboard(next_session_id, refreshed),
    )
    logger.info("market_listing_removed_from_ui", user_id=session.user_id, listing_id=listing_id)


async def _handle_market_cancel_request(query, session: MenuSession, db: Database, section: str) -> None:
    request_ids = session.data.get("my_market_request_ids")
    if not isinstance(request_ids, list):
        raise ValueError("My request ids are missing")
    index = MARKET_CANCEL_REQUEST_ROUTES[section]
    if index >= len(request_ids):
        raise ValueError("Request removal target is unavailable")
    request_id = int(request_ids[index])
    await db.cancel_market_buy_request(
        session.user_id,
        query.from_user.username if getattr(query, "from_user", None) else None,
        request_id=request_id,
    )
    refreshed = await db.get_my_market_buy_requests(
        session.user_id,
        query.from_user.username if getattr(query, "from_user", None) else None,
    )
    next_session_id = session_store.create_session(
        chat_id=session.chat_id,
        message_id=session.message_id,
        user_id=session.user_id,
        message_thread_id=session.message_thread_id,
        data={"my_market_request_ids": [entry.request_id for entry in refreshed[:5]]},
    )
    await _edit_market_message(
        query,
        _render_my_market_requests_text(
            query.from_user.first_name if getattr(query, "from_user", None) else "тренер",
            refreshed,
        ),
        _build_my_market_requests_keyboard(next_session_id, refreshed),
    )
    logger.info("market_request_canceled_from_ui", user_id=session.user_id, request_id=request_id)


async def _handle_market_fulfill_select(query, session: MenuSession, db: Database, section: str) -> None:
    request_ids = session.data.get("market_sell_request_ids")
    pokemon_ids = session.data.get("market_sell_request_pokemon_ids")
    if not isinstance(request_ids, list) or not isinstance(pokemon_ids, list):
        raise ValueError("Sell-request session data is missing")
    index = MARKET_FULFILL_REQUEST_ROUTES[section]
    if index >= len(request_ids) or index >= len(pokemon_ids):
        raise ValueError("Request fulfillment target is unavailable")

    request_id = int(request_ids[index])
    requests = await db.get_sellable_market_buy_requests(
        session.user_id,
        query.from_user.username if getattr(query, "from_user", None) else None,
    )
    selected = next((entry for entry in requests if entry.request_id == request_id), None)
    if not selected or selected.matching_user_pokemon_id is None:
        raise ShopError("Эта заявка уже недоступна.")

    confirmation_data = dict(session.data)
    confirmation_data["market_selected_request_id"] = request_id
    confirmation_data["market_selected_request_pokemon_id"] = int(selected.matching_user_pokemon_id)
    next_session_id = session_store.create_session(
        chat_id=session.chat_id,
        message_id=session.message_id,
        user_id=session.user_id,
        message_thread_id=session.message_thread_id,
        data=confirmation_data,
    )
    await _edit_market_message(
        query,
        _render_market_fulfill_confirmation_text(selected, int(selected.matching_user_pokemon_id)),
        _build_market_fulfill_confirmation_keyboard(next_session_id),
    )
    logger.info("market_request_selected_for_fulfill", user_id=session.user_id, request_id=request_id)


async def _handle_market_confirm_fulfill(query, session: MenuSession, db: Database) -> None:
    request_id = session.data.get("market_selected_request_id")
    user_pokemon_id = session.data.get("market_selected_request_pokemon_id")
    if request_id is None or user_pokemon_id is None:
        raise ValueError("Fulfillment confirmation payload is missing")
    precheck_error = await db.get_market_request_fulfill_precheck_error(
        session.user_id,
        query.from_user.username if getattr(query, "from_user", None) else None,
        request_id=int(request_id),
        user_pokemon_id=int(user_pokemon_id),
    )
    if precheck_error:
        await query.answer(f"⚠️ {precheck_error}", show_alert=False)
        return

    result = await db.fulfill_market_buy_request(
        session.user_id,
        query.from_user.username if getattr(query, "from_user", None) else None,
        request_id=int(request_id),
        user_pokemon_id=int(user_pokemon_id),
    )
    next_session_id = _create_session(session)
    await _edit_market_message(
        query,
        "\n".join(
            [
                "✅ <b>Заявка закрыта</b>",
                "",
                f"Покемон: <b>{escape_html(result.request.name)}</b>",
                f"Цена: 🪙 <b>{result.price}</b>",
                f"Экземпляр: <code>{result.transferred_user_pokemon_id}</code>",
            ]
        ),
        build_back_button(next_session_id),
    )
    logger.info(
        "market_request_fulfilled_from_ui",
        user_id=session.user_id,
        request_id=result.request.request_id,
        user_pokemon_id=result.transferred_user_pokemon_id,
    )


def _render_market_card_entry_text(
    *,
    action: str,
    pokemon_name: str,
    pokemon_id: int,
    user_pokemon_id: int | None,
) -> str:
    if action == MARKET_CARD_ACTION_SELL:
        lines = [
            "🏪 <b>Рынок</b>",
            "",
            f"Вы готовите продажу покемона <b>{escape_html(pokemon_name)}</b> <code>#{pokemon_id}</code>.",
            (f"Экземпляр: <code>{user_pokemon_id}</code>" if user_pokemon_id is not None else ""),
            "",
            "Следующий шаг для этого сценария: создание лота на продажу.",
        ]
    else:
        lines = [
            "🏪 <b>Рынок</b>",
            "",
            f"Вы готовите заявку на покупку покемона <b>{escape_html(pokemon_name)}</b> <code>#{pokemon_id}</code>.",
            "",
            "Следующий шаг для этого сценария: создание заявки на покупку.",
        ]
    return "\n".join(line for line in lines if line)


def _render_market_sell_confirmation_text(
    *,
    pokemon_name: str,
    pokemon_id: int,
    user_pokemon_id: int,
    price: int,
    commission: int,
    balance: int,
    enough_for_commission: bool,
) -> str:
    return "\n".join(
        [
            "🏪 <b>Подтверждение лота</b>",
            "",
            f"Покемон: <b>{escape_html(pokemon_name)}</b> <code>#{pokemon_id}</code>",
            f"Экземпляр: <code>{user_pokemon_id}</code>",
            f"Цена: 🪙 <b>{price}</b>",
            f"Стартовая комиссия: 🪙 <b>{commission}</b>",
            f"Ваш баланс: 🪙 <b>{balance}</b>",
            f"Хватает на стартовую комиссию: <b>{'да' if enough_for_commission else 'нет'}</b>",
        ]
    )


def _render_market_buy_confirmation_text(entry: MarketListingSummary, current_balance: int) -> str:
    return "\n".join(
        [
            "🏪 <b>Подтверждение покупки</b>",
            "",
            f"Покемон: <b>{escape_html(entry.name)}</b> <code>#{entry.pokemon_id}</code>",
            f"Экземпляр: <code>{entry.user_pokemon_id}</code>",
            f"Продавец: <b>{escape_html(entry.seller_label or 'тренер')}</b>",
            f"Цена: 🪙 <b>{entry.price}</b>",
            f"Ваш баланс: 🪙 <b>{current_balance}</b>",
            f"Хватает на покупку: <b>{'да' if current_balance >= entry.price else 'нет'}</b>",
        ]
    )


def _render_market_root_text(user_label: str) -> str:
    return "\n".join(
        [
            f"🏪 <b>{escape_html(user_label)}, рынок открыт</b>",
            "",
            "Здесь можно покупать покемонов за <b>pokecoin</b>,",
            "закрывать чужие заявки и управлять своими лотами.",
            "",
            "Выберите раздел ниже.",
        ]
    )


def _render_market_buy_text(user_label: str, page: MarketBrowsePage) -> str:
    lines = [
        f"🏪 <b>{escape_html(user_label)}, активные лоты</b> <code>({page.current_page}/{page.total_pages})</code>",
        "",
    ]
    if page.entries:
        for index, entry in enumerate(page.entries, start=1):
            lines.append(_render_market_listing_line(index, entry))
    else:
        lines.append("Пока нет активных лотов под текущие фильтры.")
    lines.extend(
        [
            "",
            f"Баланс: 🪙 <b>{page.current_balance}</b>",
            f"Найдено лотов: <b>{page.total_entries}</b>",
            f"Сортировка: <b>{'сначала дешёвые' if page.filter_state.sort_mode == MARKET_SORT_CHEAPEST else 'сначала новые'}</b>",
            (
                f"Редкости: <b>{escape_html(', '.join(page.filter_state.rarities))}</b>"
                if page.filter_state.rarities
                else "Редкости: <b>все</b>"
            ),
            f"Только хватает: <b>{'да' if page.filter_state.affordable_only else 'нет'}</b>",
        ]
    )
    return "\n".join(lines)


def _render_market_listing_line(index: int, entry: MarketListingSummary) -> str:
    rarity_marker = {
        "Legendary": "🟠",
        "Epic": "🟣",
        "Rare": "🟢",
        "Common": "⚪️",
    }.get(entry.rarity, "⚪️")
    seller = escape_html(entry.seller_label or "тренер")
    return (
        f"<b>{index}.</b> {rarity_marker} <b>{escape_html(entry.name)}</b> "
        f"[id: {entry.pokemon_id}] | экз: {entry.user_pokemon_id} | 🪙 <b>{entry.price}</b> | {seller}"
    )


def _render_my_market_listings_text(user_label: str, listings: list[MarketListingSummary]) -> str:
    lines = [f"📦 <b>{escape_html(user_label)}, ваши лоты</b>", ""]
    if not listings:
        lines.append("У вас пока нет активных лотов.")
    else:
        for index, entry in enumerate(listings, start=1):
            rarity_marker = _market_rarity_marker(entry.rarity)
            lines.append(
                f"{index}. {rarity_marker} <b>{escape_html(entry.name)}</b> [id: {entry.pokemon_id}] | "
                f"экз: {entry.user_pokemon_id} | 🪙 <b>{entry.price}</b> | дней осталось: <b>{entry.days_remaining}</b>"
            )
    return "\n".join(lines)


def _render_my_market_requests_text(user_label: str, requests: list[MarketBuyRequestSummary]) -> str:
    lines = [f"🧾 <b>{escape_html(user_label)}, ваши заявки</b>", ""]
    if not requests:
        lines.append("У вас пока нет активных заявок.")
    else:
        for index, entry in enumerate(requests, start=1):
            rarity_marker = {
                "Legendary": "🟠",
                "Epic": "🟣",
                "Rare": "🟢",
                "Common": "⚪️",
            }.get(entry.rarity, "⚪️")
            lines.append(
                f"{index}. {rarity_marker} <b>{escape_html(entry.name)}</b> [id: {entry.pokemon_id}] | 🪙 <b>{entry.price}</b>"
            )
    return "\n".join(lines)


def _build_market_root_keyboard(session_id: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("🛒 Купить", callback_data=f"menu:{MARKET_ROUTE_BUY}:{session_id}"),
                InlineKeyboardButton("📤 Продать", callback_data=f"menu:{MARKET_ROUTE_SELL}:{session_id}"),
            ],
            [
                InlineKeyboardButton("📦 Мои лоты", callback_data=f"menu:{MARKET_ROUTE_MY_LISTINGS}:{session_id}"),
                InlineKeyboardButton("🧾 Мои заявки", callback_data=f"menu:{MARKET_ROUTE_MY_REQUESTS}:{session_id}"),
            ],
            [
                InlineKeyboardButton("🔙 Назад", callback_data=f"menu:back:{session_id}"),
            ],
        ]
    )


def _build_market_card_entry_keyboard(session_id: str, action: str) -> InlineKeyboardMarkup:
    if action == MARKET_CARD_ACTION_SELL:
        return InlineKeyboardMarkup(
            [
                [InlineKeyboardButton("🪙 Указать цену", callback_data=f"menu:{MARKET_ROUTE_START_SELL_PRICE}:{session_id}")],
                [InlineKeyboardButton("🔙 Назад", callback_data=f"menu:back:{session_id}")],
            ]
        )
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("🪙 Указать цену", callback_data=f"menu:{MARKET_ROUTE_START_BUY_PRICE}:{session_id}")],
            [InlineKeyboardButton("🔙 Назад", callback_data=f"menu:back:{session_id}")],
        ]
    )


def _build_market_sell_confirmation_keyboard(session_id: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("✅ Подтвердить", callback_data=f"menu:{MARKET_ROUTE_CONFIRM_SELL}:{session_id}")],
            [InlineKeyboardButton("❌ Отмена", callback_data=f"menu:{MARKET_ROUTE_ROOT}:{session_id}")],
        ]
    )


def _build_market_buy_confirmation_keyboard(session_id: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("✅ Купить", callback_data=f"menu:{MARKET_ROUTE_CONFIRM_BUY}:{session_id}")],
            [InlineKeyboardButton("❌ Отмена", callback_data=f"menu:{MARKET_ROUTE_BUY}:{session_id}")],
        ]
    )


def _build_market_buy_keyboard(session_id: str, page: MarketBrowsePage) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []
    if page.entries:
        for index in range(0, len(page.entries), 5):
            row = []
            for entry_index, _entry in enumerate(page.entries[index:index + 5], start=index + 1):
                route = list(MARKET_BUY_SELECT_ROUTES.keys())[entry_index - 1]
                row.append(InlineKeyboardButton(str(entry_index), callback_data=f"menu:{route}:{session_id}"))
            rows.append(row)
    rows.append(
        [
            _build_market_toggle_button(
                f"{_market_rarity_marker(rarity)} {rarity}",
                rarity in page.filter_state.rarities,
                f"menu:mrr_{MARKET_RARITY_CODES[rarity]}:{session_id}",
            )
            for rarity in MARKET_RARITY_OPTIONS
        ]
    )
    rows.append(
        [
            _build_market_toggle_button(
                "🪙 Только хватает",
                page.filter_state.affordable_only,
                f"menu:{MARKET_ROUTE_AFFORDABLE}:{session_id}",
            )
        ]
    )
    rows.append(
        [
            _build_market_toggle_button(
                "🆕 Новые",
                page.filter_state.sort_mode == MARKET_SORT_NEWEST,
                f"menu:{MARKET_ROUTE_SORT_NEWEST}:{session_id}",
            ),
            _build_market_toggle_button(
                "🪙 Дешёвые",
                page.filter_state.sort_mode == MARKET_SORT_CHEAPEST,
                f"menu:{MARKET_ROUTE_SORT_CHEAPEST}:{session_id}",
            ),
        ]
    )
    nav_row: list[InlineKeyboardButton] = []
    if page.has_previous():
        nav_row.append(InlineKeyboardButton("⬅️", callback_data=f"menu:{MARKET_ROUTE_BUY_PAGE_PREV}:{session_id}"))
    nav_row.append(InlineKeyboardButton("🔙 Назад", callback_data=f"menu:{MARKET_ROUTE_ROOT}:{session_id}"))
    if page.has_next():
        nav_row.append(InlineKeyboardButton("➡️", callback_data=f"menu:{MARKET_ROUTE_BUY_PAGE_NEXT}:{session_id}"))
    rows.append(nav_row)
    return InlineKeyboardMarkup(rows)


def _build_my_market_listings_keyboard(session_id: str, listings: list[MarketListingSummary]) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []
    for index, _entry in enumerate(listings[:2], start=1):
        route = MARKET_ROUTE_REMOVE_LISTING_1 if index == 1 else MARKET_ROUTE_REMOVE_LISTING_2
        rows.append([InlineKeyboardButton(f"❌ Снять лот #{index}", callback_data=f"menu:{route}:{session_id}")])
    rows.append([InlineKeyboardButton("🔙 Назад", callback_data=f"menu:{MARKET_ROUTE_ROOT}:{session_id}")])
    return InlineKeyboardMarkup(rows)


def _render_market_buy_request_confirmation_text(
    *,
    pokemon_name: str,
    pokemon_id: int,
    price: int,
    balance: int,
    enough_for_request: bool,
) -> str:
    return "\n".join(
        [
            "🏪 <b>Подтверждение заявки</b>",
            "",
            f"Покемон: <b>{escape_html(pokemon_name)}</b> <code>#{pokemon_id}</code>",
            f"Цена заявки: 🪙 <b>{price}</b>",
            f"Ваш баланс: 🪙 <b>{balance}</b>",
            f"Хватает на резерв: <b>{'да' if enough_for_request else 'нет'}</b>",
        ]
    )


def _build_market_buy_request_confirmation_keyboard(session_id: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("✅ Подтвердить", callback_data=f"menu:{MARKET_ROUTE_CONFIRM_REQUEST}:{session_id}")],
            [InlineKeyboardButton("❌ Отмена", callback_data=f"menu:{MARKET_ROUTE_ROOT}:{session_id}")],
        ]
    )


def _render_market_sell_requests_text(user_label: str, requests: list[MarketBuyRequestSummary]) -> str:
    lines = [f"📤 <b>{escape_html(user_label)}, доступные заявки</b>", ""]
    if not requests:
        lines.append("Сейчас нет чужих заявок, которые вы можете закрыть.")
    else:
        for index, entry in enumerate(requests, start=1):
            rarity_marker = _market_rarity_marker(entry.rarity)
            lines.append(
                f"{index}. {rarity_marker} <b>{escape_html(entry.name)}</b> [id: {entry.pokemon_id}] | "
                f"🪙 <b>{entry.price}</b> | покупатель: <b>{escape_html(entry.requester_label or 'тренер')}</b>"
            )
    return "\n".join(lines)


def _build_market_sell_requests_keyboard(session_id: str, requests: list[MarketBuyRequestSummary]) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []
    for index, _entry in enumerate(requests[:5], start=1):
        route = list(MARKET_FULFILL_REQUEST_ROUTES.keys())[index - 1]
        rows.append([InlineKeyboardButton(f"✅ Закрыть заявку #{index}", callback_data=f"menu:{route}:{session_id}")])
    rows.append([InlineKeyboardButton("🔙 Назад", callback_data=f"menu:{MARKET_ROUTE_ROOT}:{session_id}")])
    return InlineKeyboardMarkup(rows)


def _build_my_market_requests_keyboard(session_id: str, requests: list[MarketBuyRequestSummary]) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []
    for index, _entry in enumerate(requests[:5], start=1):
        route = list(MARKET_CANCEL_REQUEST_ROUTES.keys())[index - 1]
        rows.append([InlineKeyboardButton(f"❌ Снять заявку #{index}", callback_data=f"menu:{route}:{session_id}")])
    rows.append([InlineKeyboardButton("🔙 Назад", callback_data=f"menu:{MARKET_ROUTE_ROOT}:{session_id}")])
    return InlineKeyboardMarkup(rows)


def _render_market_fulfill_confirmation_text(entry: MarketBuyRequestSummary, user_pokemon_id: int) -> str:
    return "\n".join(
        [
            "🏪 <b>Подтверждение продажи по заявке</b>",
            "",
            f"Покемон: <b>{escape_html(entry.name)}</b> <code>#{entry.pokemon_id}</code>",
            f"Ваш экземпляр: <code>{user_pokemon_id}</code>",
            f"Покупатель: <b>{escape_html(entry.requester_label or 'тренер')}</b>",
            f"Цена: 🪙 <b>{entry.price}</b>",
        ]
    )


def _build_market_fulfill_confirmation_keyboard(session_id: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("✅ Подтвердить", callback_data=f"menu:{MARKET_ROUTE_CONFIRM_FULFILL}:{session_id}")],
            [InlineKeyboardButton("❌ Отмена", callback_data=f"menu:{MARKET_ROUTE_SELL}:{session_id}")],
        ]
    )


def _market_rarity_marker(rarity: str) -> str:
    return {
        "Legendary": "🟠",
        "Epic": "🟣",
        "Rare": "🟢",
        "Common": "⚪️",
    }.get(rarity, "⚪️")


def _build_market_toggle_button(text: str, enabled: bool, callback_data: str) -> InlineKeyboardButton:
    prefix = "✅ " if enabled else ""
    return InlineKeyboardButton(f"{prefix}{text}", callback_data=callback_data)


def _calculate_sale_commission(price: int) -> int:
    return max(1, int(price * 0.01))


def _toggle_market_rarity(filter_state: MarketBrowseState, rarity: str) -> MarketBrowseState:
    rarities = list(filter_state.rarities)
    if rarity in rarities:
        rarities.remove(rarity)
    else:
        rarities.append(rarity)
    ordered = tuple(option for option in MARKET_RARITY_OPTIONS if option in rarities)
    return MarketBrowseState(
        rarities=ordered,
        affordable_only=filter_state.affordable_only,
        sort_mode=filter_state.sort_mode,
        page=1,
    )


def _market_buy_session_data(page: MarketBrowsePage) -> dict[str, object]:
    return {
        "market_screen": MARKET_VIEW_BUY,
        "market_buy_filters": page.filter_state.to_session_payload(),
        "market_buy_listing_ids": [entry.listing_id for entry in page.entries],
    }


def _create_session(session: MenuSession) -> str:
    return session_store.create_session(
        chat_id=session.chat_id,
        message_id=session.message_id,
        user_id=session.user_id,
        message_thread_id=session.message_thread_id,
        data=dict(session.data),
    )


async def _edit_market_message(query, text: str, reply_markup: InlineKeyboardMarkup) -> None:
    message = getattr(query, "message", None)
    if getattr(message, "photo", None):
        await query.edit_message_caption(caption=text, parse_mode="HTML", reply_markup=reply_markup)
    else:
        await query.edit_message_text(text=text, parse_mode="HTML", reply_markup=reply_markup)


async def _edit_market_message_by_ids(
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


def _display_user(update: Optional[Update]) -> str:
    if update and update.effective_user:
        return display_name(
            getattr(update.effective_user, "username", None),
            getattr(update.effective_user, "first_name", None),
        )
    return "тренер"


async def _get_market_sell_block_reason(query, session: MenuSession, db: Database) -> str | None:
    username = getattr(getattr(query, "from_user", None), "username", None)
    user_pokemon_id = session.data.get("market_entry_user_pokemon_id")
    if user_pokemon_id is None:
        return "Нельзя создать лот: экран устарел."
    return await db.get_market_sell_precheck_error(
        session.user_id,
        username,
        user_pokemon_id=int(user_pokemon_id),
    )


async def _get_market_buy_request_block_reason(query, session: MenuSession, db: Database) -> str | None:
    username = getattr(getattr(query, "from_user", None), "username", None)
    pokemon_id = session.data.get("market_entry_pokemon_id")
    if pokemon_id is None:
        return "Нельзя создать заявку: экран устарел."
    return await db.get_market_buy_request_precheck_error(
        session.user_id,
        username,
        pokemon_id=int(pokemon_id),
    )


async def _get_market_sell_block_reason_from_context(
    update: Update,
    db: Database,
    *,
    user_pokemon_id: int,
) -> str | None:
    if not update.effective_user:
        return "Рынок временно недоступен."
    return await db.get_market_sell_precheck_error(
        update.effective_user.id,
        update.effective_user.username,
        user_pokemon_id=user_pokemon_id,
    )


async def _get_market_buy_request_block_reason_from_context(
    update: Update,
    db: Database,
    *,
    pokemon_id: int,
) -> str | None:
    if not update.effective_user:
        return "Рынок временно недоступен."
    return await db.get_market_buy_request_precheck_error(
        update.effective_user.id,
        update.effective_user.username,
        pokemon_id=pokemon_id,
    )


def _get_db(context: ContextTypes.DEFAULT_TYPE) -> Optional[Database]:
    application = getattr(context, "application", None)
    if not application or not hasattr(application, "bot_data"):
        return None
    bot_data = getattr(application, "bot_data", None)
    if not isinstance(bot_data, dict):
        return None
    db = bot_data.get("db")
    if not db or not hasattr(db, "get_market_listings_page"):
        return None
    return db
