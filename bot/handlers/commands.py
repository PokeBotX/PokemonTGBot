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
from bot.handlers.sections.profile import _display_profile_owner, handle_pokemon_search_command, show_profile_screen
from bot.handlers.sections.shop import show_shop_screen, SHOP_VIEW_ITEMS, SHOP_VIEW_POKEMON
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


async def _sync_user_with_db(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Create or update user in DB if DB integration is enabled."""
    application = getattr(context, "application", None)
    if not application:
        return
    db = application.bot_data.get("db")
    if not db or not update.effective_user:
        return

    try:
        db_user_id = await db.get_or_create_user(
            telegram_id=update.effective_user.id,
            username=update.effective_user.username,
        )
        logger.info("db_user_synced", telegram_id=update.effective_user.id, db_user_id=db_user_id)
    except Exception as e:
        logger.warning(
            "db_user_sync_failed",
            telegram_id=update.effective_user.id if update.effective_user else None,
            error=str(e),
        )


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Handle /start command.
    Shows main menu to user.
    """
    await _show_main_menu(update, context)


async def menu_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Handle /menu command.
    Shows main menu to user.
    """
    await _show_main_menu(update, context)


async def shop_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /shop command."""
    await _sync_user_with_db(update, context)
    await show_shop_screen(update, context)


async def pokemon_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /pokemon command."""
    await _sync_user_with_db(update, context)
    await show_shop_screen(update, context, screen=SHOP_VIEW_POKEMON)


async def items_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /items command."""
    await _sync_user_with_db(update, context)
    await show_shop_screen(update, context, screen=SHOP_VIEW_ITEMS)


async def collection_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /collection command."""
    await _sync_user_with_db(update, context)
    await show_collection_screen(update, context)


async def profile_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /profile command."""
    await _sync_user_with_db(update, context)
    application = getattr(context, "application", None)
    db = application.bot_data.get("db") if application else None
    if not db or not update.effective_user:
        await show_profile_screen(update, context)
        return

    reply_to = getattr(update.effective_message, "reply_to_message", None)
    command_text = update.effective_message.text or ""
    argument = _extract_command_argument(command_text)

    try:
        if reply_to and getattr(reply_to, "from_user", None) and not getattr(reply_to.from_user, "is_bot", False):
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

    await show_profile_screen(update, context)


async def find_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /find command for group encounter spawning."""
    await _sync_user_with_db(update, context)
    await maybe_spawn_encounter_from_find(update, context)


async def search_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /search command for pokemon-name lookup."""
    await _sync_user_with_db(update, context)
    await handle_pokemon_search_command(update, context)


async def section_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle direct placeholder section commands like /market and /profile."""
    await _sync_user_with_db(update, context)
    if not update.message or not update.message.text:
        return

    section = update.message.text.split()[0].lstrip("/").split("@", maxsplit=1)[0]
    section_name = PLACEHOLDER_COMMAND_SECTIONS.get(section)
    if not section_name:
        return
    await _show_placeholder_section(update, section_name)


def _extract_command_argument(text: str) -> str:
    if not isinstance(text, str):
        return ""
    parts = text.split(maxsplit=1)
    if len(parts) < 2:
        return ""
    return parts[1].strip()


async def _show_main_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Internal: Send main menu message with inline keyboard.
    
    Handles:
    - Private chats
    - Group chats
    - Forum topics (threads)
    """
    try:
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
        username = update.effective_user.username or update.effective_user.first_name or "тренер"
        
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
