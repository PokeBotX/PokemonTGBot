"""Group chat activity hooks for encounter spawning."""

import structlog
from telegram import Update
from telegram.ext import ContextTypes

from bot.handlers.sections.chat_encounters import maybe_spawn_encounter_from_message

logger = structlog.get_logger()


async def group_message_activity_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Observe group chat messages and trigger hidden encounter checks."""
    logger.debug(
        "group_message_activity_tick",
        chat_id=update.effective_chat.id if update.effective_chat else None,
    )
    await maybe_spawn_encounter_from_message(update, context)
