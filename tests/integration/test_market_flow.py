"""Integration tests for market flows."""

from unittest.mock import AsyncMock, Mock

import pytest
from telegram import CallbackQuery, Chat, Message, Update, User
from telegram.ext import ContextTypes

from datetime import UTC, datetime, timedelta

from bot.db.database import (
    MarketBrowsePage,
    MarketBrowseState,
    MarketBuyRequestSummary,
    MarketListingSummary,
    MarketPurchaseResult,
    MarketRequestFulfillmentResult,
    ShopView,
)
from bot.handlers.commands import buyprice_command, sellprice_command
from bot.handlers.sections.market import (
    MARKET_PENDING_ACTION_BUY_PRICE,
    MARKET_PENDING_ACTION_SELL_PRICE,
    MARKET_ROUTE_ROOT,
    MARKET_ROUTE_CANCEL_REQUEST_1,
    MARKET_ROUTE_BUY_SELECT_1,
    MARKET_ROUTE_CONFIRM_BUY,
    MARKET_ROUTE_CONFIRM_SELL,
    MARKET_ROUTE_CONFIRM_FULFILL,
    MARKET_ROUTE_FULFILL_REQUEST_1,
    MARKET_ROUTE_START_SELL_PRICE,
    MARKET_ROUTE_START_BUY_PRICE,
    market_handler,
)
from bot.navigation.session import MenuSession, session_store


@pytest.fixture(autouse=True)
def clear_sessions() -> None:
    session_store._sessions.clear()
    session_store._callback_locks.clear()
    session_store._pending_inputs.clear()
    yield
    session_store._sessions.clear()
    session_store._callback_locks.clear()
    session_store._pending_inputs.clear()


@pytest.mark.asyncio
async def test_market_start_sell_price_sets_pending_input() -> None:
    session = MenuSession(
        session_id="market-session",
        chat_id=12345,
        message_id=555,
        user_id=12345,
        message_thread_id=None,
        data={
            "market_entry_action": "sell",
            "market_entry_pokemon_id": 25,
            "market_entry_pokemon_name": "Pikachu",
            "market_entry_user_pokemon_id": 250,
        },
    )
    query = AsyncMock(spec=CallbackQuery)
    query.data = f"menu:{MARKET_ROUTE_START_SELL_PRICE}:market-session"
    query.message = Mock(spec=Message)
    query.message.photo = []
    query.edit_message_text = AsyncMock()

    update = Mock(spec=Update)
    update.callback_query = query
    update.effective_user = Mock(spec=User)
    update.effective_user.id = 12345

    context = Mock(spec=ContextTypes.DEFAULT_TYPE)
    db = AsyncMock()
    db.get_market_sell_precheck_error = AsyncMock(return_value=None)
    application = Mock()
    application.bot_data = {"db": db}
    context.application = application

    await market_handler(update, context, session)

    pending = session_store.get_pending_input(chat_id=12345, user_id=12345)
    assert pending is not None
    assert pending.action == MARKET_PENDING_ACTION_SELL_PRICE


@pytest.mark.asyncio
async def test_market_start_buy_price_sets_pending_input() -> None:
    session = MenuSession(
        session_id="market-session",
        chat_id=12345,
        message_id=555,
        user_id=12345,
        message_thread_id=None,
        data={
            "market_entry_action": "buy_request",
            "market_entry_pokemon_id": 25,
            "market_entry_pokemon_name": "Pikachu",
        },
    )
    query = AsyncMock(spec=CallbackQuery)
    query.data = f"menu:{MARKET_ROUTE_START_BUY_PRICE}:market-session"
    query.message = Mock(spec=Message)
    query.message.photo = []
    query.edit_message_text = AsyncMock()

    update = Mock(spec=Update)
    update.callback_query = query
    update.effective_user = Mock(spec=User)
    update.effective_user.id = 12345

    context = Mock(spec=ContextTypes.DEFAULT_TYPE)
    db = AsyncMock()
    db.get_market_buy_request_precheck_error = AsyncMock(return_value=None)
    application = Mock()
    application.bot_data = {"db": db}
    context.application = application

    await market_handler(update, context, session)

    pending = session_store.get_pending_input(chat_id=12345, user_id=12345)
    assert pending is not None
    assert pending.action == MARKET_PENDING_ACTION_BUY_PRICE


@pytest.mark.asyncio
async def test_market_start_sell_price_shows_reason_when_slots_full() -> None:
    session = MenuSession(
        session_id="market-session",
        chat_id=12345,
        message_id=555,
        user_id=12345,
        message_thread_id=None,
        data={
            "market_entry_action": "sell",
            "market_entry_pokemon_id": 25,
            "market_entry_pokemon_name": "Pikachu",
            "market_entry_user_pokemon_id": 250,
        },
    )
    query = AsyncMock(spec=CallbackQuery)
    query.data = f"menu:{MARKET_ROUTE_START_SELL_PRICE}:market-session"
    query.message = Mock(spec=Message)
    query.message.photo = []
    query.edit_message_text = AsyncMock()
    query.answer = AsyncMock()
    query.from_user = Mock(spec=User)
    query.from_user.id = 12345
    query.from_user.username = "ash"

    update = Mock(spec=Update)
    update.callback_query = query
    update.effective_user = query.from_user

    db = AsyncMock()
    db.get_market_sell_precheck_error = AsyncMock(
        return_value="Нельзя создать лот: у вас уже заняты все 2 слота продажи."
    )
    application = Mock()
    application.bot_data = {"db": db}
    context = Mock(spec=ContextTypes.DEFAULT_TYPE)
    context.application = application

    await market_handler(update, context, session)

    assert session_store.get_pending_input(chat_id=12345, user_id=12345) is None
    assert query.answer.called
    assert "слота продажи" in query.answer.call_args.args[0]


@pytest.mark.asyncio
async def test_market_start_sell_price_shows_reason_when_no_commission_money() -> None:
    session = MenuSession(
        session_id="market-session",
        chat_id=12345,
        message_id=555,
        user_id=12345,
        message_thread_id=None,
        data={
            "market_entry_action": "sell",
            "market_entry_pokemon_id": 25,
            "market_entry_pokemon_name": "Pikachu",
            "market_entry_user_pokemon_id": 250,
        },
    )
    query = AsyncMock(spec=CallbackQuery)
    query.data = f"menu:{MARKET_ROUTE_START_SELL_PRICE}:market-session"
    query.message = Mock(spec=Message)
    query.message.photo = []
    query.edit_message_text = AsyncMock()
    query.answer = AsyncMock()
    query.from_user = Mock(spec=User)
    query.from_user.id = 12345
    query.from_user.username = "ash"

    update = Mock(spec=Update)
    update.callback_query = query
    update.effective_user = query.from_user

    db = AsyncMock()
    db.get_market_sell_precheck_error = AsyncMock(
        return_value="Нельзя создать лот: не хватает pokecoin даже на стартовую комиссию."
    )
    application = Mock()
    application.bot_data = {"db": db}
    context = Mock(spec=ContextTypes.DEFAULT_TYPE)
    context.application = application

    await market_handler(update, context, session)

    assert session_store.get_pending_input(chat_id=12345, user_id=12345) is None
    assert query.answer.called
    assert "стартовую комиссию" in query.answer.call_args.args[0]


@pytest.mark.asyncio
async def test_market_start_sell_price_shows_reason_when_already_listed() -> None:
    session = MenuSession(
        session_id="market-session",
        chat_id=12345,
        message_id=555,
        user_id=12345,
        message_thread_id=None,
        data={
            "market_entry_action": "sell",
            "market_entry_pokemon_id": 25,
            "market_entry_pokemon_name": "Pikachu",
            "market_entry_user_pokemon_id": 250,
        },
    )
    query = AsyncMock(spec=CallbackQuery)
    query.data = f"menu:{MARKET_ROUTE_START_SELL_PRICE}:market-session"
    query.message = Mock(spec=Message)
    query.message.photo = []
    query.edit_message_text = AsyncMock()
    query.answer = AsyncMock()
    query.from_user = Mock(spec=User)
    query.from_user.id = 12345
    query.from_user.username = "ash"

    update = Mock(spec=Update)
    update.callback_query = query
    update.effective_user = query.from_user

    db = AsyncMock()
    db.get_market_sell_precheck_error = AsyncMock(
        return_value="Нельзя создать лот: этот покемон уже выставлен на рынок."
    )
    application = Mock()
    application.bot_data = {"db": db}
    context = Mock(spec=ContextTypes.DEFAULT_TYPE)
    context.application = application

    await market_handler(update, context, session)

    assert session_store.get_pending_input(chat_id=12345, user_id=12345) is None
    assert query.answer.called
    assert "уже выставлен" in query.answer.call_args.args[0]


@pytest.mark.asyncio
async def test_market_start_buy_price_shows_reason_when_request_slots_full() -> None:
    session = MenuSession(
        session_id="market-session",
        chat_id=12345,
        message_id=555,
        user_id=12345,
        message_thread_id=None,
        data={
            "market_entry_action": "buy_request",
            "market_entry_pokemon_id": 25,
            "market_entry_pokemon_name": "Pikachu",
        },
    )
    query = AsyncMock(spec=CallbackQuery)
    query.data = f"menu:{MARKET_ROUTE_START_BUY_PRICE}:market-session"
    query.message = Mock(spec=Message)
    query.message.photo = []
    query.edit_message_text = AsyncMock()
    query.answer = AsyncMock()
    query.from_user = Mock(spec=User)
    query.from_user.id = 12345
    query.from_user.username = "ash"

    update = Mock(spec=Update)
    update.callback_query = query
    update.effective_user = query.from_user

    db = AsyncMock()
    db.get_market_buy_request_precheck_error = AsyncMock(
        return_value="Нельзя создать заявку: у вас уже заняты все 5 слотов заявок."
    )
    application = Mock()
    application.bot_data = {"db": db}
    context = Mock(spec=ContextTypes.DEFAULT_TYPE)
    context.application = application

    await market_handler(update, context, session)

    assert session_store.get_pending_input(chat_id=12345, user_id=12345) is None
    assert query.answer.called
    assert "слотов заявок" in query.answer.call_args.args[0]


@pytest.mark.asyncio
async def test_market_start_buy_price_shows_reason_when_duplicate_request_exists() -> None:
    session = MenuSession(
        session_id="market-session",
        chat_id=12345,
        message_id=555,
        user_id=12345,
        message_thread_id=None,
        data={
            "market_entry_action": "buy_request",
            "market_entry_pokemon_id": 25,
            "market_entry_pokemon_name": "Pikachu",
        },
    )
    query = AsyncMock(spec=CallbackQuery)
    query.data = f"menu:{MARKET_ROUTE_START_BUY_PRICE}:market-session"
    query.message = Mock(spec=Message)
    query.message.photo = []
    query.edit_message_text = AsyncMock()
    query.answer = AsyncMock()
    query.from_user = Mock(spec=User)
    query.from_user.id = 12345
    query.from_user.username = "ash"

    update = Mock(spec=Update)
    update.callback_query = query
    update.effective_user = query.from_user

    db = AsyncMock()
    db.get_market_buy_request_precheck_error = AsyncMock(
        return_value="Нельзя создать заявку: у вас уже есть активная заявка на этого покемона."
    )
    application = Mock()
    application.bot_data = {"db": db}
    context = Mock(spec=ContextTypes.DEFAULT_TYPE)
    context.application = application

    await market_handler(update, context, session)

    assert session_store.get_pending_input(chat_id=12345, user_id=12345) is None
    assert query.answer.called
    assert "активная заявка" in query.answer.call_args.args[0]


@pytest.mark.asyncio
async def test_market_confirm_sell_allows_relisting_after_historical_listing() -> None:
    session = MenuSession(
        session_id="market-relist-session",
        chat_id=12345,
        message_id=555,
        user_id=12345,
        message_thread_id=None,
        data={
            "market_entry_action": "sell",
            "market_entry_pokemon_id": 25,
            "market_entry_pokemon_name": "Pikachu",
            "market_entry_user_pokemon_id": 250,
            "market_sell_price": 2500,
        },
    )

    query = AsyncMock(spec=CallbackQuery)
    query.data = f"menu:{MARKET_ROUTE_CONFIRM_SELL}:market-relist-session"
    query.message = Mock(spec=Message)
    query.message.photo = []
    query.edit_message_text = AsyncMock()
    query.answer = AsyncMock()
    query.from_user = Mock(spec=User)
    query.from_user.id = 12345
    query.from_user.username = "ash"
    query.from_user.first_name = "Ash"

    update = Mock(spec=Update)
    update.callback_query = query
    update.effective_user = query.from_user

    db = AsyncMock()
    db.create_market_listing = AsyncMock(
        return_value=MarketListingSummary(
            listing_id=77,
            seller_user_id=1,
            seller_label="@ash",
            user_pokemon_id=250,
            pokemon_id=25,
            name="Pikachu",
            rarity="Rare",
            pokemon_type="electric",
            price=2500,
            status="active",
            listed_at=datetime.now(UTC),
            expires_at=datetime.now(UTC) + timedelta(days=5),
            days_remaining=5,
            image_credit_id=None,
        )
    )
    application = Mock()
    application.bot_data = {"db": db}
    context = Mock(spec=ContextTypes.DEFAULT_TYPE)
    context.application = application

    await market_handler(update, context, session)

    assert db.create_market_listing.called
    assert query.edit_message_text.called
    rendered_text = query.edit_message_text.call_args.kwargs["text"]
    assert "Лот создан" in rendered_text


@pytest.mark.asyncio
async def test_sellprice_command_builds_confirmation_flow() -> None:
    session_store.set_pending_input(
        action=MARKET_PENDING_ACTION_SELL_PRICE,
        chat_id=12345,
        user_id=12345,
        source_message_id=777,
        source_message_thread_id=None,
        data={
            "market_entry_action": "sell",
            "market_entry_pokemon_id": 25,
            "market_entry_pokemon_name": "Pikachu",
            "market_entry_user_pokemon_id": 250,
        },
    )

    user = Mock(spec=User)
    user.id = 12345
    user.username = "ash"
    user.first_name = "Ash"

    chat = Mock(spec=Chat)
    chat.id = 12345
    chat.type = "private"
    chat.send_message = AsyncMock()

    message = Mock(spec=Message)
    message.message_id = 778
    message.chat = chat
    message.message_thread_id = None
    message.text = "/sellprice 2500 250"

    update = Mock(spec=Update)
    update.effective_chat = chat
    update.effective_user = user
    update.effective_message = message

    db = AsyncMock()
    db.get_market_sell_precheck_error = AsyncMock(return_value=None)
    db.get_user_pokemon_entry = AsyncMock(
        return_value=Mock(
            pokemon_id=25,
            sample_user_pokemon_id=250,
            name="Pikachu",
            is_locked=False,
        )
    )
    db.get_shop_view = AsyncMock(
        return_value=ShopView(
            user_id=1,
            balance=0,
            pokecoin_balance=120,
            ultraball_quantity=0,
            masterball_quantity=0,
            epic_pity_counter=0,
            legendary_pity_counter=0,
            bonus_available=0,
            bonus_ready_in_seconds=0,
        )
    )
    application = Mock()
    application.bot_data = {"db": db}
    context = Mock(spec=ContextTypes.DEFAULT_TYPE)
    context.application = application
    context.bot = Mock()
    context.bot.edit_message_caption = AsyncMock()
    context.bot.edit_message_text = AsyncMock()

    await sellprice_command(update, context)

    assert db.get_shop_view.called
    assert context.bot.edit_message_caption.called or context.bot.edit_message_text.called
    assert chat.send_message.called
    assert session_store.get_pending_input(chat_id=12345, user_id=12345) is None


@pytest.mark.asyncio
async def test_buyprice_command_builds_confirmation_flow() -> None:
    session_store.set_pending_input(
        action=MARKET_PENDING_ACTION_BUY_PRICE,
        chat_id=12345,
        user_id=12345,
        source_message_id=777,
        source_message_thread_id=None,
        data={
            "market_entry_action": "buy_request",
            "market_entry_pokemon_id": 25,
            "market_entry_pokemon_name": "Pikachu",
        },
    )

    user = Mock(spec=User)
    user.id = 12345
    user.username = "ash"
    user.first_name = "Ash"

    chat = Mock(spec=Chat)
    chat.id = 12345
    chat.type = "private"
    chat.send_message = AsyncMock()

    message = Mock(spec=Message)
    message.message_id = 778
    message.chat = chat
    message.message_thread_id = None
    message.text = "/buyprice 2500 25"

    update = Mock(spec=Update)
    update.effective_chat = chat
    update.effective_user = user
    update.effective_message = message

    db = AsyncMock()
    db.get_market_buy_request_precheck_error = AsyncMock(return_value=None)
    db.get_pokemon_catalog_entry = AsyncMock(
        return_value=Mock(
            pokemon_id=25,
            name="Pikachu",
        )
    )
    db.get_shop_view = AsyncMock(
        return_value=ShopView(
            user_id=1,
            balance=0,
            pokecoin_balance=3500,
            ultraball_quantity=0,
            masterball_quantity=0,
            epic_pity_counter=0,
            legendary_pity_counter=0,
            bonus_available=0,
            bonus_ready_in_seconds=0,
        )
    )
    application = Mock()
    application.bot_data = {"db": db}
    context = Mock(spec=ContextTypes.DEFAULT_TYPE)
    context.application = application
    context.bot = Mock()
    context.bot.edit_message_caption = AsyncMock()
    context.bot.edit_message_text = AsyncMock()

    await buyprice_command(update, context)

    assert db.get_shop_view.called
    assert context.bot.edit_message_caption.called or context.bot.edit_message_text.called
    assert chat.send_message.called
    assert session_store.get_pending_input(chat_id=12345, user_id=12345) is None


@pytest.mark.asyncio
async def test_market_buy_select_and_confirm_flow() -> None:
    listing = MarketListingSummary(
        listing_id=1,
        seller_user_id=777,
        seller_label="@misty",
        user_pokemon_id=250,
        pokemon_id=25,
        name="Pikachu",
        rarity="Rare",
        pokemon_type="electric",
        price=500,
        status="active",
        listed_at=datetime.now(UTC),
        expires_at=datetime.now(UTC) + timedelta(days=5),
        days_remaining=5,
        image_credit_id=None,
    )
    session = MenuSession(
        session_id="buy-session",
        chat_id=12345,
        message_id=600,
        user_id=12345,
        message_thread_id=None,
        data={
            "market_buy_filters": MarketBrowseState().to_session_payload(),
            "market_buy_listing_ids": [1],
        },
    )

    query = AsyncMock(spec=CallbackQuery)
    query.data = f"menu:{MARKET_ROUTE_BUY_SELECT_1}:buy-session"
    query.message = Mock(spec=Message)
    query.message.photo = []
    query.edit_message_text = AsyncMock()
    query.from_user = Mock(spec=User)
    query.from_user.id = 12345
    query.from_user.username = "ash"
    query.from_user.first_name = "Ash"
    query.answer = AsyncMock()

    update = Mock(spec=Update)
    update.callback_query = query
    update.effective_user = query.from_user

    db = AsyncMock()
    db.get_market_listings_page = AsyncMock(
        return_value=MarketBrowsePage(
            entries=[listing],
            filter_state=MarketBrowseState(),
            total_entries=1,
            current_page=1,
            total_pages=1,
            current_balance=900,
        )
    )
    context = Mock(spec=ContextTypes.DEFAULT_TYPE)
    application = Mock()
    application.bot_data = {"db": db}
    context.application = application

    await market_handler(update, context, session)
    assert query.edit_message_text.called

    confirm_session = MenuSession(
        session_id="confirm-session",
        chat_id=12345,
        message_id=600,
        user_id=12345,
        message_thread_id=None,
        data={"market_selected_listing_id": 1},
    )
    confirm_query = AsyncMock(spec=CallbackQuery)
    confirm_query.data = f"menu:{MARKET_ROUTE_CONFIRM_BUY}:confirm-session"
    confirm_query.message = Mock(spec=Message)
    confirm_query.message.photo = []
    confirm_query.edit_message_text = AsyncMock()
    confirm_query.from_user = query.from_user
    confirm_query.answer = AsyncMock()
    confirm_update = Mock(spec=Update)
    confirm_update.callback_query = confirm_query
    confirm_update.effective_user = query.from_user

    db.get_market_buy_listing_precheck_error = AsyncMock(return_value=None)
    db.purchase_market_listing = AsyncMock(
        return_value=MarketPurchaseResult(
            listing=listing,
            buyer_user_id=12345,
            seller_user_id=777,
            price=500,
        )
    )

    await market_handler(confirm_update, context, confirm_session)
    assert db.purchase_market_listing.called
    assert confirm_query.edit_message_text.called


@pytest.mark.asyncio
async def test_market_confirm_buy_shows_reason_when_listing_already_sold() -> None:
    session = MenuSession(
        session_id="confirm-session",
        chat_id=12345,
        message_id=600,
        user_id=12345,
        message_thread_id=None,
        data={"market_selected_listing_id": 1},
    )
    query = AsyncMock(spec=CallbackQuery)
    query.data = f"menu:{MARKET_ROUTE_CONFIRM_BUY}:confirm-session"
    query.message = Mock(spec=Message)
    query.message.photo = []
    query.edit_message_text = AsyncMock()
    query.from_user = Mock(spec=User)
    query.from_user.id = 12345
    query.from_user.username = "ash"
    query.answer = AsyncMock()

    update = Mock(spec=Update)
    update.callback_query = query
    update.effective_user = query.from_user

    db = AsyncMock()
    db.get_market_buy_listing_precheck_error = AsyncMock(return_value="Этот лот уже купили.")
    context = Mock(spec=ContextTypes.DEFAULT_TYPE)
    application = Mock()
    application.bot_data = {"db": db}
    context.application = application

    await market_handler(update, context, session)

    assert db.purchase_market_listing.call_count == 0
    assert query.answer.called
    assert "уже купили" in query.answer.call_args.args[0]


@pytest.mark.asyncio
async def test_market_cancel_request_flow() -> None:
    request = MarketBuyRequestSummary(
        request_id=5,
        requester_user_id=12345,
        requester_label="@ash",
        pokemon_id=25,
        name="Pikachu",
        rarity="Rare",
        pokemon_type="electric",
        price=700,
        reserved_amount=700,
        status="active",
        created_at=datetime.now(UTC),
        image_credit_id=None,
        matching_user_pokemon_id=None,
    )
    session = MenuSession(
        session_id="request-session",
        chat_id=12345,
        message_id=600,
        user_id=12345,
        message_thread_id=None,
        data={"my_market_request_ids": [5]},
    )
    query = AsyncMock(spec=CallbackQuery)
    query.data = f"menu:{MARKET_ROUTE_CANCEL_REQUEST_1}:request-session"
    query.message = Mock(spec=Message)
    query.message.photo = []
    query.edit_message_text = AsyncMock()
    query.from_user = Mock(spec=User)
    query.from_user.id = 12345
    query.from_user.username = "ash"
    query.from_user.first_name = "Ash"
    query.answer = AsyncMock()

    update = Mock(spec=Update)
    update.callback_query = query
    update.effective_user = query.from_user

    db = AsyncMock()
    db.cancel_market_buy_request = AsyncMock(return_value=request)
    db.get_my_market_buy_requests = AsyncMock(return_value=[])
    context = Mock(spec=ContextTypes.DEFAULT_TYPE)
    application = Mock()
    application.bot_data = {"db": db}
    context.application = application

    await market_handler(update, context, session)

    assert db.cancel_market_buy_request.called
    assert query.edit_message_text.called


@pytest.mark.asyncio
async def test_market_fulfill_request_flow() -> None:
    request = MarketBuyRequestSummary(
        request_id=9,
        requester_user_id=777,
        requester_label="@misty",
        pokemon_id=25,
        name="Pikachu",
        rarity="Rare",
        pokemon_type="electric",
        price=900,
        reserved_amount=900,
        status="active",
        created_at=datetime.now(UTC),
        image_credit_id=None,
        matching_user_pokemon_id=250,
    )
    session = MenuSession(
        session_id="sell-session",
        chat_id=12345,
        message_id=601,
        user_id=12345,
        message_thread_id=None,
        data={
            "market_sell_request_ids": [9],
            "market_sell_request_pokemon_ids": [250],
        },
    )
    query = AsyncMock(spec=CallbackQuery)
    query.data = f"menu:{MARKET_ROUTE_FULFILL_REQUEST_1}:sell-session"
    query.message = Mock(spec=Message)
    query.message.photo = []
    query.edit_message_text = AsyncMock()
    query.from_user = Mock(spec=User)
    query.from_user.id = 12345
    query.from_user.username = "ash"
    query.from_user.first_name = "Ash"
    query.answer = AsyncMock()

    update = Mock(spec=Update)
    update.callback_query = query
    update.effective_user = query.from_user

    db = AsyncMock()
    db.get_sellable_market_buy_requests = AsyncMock(return_value=[request])
    context = Mock(spec=ContextTypes.DEFAULT_TYPE)
    application = Mock()
    application.bot_data = {"db": db}
    context.application = application

    await market_handler(update, context, session)
    assert query.edit_message_text.called

    confirm_session = MenuSession(
        session_id="fulfill-confirm",
        chat_id=12345,
        message_id=601,
        user_id=12345,
        message_thread_id=None,
        data={
            "market_selected_request_id": 9,
            "market_selected_request_pokemon_id": 250,
        },
    )
    confirm_query = AsyncMock(spec=CallbackQuery)
    confirm_query.data = f"menu:{MARKET_ROUTE_CONFIRM_FULFILL}:fulfill-confirm"
    confirm_query.message = Mock(spec=Message)
    confirm_query.message.photo = []
    confirm_query.edit_message_text = AsyncMock()
    confirm_query.from_user = query.from_user
    confirm_query.answer = AsyncMock()

    confirm_update = Mock(spec=Update)
    confirm_update.callback_query = confirm_query
    confirm_update.effective_user = confirm_query.from_user

    db.get_market_request_fulfill_precheck_error = AsyncMock(return_value=None)
    db.fulfill_market_buy_request = AsyncMock(
        return_value=MarketRequestFulfillmentResult(
            request=request,
            seller_user_id=12345,
            buyer_user_id=777,
            transferred_user_pokemon_id=250,
            price=900,
        )
    )

    await market_handler(confirm_update, context, confirm_session)
    assert db.fulfill_market_buy_request.called
    assert confirm_query.edit_message_text.called


@pytest.mark.asyncio
async def test_market_confirm_fulfill_shows_reason_when_request_canceled() -> None:
    session = MenuSession(
        session_id="fulfill-confirm",
        chat_id=12345,
        message_id=601,
        user_id=12345,
        message_thread_id=None,
        data={
            "market_selected_request_id": 9,
            "market_selected_request_pokemon_id": 250,
        },
    )
    query = AsyncMock(spec=CallbackQuery)
    query.data = f"menu:{MARKET_ROUTE_CONFIRM_FULFILL}:fulfill-confirm"
    query.message = Mock(spec=Message)
    query.message.photo = []
    query.edit_message_text = AsyncMock()
    query.from_user = Mock(spec=User)
    query.from_user.id = 12345
    query.from_user.username = "ash"
    query.answer = AsyncMock()

    update = Mock(spec=Update)
    update.callback_query = query
    update.effective_user = query.from_user

    db = AsyncMock()
    db.get_market_request_fulfill_precheck_error = AsyncMock(return_value="Эту заявку уже отменили.")
    context = Mock(spec=ContextTypes.DEFAULT_TYPE)
    application = Mock()
    application.bot_data = {"db": db}
    context.application = application

    await market_handler(update, context, session)

    assert db.fulfill_market_buy_request.call_count == 0
    assert query.answer.called
    assert "уже отменили" in query.answer.call_args.args[0]


@pytest.mark.asyncio
async def test_market_root_uses_caption_edit_for_photo_messages() -> None:
    session = MenuSession(
        session_id="root-session",
        chat_id=12345,
        message_id=700,
        user_id=12345,
        message_thread_id=None,
        data={},
    )
    query = AsyncMock(spec=CallbackQuery)
    query.data = f"menu:{MARKET_ROUTE_ROOT}:root-session"
    query.message = Mock(spec=Message)
    query.message.photo = [Mock()]
    query.edit_message_caption = AsyncMock()
    query.edit_message_text = AsyncMock()
    query.from_user = Mock(spec=User)
    query.from_user.id = 12345
    query.from_user.username = "ash"
    query.from_user.first_name = "Ash"
    query.answer = AsyncMock()

    update = Mock(spec=Update)
    update.callback_query = query
    update.effective_user = query.from_user

    context = Mock(spec=ContextTypes.DEFAULT_TYPE)

    await market_handler(update, context, session)

    assert query.edit_message_caption.called
    assert not query.edit_message_text.called


@pytest.mark.asyncio
async def test_market_confirm_buy_without_money_shows_toast() -> None:
    session = MenuSession(
        session_id="poor-confirm",
        chat_id=12345,
        message_id=602,
        user_id=12345,
        message_thread_id=None,
        data={
            "market_selected_listing_id": 1,
            "market_selected_listing_price": 500,
        },
    )
    query = AsyncMock(spec=CallbackQuery)
    query.data = f"menu:{MARKET_ROUTE_CONFIRM_BUY}:poor-confirm"
    query.message = Mock(spec=Message)
    query.message.photo = []
    query.edit_message_text = AsyncMock()
    query.from_user = Mock(spec=User)
    query.from_user.id = 12345
    query.from_user.username = "ash"
    query.from_user.first_name = "Ash"
    query.answer = AsyncMock()

    update = Mock(spec=Update)
    update.callback_query = query
    update.effective_user = query.from_user

    db = AsyncMock()
    db.get_market_buy_listing_precheck_error = AsyncMock(return_value=None)
    db.get_shop_view = AsyncMock(
        return_value=ShopView(
            user_id=1,
            balance=0,
            pokecoin_balance=100,
            ultraball_quantity=0,
            masterball_quantity=0,
            epic_pity_counter=0,
            legendary_pity_counter=0,
            bonus_available=0,
            bonus_ready_in_seconds=0,
        )
    )
    context = Mock(spec=ContextTypes.DEFAULT_TYPE)
    application = Mock()
    application.bot_data = {"db": db}
    context.application = application

    await market_handler(update, context, session)

    assert db.purchase_market_listing.call_count == 0
    assert query.answer.called
    assert "pokecoin" in query.answer.call_args.args[0].lower()


@pytest.mark.asyncio
async def test_sellprice_command_can_work_without_pending_context() -> None:
    user = Mock(spec=User)
    user.id = 12345
    user.username = "ash"
    user.first_name = "Ash"

    chat = Mock(spec=Chat)
    chat.id = 12345
    chat.type = "private"
    chat.send_message = AsyncMock()

    sent_confirmation = Mock(spec=Message)
    sent_confirmation.message_id = 901
    sent_confirmation.edit_reply_markup = AsyncMock()
    chat.send_message = AsyncMock(return_value=sent_confirmation)

    message = Mock(spec=Message)
    message.message_id = 778
    message.chat = chat
    message.message_thread_id = None
    message.text = "/sellprice 2500 250"

    update = Mock(spec=Update)
    update.effective_chat = chat
    update.effective_user = user
    update.effective_message = message

    db = AsyncMock()
    db.get_market_sell_precheck_error = AsyncMock(return_value=None)
    db.get_user_pokemon_entry = AsyncMock(
        return_value=Mock(
            pokemon_id=25,
            sample_user_pokemon_id=250,
            name="Pikachu",
            is_locked=False,
        )
    )
    db.get_shop_view = AsyncMock(
        return_value=ShopView(
            user_id=1,
            balance=0,
            pokecoin_balance=300,
            ultraball_quantity=0,
            masterball_quantity=0,
            epic_pity_counter=0,
            legendary_pity_counter=0,
            bonus_available=0,
            bonus_ready_in_seconds=0,
        )
    )
    application = Mock()
    application.bot_data = {"db": db}
    context = Mock(spec=ContextTypes.DEFAULT_TYPE)
    context.application = application
    context.bot = Mock()
    context.bot.edit_message_caption = AsyncMock()
    context.bot.edit_message_text = AsyncMock()

    await sellprice_command(update, context)

    assert chat.send_message.called
    assert sent_confirmation.edit_reply_markup.called
