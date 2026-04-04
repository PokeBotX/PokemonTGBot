"""Group chat activity hooks for encounter spawning."""

import structlog
from telegram import Update
from telegram.ext import ContextTypes

from bot.handlers.sections.chat_encounters import maybe_spawn_encounter_from_message

logger = structlog.get_logger()


async def group_message_activity_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Observe group chat messages and trigger hidden encounter checks."""
    logger.info(
        "group_message_activity_received",
        chat_id=update.effective_chat.id if update.effective_chat else None,
        chat_type=update.effective_chat.type if update.effective_chat else None,
        user_id=update.effective_user.id if update.effective_user else None,
        is_bot=getattr(update.effective_user, "is_bot", None) if update.effective_user else None,
        message_id=update.effective_message.message_id if update.effective_message else None,
        has_text=bool(getattr(update.effective_message, "text", None)) if update.effective_message else None,
        text_length=len(getattr(update.effective_message, "text", "") or "") if update.effective_message else None,
    )
    await maybe_spawn_encounter_from_message(update, context)
