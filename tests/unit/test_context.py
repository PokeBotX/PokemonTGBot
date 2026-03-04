"""Unit tests for context extraction."""
import pytest
from unittest.mock import Mock
from telegram import Update, Message, User, Chat

from bot.navigation.context import extract_context, MessageContext


def test_extract_context_private_chat():
    """Test context extraction from private chat."""
    # Mock objects
    user = Mock(spec=User)
    user.id = 12345
    
    chat = Mock(spec=Chat)
    chat.id = 12345
    chat.type = "private"
    
    message = Mock(spec=Message)
    message.message_id = 100
    message.chat = chat
    message.from_user = user
    message.message_thread_id = None
    
    update = Mock(spec=Update)
    update.effective_chat = chat
    update.effective_user = user
    update.effective_message = message
    
    # Extract context
    context = extract_context(update)
    
    # Assertions
    assert isinstance(context, MessageContext)
    assert context.chat_id == 12345
    assert context.user_id == 12345
    assert context.message_id == 100
    assert context.chat_type == "private"
    assert context.message_thread_id is None


def test_extract_context_group_chat():
    """Test context extraction from group chat."""
    user = Mock(spec=User)
    user.id = 12345
    
    chat = Mock(spec=Chat)
    chat.id = -67890
    chat.type = "group"
    
    message = Mock(spec=Message)
    message.message_id = 200
    message.chat = chat
    message.from_user = user
    message.message_thread_id = None
    
    update = Mock(spec=Update)
    update.effective_chat = chat
    update.effective_user = user
    update.effective_message = message
    
    context = extract_context(update)
    
    assert context.chat_id == -67890
    assert context.user_id == 12345
    assert context.message_id == 200
    assert context.chat_type == "group"
    assert context.message_thread_id is None


def test_extract_context_forum_topic():
    """Test context extraction from forum topic (supergroup with thread_id)."""
    user = Mock(spec=User)
    user.id = 12345
    
    chat = Mock(spec=Chat)
    chat.id = -100123456789
    chat.type = "supergroup"
    chat.is_forum = True
    
    message = Mock(spec=Message)
    message.message_id = 300
    message.chat = chat
    message.from_user = user
    message.message_thread_id = 42  # Forum topic ID
    
    update = Mock(spec=Update)
    update.effective_chat = chat
    update.effective_user = user
    update.effective_message = message
    
    context = extract_context(update)
    
    assert context.chat_id == -100123456789
    assert context.user_id == 12345
    assert context.message_id == 300
    assert context.chat_type == "supergroup"
    assert context.message_thread_id == 42


def test_extract_context_missing_chat():
    """Test that ValueError is raised when chat is missing."""
    update = Mock(spec=Update)
    update.effective_chat = None
    update.effective_user = Mock(spec=User)
    update.effective_message = Mock(spec=Message)
    
    with pytest.raises(ValueError, match="Update missing effective_chat or effective_user"):
        extract_context(update)


def test_extract_context_missing_user():
    """Test that ValueError is raised when user is missing."""
    chat = Mock(spec=Chat)
    chat.id = 12345
    chat.type = "private"
    
    update = Mock(spec=Update)
    update.effective_chat = chat
    update.effective_user = None
    update.effective_message = Mock(spec=Message)
    
    with pytest.raises(ValueError, match="Update missing effective_chat or effective_user"):
        extract_context(update)


def test_extract_context_without_message():
    """Test context extraction when message is None (callback query case)."""
    user = Mock(spec=User)
    user.id = 12345
    
    chat = Mock(spec=Chat)
    chat.id = 12345
    chat.type = "private"
    
    update = Mock(spec=Update)
    update.effective_chat = chat
    update.effective_user = user
    update.effective_message = None
    
    # Should not raise, message_id will be None
    context = extract_context(update)
    
    assert context.chat_id == 12345
    assert context.user_id == 12345
    assert context.message_id is None
    assert context.message_thread_id is None
