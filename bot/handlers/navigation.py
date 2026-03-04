"""Navigation callback query handler."""
import structlog
from telegram import Update
from telegram.ext import ContextTypes

from bot.navigation.context import extract_context
from bot.navigation.router import parse_callback_data, navigation_router
from bot.navigation.session import session_store
from bot.ui.messages import (
    ERROR_STALE_MENU,
    ERROR_PROCESSING,
    ERROR_INVALID_CALLBACK,
    ERROR_BOT_RESTARTED,
    ERROR_NOT_YOUR_BUTTON,
)

logger = structlog.get_logger()


async def handle_callback_query(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Handle all callback queries from inline buttons.
    
    Flow:
    1. Parse callback_data
    2. Check idempotency (duplicate clicks)
    3. Validate session (not expired, correct context)
    4. Route to section handler
    5. Handle errors gracefully
    """
    query = update.callback_query
    
    try:
        # Check for duplicate callback (double-click protection)
        if session_store.is_callback_locked(query.id):
            await query.answer(ERROR_PROCESSING, show_alert=False)
            logger.info("callback_duplicate_ignored", callback_id=query.id)
            return
        
        # Lock callback to prevent duplicates
        session_store.lock_callback(query.id)
        
        # Parse callback data
        callback_data = parse_callback_data(query.data)
        if not callback_data:
            await query.answer(ERROR_INVALID_CALLBACK, show_alert=True)
            logger.warning("callback_invalid_format", data=query.data)
            return
        
        logger.info(
            "callback_received",
            section=callback_data.section,
            session_id=callback_data.session_id,
            user_id=update.effective_user.id,
        )
        
        # Validate session
        session = session_store.get_session(callback_data.session_id)
        if not session:
            await query.answer(ERROR_BOT_RESTARTED, show_alert=True)
            logger.warning(
                "session_not_found",
                session_id=callback_data.session_id,
                user_id=update.effective_user.id,
            )
            return
        
        # Check if user is trying to use someone else's button
        if update.effective_user.id != session.user_id:
            await query.answer(ERROR_NOT_YOUR_BUTTON, show_alert=True)
            logger.warning(
                "unauthorized_button_click",
                session_id=callback_data.session_id,
                session_user_id=session.user_id,
                actual_user_id=update.effective_user.id,
            )
            return
        
        # Check session context matches
        msg_context = extract_context(update)
        if not session.matches_context(
            msg_context.chat_id,
            query.message.message_id,
            msg_context.message_thread_id,
        ):
            await query.answer(ERROR_STALE_MENU, show_alert=True)
            logger.warning(
                "session_context_mismatch",
                session_id=callback_data.session_id,
                expected_chat=session.chat_id,
                actual_chat=msg_context.chat_id,
            )
            return
        
        # Answer callback query (Telegram requirement) - after all validations
        await query.answer()
        
        # Route to section handler
        handler = navigation_router.get_handler(callback_data.section)
        if not handler:
            await query.answer(ERROR_INVALID_CALLBACK, show_alert=True)
            logger.error(
                "no_handler_for_section",
                section=callback_data.section,
            )
            return
        
        # Execute handler
        await handler(update, context, session)
        
        logger.info(
            "callback_handled",
            section=callback_data.section,
            session_id=callback_data.session_id,
        )
    
    except Exception as e:
        logger.error(
            "callback_handler_error",
            error=str(e),
            callback_data=query.data if query else None,
        )
        try:
            await query.answer(ERROR_INVALID_CALLBACK, show_alert=True)
        except:
            pass  # Best effort
