"""Integration-style tests for shop callbacks with mocked DB operations."""

from unittest.mock import AsyncMock, Mock

import pytest
from telegram import CallbackQuery, Chat, Message, Update, User

from bot.db.database import BonusNotReadyError, InsufficientFundsError, ItemPurchaseResult, PokemonReward, ShopView, SpinResult
from bot.handlers.sections.shop import shop_handler
from bot.navigation.session import MenuSession, session_store


@pytest.fixture(autouse=True)
def clear_sessions():
    session_store._sessions.clear()
    session_store._callback_locks.clear()
    yield
    session_store._sessions.clear()
    session_store._callback_locks.clear()


def _make_update(section: str, session: MenuSession) -> Update:
    user = Mock(spec=User)
    user.id = session.user_id
    user.username = "ash"
    user.first_name = "Ash"

    chat = Mock(spec=Chat)
    chat.id = session.chat_id
    chat.type = "private"

    message = Mock(spec=Message)
    message.message_id = session.message_id
    message.chat = chat
    message.message_thread_id = session.message_thread_id

    query = AsyncMock(spec=CallbackQuery)
    query.id = "callback-id"
    query.data = f"menu:{section}:{session.session_id}"
    query.message = message
    query.edit_message_text = AsyncMock()

    update = Mock(spec=Update)
    update.callback_query = query
    update.effective_user = user
    update.effective_chat = chat
    update.effective_message = message
    return update


def _make_context(db: AsyncMock) -> Mock:
    application = Mock()
    application.bot_data = {"db": db}
    application.bot = AsyncMock()
    context = Mock()
    context.application = application
    context.bot = application.bot
    return context


def _shop_view(balance: int = 2500) -> ShopView:
    return ShopView(
        user_id=1,
        balance=balance,
        pokecoin_balance=0,
        ultraball_quantity=1,
        masterball_quantity=0,
        epic_pity_counter=3,
        legendary_pity_counter=7,
        bonus_available=125,
        bonus_ready_in_seconds=0,
    )


@pytest.mark.asyncio
async def test_shop_bonus_claim_updates_message() -> None:
    session = MenuSession("session-1", 1, 100, None, 1)
    db = AsyncMock()
    db.claim_daily_bonus = AsyncMock(return_value=Mock(amount_claimed=125, next_bonus_in_seconds=3600, shop_view=_shop_view(2625)))
    context = _make_context(db)
    update = _make_update("shop_bonus", session)

    await shop_handler(update, context, session)

    assert update.callback_query.edit_message_text.called
    text = update.callback_query.edit_message_text.call_args.kwargs["text"]
    assert "Вы получили" in text
    assert "теперь у вас" in text


@pytest.mark.asyncio
async def test_main_shop_shows_categories() -> None:
    session = MenuSession("session-main", 1, 100, None, 1)
    db = AsyncMock()
    db.get_shop_view = AsyncMock(return_value=_shop_view(100))
    context = _make_context(db)
    update = _make_update("shop", session)

    await shop_handler(update, context, session)

    button_texts = [
        button.text
        for row in update.callback_query.edit_message_text.call_args.kwargs["reply_markup"].inline_keyboard
        for button in row
    ]
    assert "🎮 Покемоны" in button_texts
    assert "🎒 Предметы" in button_texts
    assert "🎁 Бонус" in button_texts


@pytest.mark.asyncio
async def test_pokemon_submenu_hides_only_x5() -> None:
    session = MenuSession("session-pokemon", 1, 100, None, 1)
    db = AsyncMock()
    db.get_shop_view = AsyncMock(return_value=_shop_view(600))
    context = _make_context(db)
    update = _make_update("shop_pokemon", session)

    await shop_handler(update, context, session)

    button_texts = [
        button.text
        for row in update.callback_query.edit_message_text.call_args.kwargs["reply_markup"].inline_keyboard
        for button in row
    ]
    assert "🎲 Случайный персонаж: 💵500" in button_texts
    assert "🎲 Случайный персонаж x5: 💵2500" not in button_texts


@pytest.mark.asyncio
async def test_shop_bonus_cooldown_shows_remaining_time() -> None:
    session = MenuSession("session-2", 1, 100, None, 1)
    db = AsyncMock()
    db.claim_daily_bonus = AsyncMock(side_effect=BonusNotReadyError(remaining_seconds=120))
    db.get_shop_view = AsyncMock(return_value=_shop_view(2500))
    context = _make_context(db)
    update = _make_update("shop_bonus", session)

    await shop_handler(update, context, session)

    assert "бонус пока недоступен" in update.callback_query.edit_message_text.call_args.kwargs["text"]


@pytest.mark.asyncio
async def test_shop_spin_without_funds_shows_toast() -> None:
    session = MenuSession("session-no-money", 1, 100, None, 1)
    db = AsyncMock()
    db.spin_gacha = AsyncMock(side_effect=InsufficientFundsError("Not enough pokedollar"))
    db.get_shop_view = AsyncMock(return_value=_shop_view(100))
    context = _make_context(db)
    update = _make_update("shop_spin_1", session)

    await shop_handler(update, context, session)

    update.callback_query.answer.assert_awaited_with("💸 Недостаточно PokéDollar для этого действия.", show_alert=False)
    assert "Недостаточно PokéDollar" in update.callback_query.edit_message_text.call_args.kwargs["text"]


@pytest.mark.asyncio
async def test_shop_item_purchase_updates_message() -> None:
    session = MenuSession("session-3", 1, 100, None, 1)
    db = AsyncMock()
    db.purchase_item = AsyncMock(
        return_value=ItemPurchaseResult(
            item_code="ultraball",
            item_name="Ultraball",
            item_price=200,
            quantity_after=2,
            shop_view=_shop_view(2300),
        )
    )
    context = _make_context(db)
    update = _make_update("shop_buy_ultraball", session)

    await shop_handler(update, context, session)

    assert "Куплен" in update.callback_query.edit_message_text.call_args.kwargs["text"]


@pytest.mark.asyncio
async def test_single_spin_sends_reward_card() -> None:
    session = MenuSession("session-4", 1, 100, None, 1)
    db = AsyncMock()
    db.spin_gacha = AsyncMock(
        return_value=SpinResult(
            rewards=[
                PokemonReward(
                    user_pokemon_id=10,
                    pokemon_id=25,
                    name="Pikachu",
                    rarity="Rare",
                    pokemon_type="electric",
                    base_hp=35,
                    base_attack=55,
                    base_defense=40,
                    base_stamina=90,
                    image_credit_id=None,
                )
            ],
            spent_amount=500,
            shop_view=_shop_view(2000),
        )
    )
    context = _make_context(db)
    sent_reward = AsyncMock(spec=Message)
    sent_reward.message_id = 777
    sent_reward.edit_reply_markup = AsyncMock()
    context.application.bot.send_message = AsyncMock(return_value=sent_reward)
    context.application.bot.send_photo = AsyncMock(return_value=sent_reward)
    update = _make_update("shop_spin_1", session)

    await shop_handler(update, context, session)

    assert context.application.bot.send_photo.called or context.application.bot.send_message.called
    assert sent_reward.edit_reply_markup.called
    reward_markup = sent_reward.edit_reply_markup.call_args.kwargs["reply_markup"]
    reward_session_ids = {
        button.callback_data.rsplit(":", maxsplit=1)[-1]
        for row in reward_markup.inline_keyboard
        for button in row
    }
    assert len(reward_session_ids) == 1
    reward_session_id = next(iter(reward_session_ids))
    reward_session = session_store.get_session(reward_session_id)
    assert reward_session is not None
    assert reward_session.message_id == sent_reward.message_id
    assert "🎟 @ash" in update.callback_query.edit_message_text.call_args.kwargs["text"]


@pytest.mark.asyncio
async def test_x5_spin_sends_summary_and_detail_messages() -> None:
    session = MenuSession("session-5", 1, 100, None, 1)
    rewards = [
        PokemonReward(i, i, f"Pokemon{i}", "Common", "normal", 1, 2, 3, 4, None)
        for i in range(1, 6)
    ]
    db = AsyncMock()
    db.spin_gacha = AsyncMock(return_value=SpinResult(rewards=rewards, spent_amount=2500, shop_view=_shop_view(0)))
    context = _make_context(db)
    sent_summary = AsyncMock(spec=Message)
    sent_summary.message_id = 555
    sent_summary.edit_reply_markup = AsyncMock()
    context.application.bot.send_message = AsyncMock(return_value=sent_summary)
    update = _make_update("shop_spin_5", session)

    await shop_handler(update, context, session)

    assert context.application.bot.send_message.called
    assert sent_summary.edit_reply_markup.called
