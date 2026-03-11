"""Command handlers for /start and /menu."""
import structlog
from telegram import Update
from telegram.ext import ContextTypes
from telegram.error import TelegramError, BadRequest, Forbidden

from bot.navigation.context import extract_context
from bot.navigation.session import session_store
from bot.ui.menu import build_main_menu_keyboard
from bot.ui.messages import get_main_menu_text

logger = structlog.get_logger()


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
