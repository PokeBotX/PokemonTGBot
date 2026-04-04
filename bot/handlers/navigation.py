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
    
    original_answer = query.answer

    try:
        await _sync_user_with_db(update, context)

        # Check for duplicate callback (double-click protection)
        if session_store.is_callback_locked(query.id):
            logger.info("callback_duplicate_answer_start", callback_id=query.id)
            await query.answer(ERROR_PROCESSING, show_alert=False)
            logger.info("callback_duplicate_answer_done", callback_id=query.id)
            logger.info("callback_duplicate_ignored", callback_id=query.id)
            return
        
        # Lock callback to prevent duplicates
        session_store.lock_callback(query.id)
        
        # Parse callback data
        callback_data = parse_callback_data(query.data)
        if not callback_data:
            logger.info("callback_invalid_answer_start", raw_data=query.data)
            await query.answer(ERROR_INVALID_CALLBACK, show_alert=True)
            logger.info("callback_invalid_answer_done", raw_data=query.data)
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
            logger.info(
                "callback_missing_session_answer_start",
                session_id=callback_data.session_id,
                user_id=update.effective_user.id,
            )
            await query.answer(ERROR_BOT_RESTARTED, show_alert=True)
            logger.info(
                "callback_missing_session_answer_done",
                session_id=callback_data.session_id,
                user_id=update.effective_user.id,
            )
            logger.warning(
                "session_not_found",
                session_id=callback_data.session_id,
                user_id=update.effective_user.id,
            )
            return
        
        # Check if user is trying to use someone else's button
        if update.effective_user.id != session.user_id:
            logger.info(
                "callback_wrong_user_answer_start",
                session_id=callback_data.session_id,
                session_user_id=session.user_id,
                actual_user_id=update.effective_user.id,
            )
            await query.answer(ERROR_NOT_YOUR_BUTTON, show_alert=False)
            logger.info(
                "callback_wrong_user_answer_done",
                session_id=callback_data.session_id,
                session_user_id=session.user_id,
                actual_user_id=update.effective_user.id,
            )
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
            logger.info(
                "callback_stale_answer_start",
                session_id=callback_data.session_id,
                expected_chat=session.chat_id,
                actual_chat=msg_context.chat_id,
            )
            await query.answer(ERROR_STALE_MENU, show_alert=True)
            logger.info(
                "callback_stale_answer_done",
                session_id=callback_data.session_id,
                expected_chat=session.chat_id,
                actual_chat=msg_context.chat_id,
            )
            logger.warning(
                "session_context_mismatch",
                session_id=callback_data.session_id,
                expected_chat=session.chat_id,
                actual_chat=msg_context.chat_id,
            )
            return
        
        answered = False
        async def tracked_answer(*args, **kwargs):
            nonlocal answered
            answered = True
            logger.info(
                "callback_answer_start",
                section=callback_data.section,
                session_id=callback_data.session_id,
                user_id=update.effective_user.id,
                has_text=bool(args),
                show_alert=bool(kwargs.get("show_alert", False)),
            )
            result = await original_answer(*args, **kwargs)
            logger.info(
                "callback_answer_done",
                section=callback_data.section,
                session_id=callback_data.session_id,
                user_id=update.effective_user.id,
                has_text=bool(args),
                show_alert=bool(kwargs.get("show_alert", False)),
            )
            return result

        query.answer = tracked_answer
        
        # Route to section handler
        handler = navigation_router.get_handler(callback_data.section)
        if not handler:
            logger.info(
                "callback_no_handler_answer_start",
                section=callback_data.section,
            )
            await query.answer(ERROR_INVALID_CALLBACK, show_alert=True)
            logger.info(
                "callback_no_handler_answer_done",
                section=callback_data.section,
            )
            logger.error(
                "no_handler_for_section",
                section=callback_data.section,
            )
            return
        
        # Execute handler
        logger.info(
            "callback_handler_start",
            section=callback_data.section,
            session_id=callback_data.session_id,
            user_id=update.effective_user.id,
        )
        await handler(update, context, session)
        if not answered:
            await tracked_answer()
        logger.info(
            "callback_handler_done",
            section=callback_data.section,
            session_id=callback_data.session_id,
            user_id=update.effective_user.id,
        )
        
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
            logger.info("callback_error_answer_start", callback_data=query.data if query else None)
            await query.answer(ERROR_INVALID_CALLBACK, show_alert=True)
            logger.info("callback_error_answer_done", callback_data=query.data if query else None)
        except Exception:
            pass  # Best effort
    finally:
        query.answer = original_answer
