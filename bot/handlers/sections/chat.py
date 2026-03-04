"""Чат section handler (placeholder)."""
import structlog
from telegram import Update
from telegram.ext import ContextTypes
from telegram.error import TelegramError, BadRequest

from bot.navigation.session import MenuSession, session_store
from bot.ui.menu import build_back_button
from bot.ui.messages import get_section_placeholder

logger = structlog.get_logger()


async def chat_handler(update: Update, context: ContextTypes.DEFAULT_TYPE, session: MenuSession) -> None:
    """Handle 'Чат' section (placeholder)."""
    query = update.callback_query
    
    try:
        # Create new session for back button
        new_session_id = session_store.create_session(
            chat_id=session.chat_id,
            message_id=session.message_id,
            user_id=session.user_id,
            message_thread_id=session.message_thread_id,
        )
        
        # Update message with section content
        await query.edit_message_text(
            text=get_section_placeholder("chat"),
            parse_mode="HTML",
            reply_markup=build_back_button(new_session_id),
        )
        
        logger.info(
            "section_displayed",
            section="chat",
            session_id=new_session_id,
            user_id=session.user_id,
        )
    
    except BadRequest as e:
        # Message was deleted, chat/thread no longer exists, etc.
        logger.warning(
            "section_handler_error",
            section="chat",
            error="bad_request",
            error_message=str(e),
            user_id=session.user_id,
            chat_id=session.chat_id,
        )
    
    except TelegramError as e:
        # Other Telegram API errors
        logger.error(
            "section_handler_error",
            section="chat",
            error="telegram_api",
            error_message=str(e),
            user_id=session.user_id,
        )
    
    except Exception as e:
        # Unexpected errors
        logger.error(
            "section_handler_error",
            section="chat",
            error="unexpected",
            error_message=str(e),
            user_id=session.user_id,
        )
