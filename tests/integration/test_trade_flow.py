"""Integration tests for trade request and mutation flows."""

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, Mock

import pytest
from telegram import CallbackQuery, Chat, Message, Update, User
from telegram.ext import ContextTypes

from bot.db.database import TradeOfferLine, TradeParticipantState, TradeSessionSummary
from bot.handlers.commands import trade_command, tradeadd_command, traderemove_command
from bot.handlers.sections.trade import (
    TRADE_ROUTE_ACCEPT,
    TRADE_ROUTE_CANCEL,
    TRADE_ROUTE_TOGGLE_READY,
    _reflect_trade_maintenance,
    trade_handler,
)
from bot.db.database import TradeMaintenanceResult, TradeReadyToggleResult
from bot.navigation.session import MenuSession, session_store


@pytest.fixture(autouse=True)
def clear_sessions():
    session_store._sessions.clear()
    session_store._callback_locks.clear()
    session_store._pending_inputs.clear()
    yield
    session_store._sessions.clear()
    session_store._callback_locks.clear()
    session_store._pending_inputs.clear()


def _participant(user_id: int, username: str, *, ready: bool = False, offers: list[TradeOfferLine] | None = None) -> TradeParticipantState:
    return TradeParticipantState(
        user_id=user_id,
        telegram_id=user_id,
        username=username,
        nickname=None,
        label=f"@{username}",
        is_ready=ready,
        offers=offers or [],
    )


def _trade_summary(*, status: str = "pending", request_message_id: int | None = 500, active_message_id: int | None = None) -> TradeSessionSummary:
    return TradeSessionSummary(
        trade_id=77,
        chat_id=-1001,
        message_thread_id=None,
        request_message_id=request_message_id,
        active_message_id=active_message_id,
        status=status,
        pending_expires_at=datetime.now(UTC) + timedelta(minutes=2),
        trade_expires_at=(datetime.now(UTC) + timedelta(minutes=10)) if status == "active" else None,
        created_at=datetime.now(UTC),
        accepted_at=datetime.now(UTC) if status == "active" else None,
        canceled_at=None,
        completed_at=None,
        cancel_reason=None,
        initiator=_participant(111, "ash"),
        target=_participant(222, "misty"),
    )


@pytest.mark.asyncio
async def test_trade_command_creates_request_by_reply() -> None:
    actor = Mock(spec=User)
    actor.id = 111
    actor.username = "ash"

    target = Mock(spec=User)
    target.id = 222
    target.username = "misty"
    target.is_bot = False

    chat = Mock(spec=Chat)
    chat.id = -1001
    chat.type = "supergroup"

    reply_message = Mock(spec=Message)
    reply_message.from_user = target
    reply_message.message_id = 41

    message = Mock(spec=Message)
    message.message_id = 42
    message.chat = chat
    message.from_user = actor
    message.reply_to_message = reply_message
    message.message_thread_id = None
    message.text = "/trade"

    sent_message = Mock(spec=Message)
    sent_message.message_id = 500
    sent_message.edit_reply_markup = AsyncMock()
    chat.send_message = AsyncMock(return_value=sent_message)

    update = Mock(spec=Update)
    update.effective_user = actor
    update.effective_chat = chat
    update.effective_message = message

    db = AsyncMock()
    db.get_or_create_user_status = AsyncMock(return_value=(1, False))
    db.consume_start_guide_flag = AsyncMock(return_value=False)
    db.create_trade_request = AsyncMock(return_value=_trade_summary())
    db.attach_trade_request_message = AsyncMock()
    application = Mock()
    application.bot_data = {"db": db}
    context = Mock(spec=ContextTypes.DEFAULT_TYPE)
    context.application = application

    await trade_command(update, context)

    assert db.create_trade_request.called
    assert chat.send_message.called
    assert sent_message.edit_reply_markup.called
    assert db.attach_trade_request_message.called


@pytest.mark.asyncio
async def test_trade_command_rejects_private_chat() -> None:
    actor = Mock(spec=User)
    actor.id = 111
    actor.username = "ash"

    chat = Mock(spec=Chat)
    chat.id = 111
    chat.type = "private"
    chat.send_message = AsyncMock()

    message = Mock(spec=Message)
    message.message_id = 42
    message.chat = chat
    message.from_user = actor
    message.message_thread_id = None
    message.text = "/trade @misty"
    message.reply_to_message = None

    update = Mock(spec=Update)
    update.effective_user = actor
    update.effective_chat = chat
    update.effective_message = message

    db = AsyncMock()
    db.get_or_create_user_status = AsyncMock(return_value=(1, False))
    db.consume_start_guide_flag = AsyncMock(return_value=False)
    application = Mock()
    application.bot_data = {"db": db}
    context = Mock(spec=ContextTypes.DEFAULT_TYPE)
    context.application = application

    await trade_command(update, context)

    assert chat.send_message.called
    sent_text = chat.send_message.call_args.args[0] if chat.send_message.call_args.args else chat.send_message.call_args.kwargs["text"]
    assert "только в чатах" in sent_text


@pytest.mark.asyncio
async def test_trade_command_creates_request_by_username() -> None:
    actor = Mock(spec=User)
    actor.id = 111
    actor.username = "ash"

    chat = Mock(spec=Chat)
    chat.id = -1001
    chat.type = "supergroup"

    message = Mock(spec=Message)
    message.message_id = 42
    message.chat = chat
    message.from_user = actor
    message.reply_to_message = None
    message.message_thread_id = None
    message.text = "/trade @misty"

    sent_message = Mock(spec=Message)
    sent_message.message_id = 500
    sent_message.edit_reply_markup = AsyncMock()
    chat.send_message = AsyncMock(return_value=sent_message)

    update = Mock(spec=Update)
    update.effective_user = actor
    update.effective_chat = chat
    update.effective_message = message

    db = AsyncMock()
    db.get_or_create_user_status = AsyncMock(return_value=(1, False))
    db.consume_start_guide_flag = AsyncMock(return_value=False)
    db.resolve_trade_target_by_username = AsyncMock(return_value=(222, "misty", None))
    db.create_trade_request = AsyncMock(return_value=_trade_summary())
    db.attach_trade_request_message = AsyncMock()
    application = Mock()
    application.bot_data = {"db": db}
    context = Mock(spec=ContextTypes.DEFAULT_TYPE)
    context.application = application

    await trade_command(update, context)

    assert db.resolve_trade_target_by_username.called
    assert db.create_trade_request.called


@pytest.mark.asyncio
async def test_trade_accept_callback_renders_active_trade() -> None:
    session = MenuSession(
        session_id="trade-pending",
        chat_id=-1001,
        message_id=500,
        user_id=222,
        message_thread_id=None,
        data={"trade_id": 77},
    )
    session_store._sessions[session.session_id] = session

    query = AsyncMock(spec=CallbackQuery)
    query.data = f"menu:{TRADE_ROUTE_ACCEPT}:{session.session_id}"
    query.message = Mock(spec=Message)
    query.edit_message_text = AsyncMock()

    user = Mock(spec=User)
    user.id = 222
    user.username = "misty"

    chat = Mock(spec=Chat)
    chat.id = -1001
    chat.type = "supergroup"

    message = Mock(spec=Message)
    message.message_id = 500
    message.chat = chat
    message.message_thread_id = None

    update = Mock(spec=Update)
    update.callback_query = query
    update.effective_user = user
    update.effective_chat = chat
    update.effective_message = message

    db = AsyncMock()
    db.accept_trade_request = AsyncMock(return_value=_trade_summary(status="active", active_message_id=500))
    application = Mock()
    application.bot_data = {"db": db}
    context = Mock(spec=ContextTypes.DEFAULT_TYPE)
    context.application = application

    await trade_handler(update, context, session)

    assert db.accept_trade_request.called
    assert query.edit_message_text.called
    assert "Активный обмен" in query.edit_message_text.call_args.kwargs["text"]


@pytest.mark.asyncio
async def test_trade_toggle_ready_rerenders_active_trade() -> None:
    session = MenuSession(
        session_id="trade-active",
        chat_id=-1001,
        message_id=500,
        user_id=111,
        message_thread_id=None,
        data={"trade_id": 77, "allowed_user_ids": [222]},
    )
    session_store._sessions[session.session_id] = session

    query = AsyncMock(spec=CallbackQuery)
    query.data = f"menu:{TRADE_ROUTE_TOGGLE_READY}:{session.session_id}"
    query.message = Mock(spec=Message)
    query.edit_message_text = AsyncMock()

    user = Mock(spec=User)
    user.id = 111
    user.username = "ash"

    chat = Mock(spec=Chat)
    chat.id = -1001
    chat.type = "supergroup"

    message = Mock(spec=Message)
    message.message_id = 500
    message.chat = chat
    message.message_thread_id = None

    update = Mock(spec=Update)
    update.callback_query = query
    update.effective_user = user
    update.effective_chat = chat
    update.effective_message = message

    trade = _trade_summary(status="active", active_message_id=500)
    trade.initiator.is_ready = True
    db = AsyncMock()
    db.toggle_trade_ready = AsyncMock(return_value=TradeReadyToggleResult(trade=trade, completed=False))
    application = Mock()
    application.bot_data = {"db": db}
    context = Mock(spec=ContextTypes.DEFAULT_TYPE)
    context.application = application

    await trade_handler(update, context, session)

    assert db.toggle_trade_ready.called
    assert query.edit_message_text.called
    assert "Активный обмен" in query.edit_message_text.call_args.kwargs["text"]


@pytest.mark.asyncio
async def test_trade_toggle_ready_completes_trade() -> None:
    session = MenuSession(
        session_id="trade-complete",
        chat_id=-1001,
        message_id=500,
        user_id=111,
        message_thread_id=None,
        data={"trade_id": 77, "allowed_user_ids": [222]},
    )
    session_store._sessions[session.session_id] = session

    query = AsyncMock(spec=CallbackQuery)
    query.data = f"menu:{TRADE_ROUTE_TOGGLE_READY}:{session.session_id}"
    query.message = Mock(spec=Message)
    query.message.reply_text = AsyncMock()
    query.edit_message_text = AsyncMock()

    user = Mock(spec=User)
    user.id = 111
    user.username = "ash"

    chat = Mock(spec=Chat)
    chat.id = -1001
    chat.type = "supergroup"

    message = Mock(spec=Message)
    message.message_id = 500
    message.chat = chat
    message.message_thread_id = None

    update = Mock(spec=Update)
    update.callback_query = query
    update.effective_user = user
    update.effective_chat = chat
    update.effective_message = message

    trade = _trade_summary(status="active", active_message_id=500)
    trade.initiator.offers = [TradeOfferLine(user_pokemon_id=101, pokemon_id=25, name="Pikachu", rarity="Rare")]
    trade.target.offers = [TradeOfferLine(user_pokemon_id=202, pokemon_id=133, name="Eevee", rarity="Common")]
    db = AsyncMock()
    db.toggle_trade_ready = AsyncMock(return_value=TradeReadyToggleResult(trade=trade, completed=True))
    application = Mock()
    application.bot_data = {"db": db}
    context = Mock(spec=ContextTypes.DEFAULT_TYPE)
    context.application = application

    await trade_handler(update, context, session)

    assert query.edit_message_text.called
    assert "Обмен завершён" in query.edit_message_text.call_args.kwargs["text"]
    assert "Передано: <b>1</b> на <b>1</b>" in query.edit_message_text.call_args.kwargs["text"]
    assert query.message.reply_text.called
    assert "Обмен совершен" in query.message.reply_text.call_args.args[0]
    assert "Pikachu [101]" in query.message.reply_text.call_args.args[0]
    assert "Eevee [202]" in query.message.reply_text.call_args.args[0]


@pytest.mark.asyncio
async def test_trade_cancel_pending_request_from_callback() -> None:
    session = MenuSession(
        session_id="trade-cancel",
        chat_id=-1001,
        message_id=500,
        user_id=222,
        message_thread_id=None,
        data={"trade_id": 77, "allowed_user_ids": [111]},
    )
    session_store._sessions[session.session_id] = session

    query = AsyncMock(spec=CallbackQuery)
    query.data = f"menu:{TRADE_ROUTE_CANCEL}:{session.session_id}"
    query.message = Mock(spec=Message)
    query.edit_message_text = AsyncMock()

    user = Mock(spec=User)
    user.id = 111
    user.username = "ash"

    chat = Mock(spec=Chat)
    chat.id = -1001
    chat.type = "supergroup"

    message = Mock(spec=Message)
    message.message_id = 500
    message.chat = chat
    message.message_thread_id = None

    update = Mock(spec=Update)
    update.callback_query = query
    update.effective_user = user
    update.effective_chat = chat
    update.effective_message = message

    db = AsyncMock()
    db.cancel_trade = AsyncMock(return_value=_trade_summary(status="canceled", request_message_id=500))
    application = Mock()
    application.bot_data = {"db": db}
    context = Mock(spec=ContextTypes.DEFAULT_TYPE)
    context.application = application

    await trade_handler(update, context, session)

    assert db.cancel_trade.called
    assert query.edit_message_text.called
    assert "Обмен отменён" in query.edit_message_text.call_args.kwargs["text"]


@pytest.mark.asyncio
async def test_tradeadd_command_updates_shared_trade_message() -> None:
    actor = Mock(spec=User)
    actor.id = 111
    actor.username = "ash"

    chat = Mock(spec=Chat)
    chat.id = 111
    chat.type = "private"
    chat.send_message = AsyncMock()

    message = Mock(spec=Message)
    message.message_id = 42
    message.chat = chat
    message.from_user = actor
    message.message_thread_id = None
    message.text = "/tradeadd 9001"

    update = Mock(spec=Update)
    update.effective_user = actor
    update.effective_chat = chat
    update.effective_message = message

    trade = _trade_summary(status="active", active_message_id=700)
    trade.initiator.offers = [TradeOfferLine(user_pokemon_id=9001, pokemon_id=25, name="Pikachu", rarity="Rare")]

    db = AsyncMock()
    db.get_or_create_user_status = AsyncMock(return_value=(1, False))
    db.consume_start_guide_flag = AsyncMock(return_value=False)
    db.add_trade_offer_pokemon = AsyncMock(return_value=trade)
    application = Mock()
    application.bot_data = {"db": db}
    bot = Mock()
    bot.edit_message_text = AsyncMock()
    context = Mock(spec=ContextTypes.DEFAULT_TYPE)
    context.application = application
    context.bot = bot

    await tradeadd_command(update, context)

    assert db.add_trade_offer_pokemon.called
    assert bot.edit_message_text.called
    assert chat.send_message.called


@pytest.mark.asyncio
async def test_traderemove_command_updates_shared_trade_message() -> None:
    actor = Mock(spec=User)
    actor.id = 111
    actor.username = "ash"

    chat = Mock(spec=Chat)
    chat.id = 111
    chat.type = "private"
    chat.send_message = AsyncMock()

    message = Mock(spec=Message)
    message.message_id = 42
    message.chat = chat
    message.from_user = actor
    message.message_thread_id = None
    message.text = "/traderemove 9001"

    update = Mock(spec=Update)
    update.effective_user = actor
    update.effective_chat = chat
    update.effective_message = message

    trade = _trade_summary(status="active", active_message_id=700)

    db = AsyncMock()
    db.get_or_create_user_status = AsyncMock(return_value=(1, False))
    db.consume_start_guide_flag = AsyncMock(return_value=False)
    db.remove_trade_offer_pokemon = AsyncMock(return_value=trade)
    application = Mock()
    application.bot_data = {"db": db}
    bot = Mock()
    bot.edit_message_text = AsyncMock()
    context = Mock(spec=ContextTypes.DEFAULT_TYPE)
    context.application = application
    context.bot = bot

    await traderemove_command(update, context)

    assert db.remove_trade_offer_pokemon.called
    assert bot.edit_message_text.called
    assert chat.send_message.called


@pytest.mark.asyncio
async def test_trade_maintenance_reflects_expired_messages() -> None:
    pending_trade = _trade_summary(status="pending", request_message_id=500)
    active_trade = _trade_summary(status="active", active_message_id=700)
    bot = Mock()
    bot.edit_message_text = AsyncMock()
    context = Mock(spec=ContextTypes.DEFAULT_TYPE)
    context.bot = bot

    await _reflect_trade_maintenance(
        context,
        TradeMaintenanceResult(
            expired_requests=[pending_trade],
            expired_active_trades=[active_trade],
        ),
    )

    assert bot.edit_message_text.call_count == 2
