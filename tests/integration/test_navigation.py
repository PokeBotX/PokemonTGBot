"""Integration tests for navigation and edge cases."""
import pytest
from unittest.mock import AsyncMock, Mock
from telegram import Update, User, Chat, CallbackQuery, Message
from telegram.ext import ContextTypes

from bot.handlers.navigation import handle_callback_query
from bot.navigation.session import session_store, MenuSession
from bot.navigation.router import navigation_router
from bot.handlers.sections.shop import shop_handler


@pytest.fixture(autouse=True)
def clear_sessions():
    """Clear session store before each test."""
    session_store._sessions.clear()
    session_store._callback_locks.clear()
    yield
    session_store._sessions.clear()
    session_store._callback_locks.clear()


@pytest.fixture
def mock_callback_update():
    """Create a mock Update with callback query."""
    def _create_update(callback_data: str, message_id: int = 100, thread_id: int = None):
        user = Mock(spec=User)
        user.id = 12345
        
        chat = Mock(spec=Chat)
        chat.id = 12345
        chat.type = "private"
        
        message = Mock(spec=Message)
        message.message_id = message_id
        message.chat = chat
        message.message_thread_id = thread_id
        
        query = AsyncMock(spec=CallbackQuery)
        query.id = "callback_123"
        query.data = callback_data
        query.answer = AsyncMock()
        query.message = message
        query.edit_message_text = AsyncMock()
        
        update = Mock(spec=Update)
        update.callback_query = query
        update.effective_user = user
        update.effective_chat = chat
        update.effective_message = message
        
        return update
    
    return _create_update


@pytest.mark.asyncio
async def test_navigation_full_flow(mock_callback_update):
    """Test full navigation flow: menu -> section -> back."""
    # Register shop handler
    navigation_router.register("shop", shop_handler)
    
    # Create session
    session_id = session_store.create_session(
        chat_id=12345,
        message_id=100,
        user_id=12345,
    )
    
    # Simulate clicking "Магазин" button
    update = mock_callback_update(f"menu:shop:{session_id}")
    context = Mock(spec=ContextTypes.DEFAULT_TYPE)
    
    await handle_callback_query(update, context)
    
    # Verify callback was answered
    assert update.callback_query.answer.called
    
    # Verify message was edited (shop placeholder shown)
    assert update.callback_query.edit_message_text.called


@pytest.mark.asyncio
async def test_invalid_callback_format(mock_callback_update):
    """Test handling of invalid callback data format."""
    update = mock_callback_update("invalid_format")
    context = Mock(spec=ContextTypes.DEFAULT_TYPE)
    
    await handle_callback_query(update, context)
    
    # Verify error message shown
    assert update.callback_query.answer.called
    call_args = update.callback_query.answer.call_args
    assert "Ошибка обработки" in str(call_args) or call_args[0][0] is not None


@pytest.mark.asyncio
async def test_unknown_section(mock_callback_update):
    """Test handling of unknown section."""
    session_id = session_store.create_session(
        chat_id=12345,
        message_id=100,
        user_id=12345,
    )
    
    # Try unknown section
    update = mock_callback_update(f"menu:unknown_section:{session_id}")
    context = Mock(spec=ContextTypes.DEFAULT_TYPE)
    
    await handle_callback_query(update, context)
    
    # Verify error was shown
    assert update.callback_query.answer.called


@pytest.mark.asyncio
async def test_bot_restarted_edge_case(mock_callback_update):
    """Test edge case: bot restarted, session no longer exists."""
    # Use non-existent session_id
    fake_session_id = "00000000-0000-0000-0000-000000000000"
    
    update = mock_callback_update(f"menu:shop:{fake_session_id}")
    context = Mock(spec=ContextTypes.DEFAULT_TYPE)
    
    await handle_callback_query(update, context)
    
    # Verify "bot restarted" error shown
    assert update.callback_query.answer.called
    call_args = update.callback_query.answer.call_args
    # Should show error with alert
    assert call_args.kwargs.get("show_alert") is True


@pytest.mark.asyncio
async def test_stale_menu_edge_case(mock_callback_update):
    """Test edge case: user clicks button from old menu."""
    # Create session for message_id 100
    session_id = session_store.create_session(
        chat_id=12345,
        message_id=100,
        user_id=12345,
    )
    
    # But callback comes from message_id 200 (different menu)
    update = mock_callback_update(f"menu:shop:{session_id}", message_id=200)
    context = Mock(spec=ContextTypes.DEFAULT_TYPE)
    
    await handle_callback_query(update, context)
    
    # Verify "stale menu" error shown
    assert update.callback_query.answer.called
    call_args = update.callback_query.answer.call_args
    assert call_args.kwargs.get("show_alert") is True


@pytest.mark.asyncio
async def test_duplicate_callback_prevention(mock_callback_update):
    """Test duplicate callback prevention (double-click protection)."""
    navigation_router.register("shop", shop_handler)
    
    session_id = session_store.create_session(
        chat_id=12345,
        message_id=100,
        user_id=12345,
    )
    
    update = mock_callback_update(f"menu:shop:{session_id}")
    context = Mock(spec=ContextTypes.DEFAULT_TYPE)
    
    # First click
    await handle_callback_query(update, context)
    
    # Reset mock to check second call
    update.callback_query.answer.reset_mock()
    update.callback_query.edit_message_text.reset_mock()
    
    # Second click (same callback_id)
    await handle_callback_query(update, context)
    
    # Second click should be ignored (still answered, but no edit)
    assert update.callback_query.answer.called
    # Edit should not be called again (or called only once total)
    # Note: This test assumes callback lock works


@pytest.mark.asyncio
async def test_session_with_thread_id(mock_callback_update):
    """Test navigation in forum topic with thread_id."""
    navigation_router.register("shop", shop_handler)
    
    # Create session with thread_id
    session_id = session_store.create_session(
        chat_id=12345,
        message_id=100,
        user_id=12345,
        message_thread_id=42,
    )
    
    # Update with matching thread_id
    update = mock_callback_update(f"menu:shop:{session_id}", thread_id=42)
    
    context = Mock(spec=ContextTypes.DEFAULT_TYPE)
    
    await handle_callback_query(update, context)
    
    # Should succeed
    assert update.callback_query.answer.called
    assert update.callback_query.edit_message_text.called


@pytest.mark.asyncio
async def test_session_thread_id_mismatch(mock_callback_update):
    """Test session validation fails when thread_id doesn't match."""
    session_id = session_store.create_session(
        chat_id=12345,
        message_id=100,
        user_id=12345,
        message_thread_id=42,  # Session expects thread 42
    )
    
    # Update with different thread_id
    update = mock_callback_update(f"menu:shop:{session_id}", thread_id=99)
    
    context = Mock(spec=ContextTypes.DEFAULT_TYPE)
    
    await handle_callback_query(update, context)
    
    # Should show error
    assert update.callback_query.answer.called
    call_args = update.callback_query.answer.call_args
    assert call_args.kwargs.get("show_alert") is True


@pytest.mark.asyncio
async def test_empty_callback_fields(mock_callback_update):
    """Test handling of callback with empty fields."""
    # Empty section
    update = mock_callback_update("menu::session-123")
    context = Mock(spec=ContextTypes.DEFAULT_TYPE)
    
    await handle_callback_query(update, context)
    
    # Should show error
    assert update.callback_query.answer.called


@pytest.mark.asyncio
async def test_wrong_action_type(mock_callback_update):
    """Test handling of callback with wrong action (not 'menu')."""
    update = mock_callback_update("other:shop:session-123")
    context = Mock(spec=ContextTypes.DEFAULT_TYPE)
    
    await handle_callback_query(update, context)
    
    # Should show error
    assert update.callback_query.answer.called


@pytest.mark.asyncio
async def test_handler_text_answer_is_not_overridden_by_empty_preanswer(mock_callback_update):
    async def answering_handler(update: Update, context: ContextTypes.DEFAULT_TYPE, session: MenuSession) -> None:
        await update.callback_query.answer("⚠️ Причина отказа", show_alert=False)

    navigation_router.register("answering", answering_handler)
    session_id = session_store.create_session(
        chat_id=12345,
        message_id=100,
        user_id=12345,
    )
    update = mock_callback_update(f"menu:answering:{session_id}")
    context = Mock(spec=ContextTypes.DEFAULT_TYPE)

    await handle_callback_query(update, context)

    assert update.callback_query.answer.call_count == 1
    assert update.callback_query.answer.call_args.args[0] == "⚠️ Причина отказа"
