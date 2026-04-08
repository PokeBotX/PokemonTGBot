"""Command handlers for /start, /menu, and direct section shortcuts."""
import structlog
from telegram import Update
from telegram.ext import ContextTypes
from telegram.error import TelegramError, BadRequest, Forbidden

from bot.navigation.context import extract_context
from bot.navigation.session import session_store
from bot.db.database import ShopError
from bot.handlers.sections.chat_encounters import maybe_spawn_encounter_from_find
from bot.handlers.sections.collection import show_collection_screen
from bot.handlers.sections.market import (
    MARKET_PENDING_ACTION_BUY_PRICE,
    MARKET_PENDING_ACTION_SELL_PRICE,
    handle_market_price_command,
    show_market_screen,
)
from bot.handlers.sections.trade import (
    handle_trade_add_command,
    handle_trade_remove_command,
    start_trade_request,
)
from bot.handlers.sections.profile import (
    _display_profile_owner,
    _display_self_profile_owner,
    handle_pokemon_search_command,
    show_profile_screen,
)
from bot.handlers.sections.shop import show_shop_screen, SHOP_VIEW_ITEMS, SHOP_VIEW_POKEMON
from bot.handlers.sections.info import show_info_screen
from bot.ui.html import display_name, escape_html
from bot.ui.menu import build_main_menu_keyboard
from bot.ui.menu import build_back_button
from bot.ui.messages import get_main_menu_text, get_section_placeholder

logger = structlog.get_logger()

PLACEHOLDER_COMMAND_SECTIONS = {
    "market": "market",
    "games": "games",
    "updates": "updates",
    "chat": "chat",
    "support": "support",
    "info": "info",
}


def _supports_db_method(db: object, method_name: str) -> bool:
    """Return True when the db object actually implements or explicitly mocks a method."""
    return method_name in getattr(db, "__dict__", {}) or hasattr(type(db), method_name)


async def _sync_user_with_db(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    """Create or update user in DB if DB integration is enabled."""
    application = getattr(context, "application", None)
    if not application:
        return
    db = application.bot_data.get("db")
    if not db or not update.effective_user:
        return False

    try:
        if _supports_db_method(db, "get_or_create_user_status"):
            db_user_id, is_new_user = await db.get_or_create_user_status(
                telegram_id=update.effective_user.id,
                username=update.effective_user.username,
            )
        else:
            db_user_id = await db.get_or_create_user(
                telegram_id=update.effective_user.id,
                username=update.effective_user.username,
            )
            is_new_user = False
        logger.info("db_user_synced", telegram_id=update.effective_user.id, db_user_id=db_user_id)
        return is_new_user
    except Exception as e:
        logger.warning(
            "db_user_sync_failed",
            telegram_id=update.effective_user.id if update.effective_user else None,
            error=str(e),
        )
        return False


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Handle /start command.
    Shows main menu to user.
    """
    await _sync_user_with_db(update, context)
    if await _maybe_show_first_entry_guide(update, context):
        return
    await _show_main_menu(update, context, skip_sync=True)


async def menu_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Handle /menu command.
    Shows main menu to user.
    """
    await _sync_user_with_db(update, context)
    if await _maybe_show_first_entry_guide(update, context):
        return
    await _show_main_menu(update, context)


async def shop_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /shop command."""
    await _sync_user_with_db(update, context)
    if await _maybe_show_first_entry_guide(update, context):
        return
    await show_shop_screen(update, context)


async def pokemon_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /pokemon command."""
    await _sync_user_with_db(update, context)
    if await _maybe_show_first_entry_guide(update, context):
        return
    await show_shop_screen(update, context, screen=SHOP_VIEW_POKEMON)


async def items_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /items command."""
    await _sync_user_with_db(update, context)
    if await _maybe_show_first_entry_guide(update, context):
        return
    await show_shop_screen(update, context, screen=SHOP_VIEW_ITEMS)


async def collection_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /collection command."""
    await _sync_user_with_db(update, context)
    if await _maybe_show_first_entry_guide(update, context):
        return
    await show_collection_screen(update, context)


async def profile_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /profile command."""
    await _sync_user_with_db(update, context)
    if await _maybe_show_first_entry_guide(update, context):
        return
    application = getattr(context, "application", None)
    db = application.bot_data.get("db") if application else None
    if not db or not update.effective_user:
        await show_profile_screen(update, context)
        return

    message = update.effective_message
    reply_to = getattr(message, "reply_to_message", None)
    command_text = update.effective_message.text or ""
    argument = _extract_command_argument(command_text)

    try:
        if (
            update.effective_chat
            and update.effective_chat.type in {"group", "supergroup"}
            and _should_use_profile_reply_target(message)
            and reply_to
            and getattr(reply_to, "from_user", None)
            and not getattr(reply_to.from_user, "is_bot", False)
        ):
            target_user = reply_to.from_user
            await db.get_or_create_user(target_user.id, target_user.username)
            summary = await db.get_profile_summary_by_telegram_id(target_user.id)
            await show_profile_screen(
                update,
                context,
                summary=summary,
                user_label=_display_profile_owner(summary),
                allow_manage=(target_user.id == update.effective_user.id),
            )
            return

        if argument:
            summary = await db.get_profile_summary_by_username(argument)
            await show_profile_screen(
                update,
                context,
                summary=summary,
                user_label=_display_profile_owner(summary),
                allow_manage=(summary.telegram_id == update.effective_user.id),
            )
            return
    except ShopError as exc:
        logger.warning(
            "profile_command_error",
            error="profile_lookup",
            error_message=str(exc),
            requester_id=update.effective_user.id if update.effective_user else None,
            argument=argument or None,
        )
        await update.effective_chat.send_message(
            f"⚠️ {exc}",
            message_thread_id=getattr(update.effective_message, "message_thread_id", None),
        )
        return

    summary = await db.get_profile_summary(update.effective_user.id, update.effective_user.username)
    await show_profile_screen(
        update,
        context,
        summary=summary,
        user_label=_display_self_profile_owner(update, summary),
        allow_manage=True,
    )


async def find_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /find command for group encounter spawning."""
    await _sync_user_with_db(update, context)
    if await _maybe_show_first_entry_guide(update, context):
        return
    await maybe_spawn_encounter_from_find(update, context)


async def search_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /search command for pokemon-name lookup."""
    await _sync_user_with_db(update, context)
    if await _maybe_show_first_entry_guide(update, context):
        return
    await handle_pokemon_search_command(update, context)


async def changename_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /changename command for profile nickname updates."""
    await _sync_user_with_db(update, context)
    if await _maybe_show_first_entry_guide(update, context):
        return
    application = getattr(context, "application", None)
    db = application.bot_data.get("db") if application else None
    if not db or not update.effective_user or not update.effective_chat or not update.effective_message:
        return

    nickname = _extract_command_argument(update.effective_message.text or "")
    if not nickname:
        await update.effective_chat.send_message(
            "✏️ Используйте команду так: <code>/changename Артём</code>",
            parse_mode="HTML",
            message_thread_id=getattr(update.effective_message, "message_thread_id", None),
        )
        return

    try:
        saved_nickname = await db.update_profile_nickname(
            update.effective_user.id,
            update.effective_user.username,
            nickname,
        )
    except ShopError as exc:
        await update.effective_chat.send_message(
            f"⚠️ {exc}",
            message_thread_id=getattr(update.effective_message, "message_thread_id", None),
        )
        return

    session_store.clear_pending_input(chat_id=update.effective_chat.id, user_id=update.effective_user.id)
    await update.effective_chat.send_message(
        f"✅ Ник сохранён: <b>{escape_html(saved_nickname)}</b>",
        parse_mode="HTML",
        message_thread_id=getattr(update.effective_message, "message_thread_id", None),
    )


async def sellprice_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /sellprice command for market sale input."""
    await _sync_user_with_db(update, context)
    if await _maybe_show_first_entry_guide(update, context):
        return
    await handle_market_price_command(update, context, action=MARKET_PENDING_ACTION_SELL_PRICE)


async def buyprice_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /buyprice command for market buy-request input."""
    await _sync_user_with_db(update, context)
    if await _maybe_show_first_entry_guide(update, context):
        return
    await handle_market_price_command(update, context, action=MARKET_PENDING_ACTION_BUY_PRICE)


async def trade_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /trade command for starting a trade request in chats."""
    await _sync_user_with_db(update, context)
    if await _maybe_show_first_entry_guide(update, context):
        return
    application = getattr(context, "application", None)
    db = application.bot_data.get("db") if application else None
    if not db or not update.effective_user or not update.effective_chat or not update.effective_message:
        return
    if update.effective_chat.type not in {"group", "supergroup"}:
        await update.effective_chat.send_message(
            "⚠️ Команда /trade доступна только в чатах.",
            message_thread_id=getattr(update.effective_message, "message_thread_id", None),
        )
        return

    target_user = None
    argument = _extract_command_argument(update.effective_message.text or "")
    if argument:
        try:
            target_tg_id, target_username, _target_nickname = await db.resolve_trade_target_by_username(argument)
        except ShopError as exc:
            await update.effective_chat.send_message(
                f"⚠️ {exc}",
                message_thread_id=getattr(update.effective_message, "message_thread_id", None),
            )
            return
        target_user = type("TradeTarget", (), {"id": target_tg_id, "username": target_username})()
    else:
        reply_to = getattr(update.effective_message, "reply_to_message", None)
        if reply_to and getattr(reply_to, "from_user", None) and not getattr(reply_to.from_user, "is_bot", False):
            target_user = reply_to.from_user

    if target_user is None:
        await update.effective_chat.send_message(
            "⚠️ Используйте /trade в ответ на сообщение пользователя или как <code>/trade @username</code>.",
            parse_mode="HTML",
            message_thread_id=getattr(update.effective_message, "message_thread_id", None),
        )
        return

    try:
        await start_trade_request(
            update,
            context,
            target_telegram_id=int(target_user.id),
            target_username=getattr(target_user, "username", None),
        )
    except ShopError as exc:
        await update.effective_chat.send_message(
            f"⚠️ {exc}",
            message_thread_id=getattr(update.effective_message, "message_thread_id", None),
        )


async def tradeadd_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /tradeadd command."""
    await _sync_user_with_db(update, context)
    if await _maybe_show_first_entry_guide(update, context):
        return
    await handle_trade_add_command(update, context)


async def traderemove_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /traderemove command."""
    await _sync_user_with_db(update, context)
    if await _maybe_show_first_entry_guide(update, context):
        return
    await handle_trade_remove_command(update, context)


async def section_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle direct placeholder section commands like /market and /profile."""
    await _sync_user_with_db(update, context)
    if await _maybe_show_first_entry_guide(update, context):
        return
    if not update.message or not update.message.text:
        return

    section = update.message.text.split()[0].lstrip("/").split("@", maxsplit=1)[0]
    if section == "market":
        await show_market_screen(update, context)
        return
    if section == "info":
        await show_info_screen(update, context)
        return
    section_name = PLACEHOLDER_COMMAND_SECTIONS.get(section)
    if not section_name:
        return
    await _show_placeholder_section(update, section_name)


async def _maybe_show_first_entry_guide(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    """Show the info guide once on the first meaningful entry into the bot."""
    application = getattr(context, "application", None)
    db = application.bot_data.get("db") if application else None
    if not db or not update.effective_user or not _supports_db_method(db, "consume_start_guide_flag"):
        return False
    try:
        should_show_guide = await db.consume_start_guide_flag(
            telegram_id=update.effective_user.id,
            username=update.effective_user.username,
        )
    except Exception as exc:
        logger.warning(
            "start_guide_flag_failed",
            telegram_id=update.effective_user.id,
            error=str(exc),
        )
        return False
    if not should_show_guide:
        return False
    await show_info_screen(update, context)
    return True


def _extract_command_argument(text: str) -> str:
    if not isinstance(text, str):
        return ""
    parts = text.split(maxsplit=1)
    if len(parts) < 2:
        return ""
    return parts[1].strip()


def _should_use_profile_reply_target(message) -> bool:
    if not message:
        return False
    reply_to = getattr(message, "reply_to_message", None)
    if not reply_to:
        return False

    is_topic_message = getattr(message, "is_topic_message", False) is True
    if not is_topic_message:
        return True

    message_thread_id = getattr(message, "message_thread_id", None)
    reply_message_id = getattr(reply_to, "message_id", None)
    if message_thread_id is None or reply_message_id is None:
        return True

    return int(reply_message_id) != int(message_thread_id)


async def _show_main_menu(update: Update, context: ContextTypes.DEFAULT_TYPE, *, skip_sync: bool = False) -> None:
    """
    Internal: Send main menu message with inline keyboard.
    
    Handles:
    - Private chats
    - Group chats
    - Forum topics (threads)
    """
    try:
        if not skip_sync:
            await _sync_user_with_db(update, context)
        msg_context = extract_context(update)
        
        logger.info(
            "show_main_menu",
            user_id=msg_context.user_id,
            chat_id=msg_context.chat_id,
            chat_type=msg_context.chat_type,
            thread_id=msg_context.message_thread_id,
        )
        
        # Get username for mention
        username = display_name(
            getattr(update.effective_user, "username", None),
            getattr(update.effective_user, "first_name", None),
        )
        
        # Send menu message with temporary session_id
        sent_message = await update.effective_chat.send_message(
            text=get_main_menu_text(username),
            parse_mode="HTML",
            reply_markup=build_main_menu_keyboard("temp"),
            message_thread_id=msg_context.message_thread_id,
        )
        
        # Create session after message is sent (to get message_id)
        session_id = session_store.create_session(
            chat_id=msg_context.chat_id,
            message_id=sent_message.message_id,
            user_id=msg_context.user_id,
            message_thread_id=msg_context.message_thread_id,
        )
        
        # Update message with real session_id
        await sent_message.edit_reply_markup(
            reply_markup=build_main_menu_keyboard(session_id)
        )
        
        logger.info(
            "main_menu_sent",
            session_id=session_id,
            message_id=sent_message.message_id,
        )
    
    except Forbidden as e:
        # Bot was blocked by user or removed from chat
        logger.warning(
            "show_main_menu_error",
            error="forbidden",
            error_message=str(e),
            user_id=update.effective_user.id if update.effective_user else None,
            chat_id=update.effective_chat.id if update.effective_chat else None,
        )
    
    except BadRequest as e:
        # Chat not found, invalid thread_id, etc.
        logger.warning(
            "show_main_menu_error",
            error="bad_request",
            error_message=str(e),
            user_id=update.effective_user.id if update.effective_user else None,
            chat_id=update.effective_chat.id if update.effective_chat else None,
            thread_id=msg_context.message_thread_id if 'msg_context' in locals() else None,
        )
    
    except TelegramError as e:
        # Other Telegram API errors (network, timeout, etc.)
        logger.error(
            "show_main_menu_error",
            error="telegram_api",
            error_message=str(e),
            user_id=update.effective_user.id if update.effective_user else None,
            chat_id=update.effective_chat.id if update.effective_chat else None,
        )
    
    except Exception as e:
        # Unexpected errors
        logger.error(
            "show_main_menu_error",
            error="unexpected",
            error_message=str(e),
            user_id=update.effective_user.id if update.effective_user else None,
            chat_id=update.effective_chat.id if update.effective_chat else None,
        )


async def _show_placeholder_section(update: Update, section: str) -> None:
    """Send a fresh placeholder section message for direct commands."""
    try:
        msg_context = extract_context(update)
        sent_message = await update.effective_chat.send_message(
            text=get_section_placeholder(section),
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
        logger.info("section_command_sent", section=section, session_id=session_id, user_id=msg_context.user_id)
    except Exception as e:
        logger.error(
            "section_command_error",
            section=section,
            error_message=str(e),
            user_id=update.effective_user.id if update.effective_user else None,
            chat_id=update.effective_chat.id if update.effective_chat else None,
        )
