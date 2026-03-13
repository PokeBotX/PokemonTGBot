"""Integration tests for command and section handlers."""
import pytest
from unittest.mock import AsyncMock, Mock
from telegram import Update, Message, User, Chat, CallbackQuery
from telegram.ext import ContextTypes

from bot.handlers.commands import menu_command, section_command, shop_command, start_command
from bot.handlers.sections.shop import shop_handler
from bot.handlers.sections.back import back_to_menu_handler
from bot.navigation.session import session_store, MenuSession
from bot.db.database import ShopView


@pytest.fixture(autouse=True)
def clear_sessions():
    """Clear session store before each test."""
    session_store._sessions.clear()
    session_store._callback_locks.clear()
    yield
    session_store._sessions.clear()
    session_store._callback_locks.clear()


@pytest.fixture
def mock_update():
    """Create a mock Update for private chat."""
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
    
    return update


@pytest.mark.asyncio
async def test_start_command_sends_menu(mock_update):
    """Test /start command sends main menu."""
    # Mock send_message
    sent_message = Mock(spec=Message)
    sent_message.message_id = 101
    sent_message.edit_reply_markup = AsyncMock()
    
    mock_update.effective_chat.send_message = AsyncMock(return_value=sent_message)
    
    context = Mock(spec=ContextTypes.DEFAULT_TYPE)
    
    # Execute command
    await start_command(mock_update, context)
    
    # Verify message was sent
    assert mock_update.effective_chat.send_message.called
    call_args = mock_update.effective_chat.send_message.call_args
    
    # Check text contains welcome message
    assert "Добро пожаловать" in call_args.kwargs["text"]
    assert call_args.kwargs["parse_mode"] == "HTML"
    
    # Verify keyboard was updated with real session_id
    assert sent_message.edit_reply_markup.called
    
    # Verify session was created
    assert len(session_store._sessions) == 1


@pytest.mark.asyncio
async def test_menu_command_sends_menu(mock_update):
    """Test /menu command sends main menu."""
    sent_message = Mock(spec=Message)
    sent_message.message_id = 102
    sent_message.edit_reply_markup = AsyncMock()
    
    mock_update.effective_chat.send_message = AsyncMock(return_value=sent_message)
    
    context = Mock(spec=ContextTypes.DEFAULT_TYPE)
    
    await menu_command(mock_update, context)
    
    # Verify message was sent
    assert mock_update.effective_chat.send_message.called
    assert len(session_store._sessions) == 1


@pytest.mark.asyncio
async def test_shop_command_sends_shop_message(mock_update):
    """Test /shop command sends a fresh shop message."""
    sent_message = Mock(spec=Message)
    sent_message.message_id = 103
    sent_message.edit_reply_markup = AsyncMock()
    mock_update.effective_chat.send_message = AsyncMock(return_value=sent_message)

    db = AsyncMock()
    db.get_shop_view = AsyncMock(
        return_value=ShopView(
            user_id=1,
            balance=2500,
            pokecoin_balance=15,
            ultraball_quantity=0,
            masterball_quantity=0,
            epic_pity_counter=2,
            legendary_pity_counter=3,
            bonus_available=125,
            bonus_ready_in_seconds=0,
        )
    )
    application = Mock()
    application.bot_data = {"db": db}
    context = Mock(spec=ContextTypes.DEFAULT_TYPE)
    context.application = application

    await shop_command(mock_update, context)

    assert mock_update.effective_chat.send_message.called
    call_args = mock_update.effective_chat.send_message.call_args
    assert "добро пожаловать в магазин" in call_args.kwargs["text"]
    assert sent_message.edit_reply_markup.called
    assert len(session_store._sessions) == 1


@pytest.mark.asyncio
async def test_market_command_sends_placeholder_section(mock_update):
    """Test /market command sends the market placeholder."""
    sent_message = Mock(spec=Message)
    sent_message.message_id = 104
    sent_message.edit_reply_markup = AsyncMock()
    mock_update.effective_chat.send_message = AsyncMock(return_value=sent_message)
    mock_update.message = Mock()
    mock_update.message.text = "/market"

    application = Mock()
    application.bot_data = {}
    context = Mock(spec=ContextTypes.DEFAULT_TYPE)
    context.application = application

    await section_command(mock_update, context)

    assert mock_update.effective_chat.send_message.called
    call_args = mock_update.effective_chat.send_message.call_args
    assert "Рынок" in call_args.kwargs["text"]
    assert sent_message.edit_reply_markup.called
    assert len(session_store._sessions) == 1


@pytest.mark.asyncio
async def test_section_handler_shows_placeholder():
    """Test shop handler renders the shop screen."""
    # Create a session
    session = MenuSession(
        session_id="test-session-123",
        chat_id=12345,
        message_id=100,
        user_id=67890,
        message_thread_id=None,
    )
    session_store._sessions[session.session_id] = session
    
    # Mock callback query
    query = AsyncMock(spec=CallbackQuery)
    query.edit_message_text = AsyncMock()
    
    user = Mock(spec=User)
    user.id = 67890
    
    chat = Mock(spec=Chat)
    chat.id = 12345
    chat.type = "private"
    
    message = Mock(spec=Message)
    message.message_id = 100
    message.chat = chat
    
    update = Mock(spec=Update)
    update.callback_query = query
    update.effective_user = user
    update.effective_chat = chat
    update.effective_message = message

    db = AsyncMock()
    db.get_shop_view = AsyncMock(
        return_value=ShopView(
            user_id=1,
            balance=2500,
            pokecoin_balance=0,
            ultraball_quantity=0,
            masterball_quantity=0,
            epic_pity_counter=2,
            legendary_pity_counter=3,
            bonus_available=125,
            bonus_ready_in_seconds=0,
        )
    )
    application = Mock()
    application.bot_data = {"db": db}
    context = Mock(spec=ContextTypes.DEFAULT_TYPE)
    context.application = application

    # Execute handler
    await shop_handler(update, context, session)
    
    # Verify message was edited
    assert query.edit_message_text.called
    call_args = query.edit_message_text.call_args
    
    # Check shop text
    assert "добро пожаловать в магазин" in call_args.kwargs["text"]
    assert "Ваш баланс" in call_args.kwargs["text"]
    assert "Выберите желаемый раздел" in call_args.kwargs["text"]

    # Verify new session was created for back button
    assert len(session_store._sessions) == 2


@pytest.mark.asyncio
async def test_back_to_menu_handler_returns_to_menu():
    """Test back button returns to main menu."""
    session = MenuSession(
        session_id="test-session-456",
        chat_id=12345,
        message_id=100,
        user_id=67890,
        message_thread_id=None,
    )
    session_store._sessions[session.session_id] = session
    
    # Mock callback query
    query = AsyncMock(spec=CallbackQuery)
    query.edit_message_text = AsyncMock()
    
    user = Mock(spec=User)
    user.id = 67890
    
    chat = Mock(spec=Chat)
    chat.id = 12345
    
    update = Mock(spec=Update)
    update.callback_query = query
    update.effective_user = user
    update.effective_chat = chat
    
    context = Mock(spec=ContextTypes.DEFAULT_TYPE)
    
    # Execute handler
    await back_to_menu_handler(update, context, session)
    
    # Verify message was edited
    assert query.edit_message_text.called
    call_args = query.edit_message_text.call_args
    
    # Check main menu text
    assert "Добро пожаловать" in call_args.kwargs["text"]
    
    # Verify new session was created
    assert len(session_store._sessions) == 2


@pytest.mark.asyncio
async def test_command_handler_with_forum_topic(mock_update):
    """Test command handler supports forum topics."""
    # Convert to forum topic
    mock_update.effective_chat.type = "supergroup"
    mock_update.effective_chat.is_forum = True
    mock_update.effective_message.message_thread_id = 42
    
    sent_message = Mock(spec=Message)
    sent_message.message_id = 200
    sent_message.edit_reply_markup = AsyncMock()
    
    mock_update.effective_chat.send_message = AsyncMock(return_value=sent_message)
    
    context = Mock(spec=ContextTypes.DEFAULT_TYPE)
    
    await start_command(mock_update, context)
    
    # Verify message_thread_id was passed
    call_args = mock_update.effective_chat.send_message.call_args
    assert call_args.kwargs.get("message_thread_id") == 42
    
    # Verify session has thread_id
    session_id = list(session_store._sessions.keys())[0]
    session = session_store._sessions[session_id]
    assert session.message_thread_id == 42


@pytest.mark.asyncio
async def test_section_handler_error_handling():
    """Test section handler gracefully handles edit errors."""
    session = MenuSession(
        session_id="test-session-error",
        chat_id=12345,
        message_id=100,
        user_id=67890,
        message_thread_id=None,
    )
    
    # Mock callback query that raises error on edit
    query = AsyncMock(spec=CallbackQuery)
    query.edit_message_text = AsyncMock(side_effect=Exception("Message was deleted"))
    
    update = Mock(spec=Update)
    update.callback_query = query
    update.effective_user = Mock(id=67890)
    update.effective_chat = Mock(id=12345)
    
    context = Mock(spec=ContextTypes.DEFAULT_TYPE)
    
    # Should not raise exception
    await shop_handler(update, context, session)
    
    # Verify edit was attempted
    assert query.edit_message_text.called
