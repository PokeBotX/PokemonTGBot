"""Context extraction from Telegram updates."""
from dataclasses import dataclass
from typing import Optional
from telegram import Update


@dataclass
class MessageContext:
    """Context information from a Telegram update."""
    chat_id: int
    user_id: int
    message_id: Optional[int] = None
    message_thread_id: Optional[int] = None
    chat_type: str = "private"  # private, group, supergroup, channel


def extract_context(update: Update) -> MessageContext:
    """
    Extract context from Telegram update.
    
    Args:
        update: Telegram Update object
    
    Returns:
        MessageContext with chat_id, user_id, message_id, thread_id, chat_type
    
    Raises:
        ValueError: If update is invalid or missing required fields
    """
    if not update.effective_chat or not update.effective_user:
        raise ValueError("Update missing effective_chat or effective_user")
    
    context = MessageContext(
        chat_id=update.effective_chat.id,
        user_id=update.effective_user.id,
        chat_type=update.effective_chat.type,
    )
    
    if update.effective_message:
        context.message_id = update.effective_message.message_id
        context.message_thread_id = getattr(
            update.effective_message, "message_thread_id", None
        )
    
    return context
