"""Back to menu handler."""
import structlog
from telegram import Update
from telegram.ext import ContextTypes
from telegram.error import TelegramError, BadRequest

from bot.navigation.session import MenuSession, session_store
from bot.ui.html import display_name
from bot.ui.menu import build_main_menu_keyboard
from bot.ui.messages import get_main_menu_text

logger = structlog.get_logger()


def _is_photo_message(message) -> bool:
    photo = getattr(message, "photo", None)
    return isinstance(photo, (list, tuple)) and len(photo) > 0


async def back_to_menu_handler(update: Update, context: ContextTypes.DEFAULT_TYPE, session: MenuSession) -> None:
    """
    Handle 'Back to Menu' button.
    
    Returns user to main menu.
    """
    query = update.callback_query
    
    try:
        # Get username for mention
        username = display_name(
            getattr(update.effective_user, "username", None),
            getattr(update.effective_user, "first_name", None),
        )
        if query.message and _is_photo_message(query.message):
            sent_message = await context.bot.send_message(
                chat_id=session.chat_id,
                message_thread_id=session.message_thread_id,
                text=get_main_menu_text(username),
                parse_mode="HTML",
                reply_markup=build_main_menu_keyboard("temp"),
            )
            new_session_id = session_store.create_session(
                chat_id=session.chat_id,
                message_id=sent_message.message_id,
                user_id=session.user_id,
                message_thread_id=session.message_thread_id,
            )
            await sent_message.edit_reply_markup(reply_markup=build_main_menu_keyboard(new_session_id))
            try:
                await query.message.delete()
            except TelegramError:
                pass
        else:
            new_session_id = session_store.create_session(
                chat_id=session.chat_id,
                message_id=session.message_id,
                user_id=session.user_id,
                message_thread_id=session.message_thread_id,
            )
            await query.edit_message_text(
                text=get_main_menu_text(username),
                parse_mode="HTML",
                reply_markup=build_main_menu_keyboard(new_session_id),
            )
        
        logger.info(
            "back_to_menu",
            session_id=new_session_id,
            user_id=session.user_id,
        )
    
    except BadRequest as e:
        # Message was deleted, chat/thread no longer exists, etc.
        logger.warning(
            "back_to_menu_error",
            error="bad_request",
            error_message=str(e),
            user_id=session.user_id,
            chat_id=session.chat_id,
        )
    
    except TelegramError as e:
        # Other Telegram API errors
        logger.error(
            "back_to_menu_error",
            error="telegram_api",
            error_message=str(e),
            user_id=session.user_id,
        )
    
    except Exception as e:
        # Unexpected errors
        logger.error(
            "back_to_menu_error",
            error="unexpected",
            error_message=str(e),
            user_id=session.user_id,
        )
