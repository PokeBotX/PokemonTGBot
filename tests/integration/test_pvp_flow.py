"""Integration tests for PvP challenge request and selection flows."""

from datetime import UTC, datetime, timedelta
from io import BytesIO
from unittest.mock import AsyncMock, Mock

import pytest
from telegram import CallbackQuery, Chat, Message, Update, User
from telegram.ext import ContextTypes

from bot.db.database import PvpRewardResolution
from bot.db.database import CollectionEntry, PvpChallengeParticipant, PvpChallengeSummary
from bot.handlers.commands import fight_command
from bot.handlers.sections import pvp as pvp_module
from bot.handlers.sections.pvp import PVP_ROUTE_ACCEPT, PVP_ROUTE_INFO, PVP_ROUTE_SELECT_FIGHTER_SECTIONS, pvp_handler
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


def _pvp_participant(user_id: int, username: str) -> PvpChallengeParticipant:
    return PvpChallengeParticipant(
        user_id=user_id,
        telegram_id=user_id,
        username=username,
        nickname=None,
        label=f"@{username}",
        selected_pokemon_type="dark",
        selected_base_hp=95,
        selected_base_attack=65,
        selected_base_defense=110,
        selected_base_stamina=130,
    )


def _team_entry(user_pokemon_id: int, name: str, *, form_badge: str | None = None) -> CollectionEntry:
    dex_form_code = "197-0" if form_badge == "Shiny" else "197"
    return CollectionEntry(
        pokemon_id=197,
        sample_user_pokemon_id=user_pokemon_id,
        name=name,
        rarity="Epic",
        pokemon_type="Dark",
        quantity=1,
        base_hp=95,
        base_attack=65,
        base_defense=110,
        base_stamina=130,
        image_credit_id=None,
        is_locked=False,
        dex_form_code=dex_form_code,
        form_badge=form_badge,
    )


def _challenge_summary(*, status: str = "pending", message_id: int | None = 500) -> PvpChallengeSummary:
    return PvpChallengeSummary(
        challenge_id=77,
        chat_id=-1001,
        message_thread_id=None,
        message_id=message_id,
        status=status,
        pending_expires_at=datetime.now(UTC) + timedelta(minutes=2),
        selection_expires_at=(datetime.now(UTC) + timedelta(minutes=8)) if status != "pending" else None,
        created_at=datetime.now(UTC),
        accepted_at=datetime.now(UTC) if status != "pending" else None,
        canceled_at=None,
        completed_at=None,
        cancel_reason=None,
        initiator=_pvp_participant(111, "ash"),
        target=_pvp_participant(222, "misty"),
    )


@pytest.mark.asyncio
async def test_fight_command_creates_request_by_reply() -> None:
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
    message.text = "/fight"

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
    db.create_pvp_challenge = AsyncMock(return_value=_challenge_summary())
    db.attach_pvp_challenge_message = AsyncMock()
    application = Mock()
    application.bot_data = {"db": db}
    context = Mock(spec=ContextTypes.DEFAULT_TYPE)
    context.application = application

    await fight_command(update, context)

    assert db.create_pvp_challenge.called
    assert chat.send_message.called
    assert sent_message.edit_reply_markup.called
    assert db.attach_pvp_challenge_message.called


@pytest.mark.asyncio
async def test_fight_command_rejects_private_chat() -> None:
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
    message.text = "/fight @misty"
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

    await fight_command(update, context)

    sent_text = chat.send_message.call_args.args[0] if chat.send_message.call_args.args else chat.send_message.call_args.kwargs["text"]
    assert "только в чатах" in sent_text


@pytest.mark.asyncio
async def test_pvp_accept_transitions_to_initiator_selection() -> None:
    session = MenuSession(
        session_id="pvp-accept",
        chat_id=-1001,
        message_id=500,
        user_id=222,
        message_thread_id=None,
        data={"challenge_id": 77, "allowed_user_ids": [111]},
    )
    query = AsyncMock(spec=CallbackQuery)
    query.data = f"menu:{PVP_ROUTE_ACCEPT}:pvp-accept"
    query.edit_message_text = AsyncMock()
    query.message = Mock(spec=Message)
    query.message.photo = []

    user = Mock(spec=User)
    user.id = 222
    user.username = "misty"

    update = Mock(spec=Update)
    update.callback_query = query
    update.effective_user = user

    challenge = _challenge_summary(status="selecting_initiator", message_id=500)
    db = AsyncMock()
    db.accept_pvp_challenge = AsyncMock(return_value=challenge)
    db.get_pvp_team_selection_options = AsyncMock(return_value=(_team_entry(7001, "Umbreon"),) * 5)
    application = Mock()
    application.bot_data = {"db": db}
    context = Mock(spec=ContextTypes.DEFAULT_TYPE)
    context.application = application

    await pvp_handler(update, context, session)

    assert db.accept_pvp_challenge.called
    assert db.get_pvp_team_selection_options.called
    text = query.edit_message_text.call_args.kwargs["text"]
    assert "Сейчас выбирает" in text
    assert "@ash" in text
    assert "Доступная команда @ash:" in text
    assert "1. <b>Umbreon</b> | Dark | HP 95 ATK 65 DEF 110 SPD 130" in text
    reply_markup = query.edit_message_text.call_args.kwargs["reply_markup"]
    labels = [button.text for row in reply_markup.inline_keyboard for button in row]
    assert "🧠 Памятка" in labels
    assert "🛑 Отменить" not in labels


@pytest.mark.asyncio
async def test_pvp_target_selection_finishes_preparation_message() -> None:
    session = MenuSession(
        session_id="pvp-select",
        chat_id=-1001,
        message_id=500,
        user_id=222,
        message_thread_id=None,
        data={
            "challenge_id": 77,
            "allowed_user_ids": [111],
            "pvp_team_options": [_team_entry(7002, "Umbreon", form_badge="Shiny").as_session_payload()],
        },
    )
    query = AsyncMock(spec=CallbackQuery)
    query.data = f"menu:{PVP_ROUTE_SELECT_FIGHTER_SECTIONS[0]}:pvp-select"
    query.edit_message_text = AsyncMock()
    query.message = Mock(spec=Message)
    query.message.photo = []

    user = Mock(spec=User)
    user.id = 222
    user.username = "misty"

    update = Mock(spec=Update)
    update.callback_query = query
    update.effective_user = user

    challenge = _challenge_summary(status="battling", message_id=500)
    challenge.initiator.selected_user_pokemon_id = 7001
    challenge.initiator.selected_name = "Eevee"
    challenge.initiator.selected_form_badge = None
    challenge.target.selected_user_pokemon_id = 7002
    challenge.target.selected_name = "Umbreon"
    challenge.target.selected_form_badge = "Shiny"
    completed_challenge = _challenge_summary(status="completed", message_id=500)
    completed_challenge.initiator.selected_user_pokemon_id = 7001
    completed_challenge.initiator.selected_name = "Eevee"
    completed_challenge.target.selected_user_pokemon_id = 7002
    completed_challenge.target.selected_name = "Umbreon"
    completed_challenge.target.selected_form_badge = "Shiny"
    db = AsyncMock()
    db.select_pvp_challenge_fighter = AsyncMock(return_value=(challenge, True))
    db.get_user_pokemon_entry = AsyncMock(
        side_effect=[
            _team_entry(7001, "Eevee"),
            _team_entry(7002, "Umbreon", form_badge="Shiny"),
        ]
    )
    db.settle_pvp_battle_rewards = AsyncMock(
        return_value=PvpRewardResolution(
            winner_reward_granted=True,
            winner_reward_amount=500,
            winner_daily_completed_count=1,
            loser_daily_completed_count=1,
        )
    )
    db.complete_pvp_challenge = AsyncMock(return_value=completed_challenge)
    bot = Mock()
    bot.edit_message_text = AsyncMock()
    application = Mock()
    application.bot_data = {"db": db, "pvp_playback_delay_seconds": 0}
    context = Mock(spec=ContextTypes.DEFAULT_TYPE)
    context.application = application
    context.bot = bot

    await pvp_handler(update, context, session)

    text = bot.edit_message_text.call_args.kwargs["text"]
    assert "Бой завершён" in text
    assert "Umbreon (shiny)" in text


@pytest.mark.asyncio
async def test_pvp_info_button_sends_reference_image() -> None:
    session = MenuSession(
        session_id="pvp-info",
        chat_id=-1001,
        message_id=500,
        user_id=222,
        message_thread_id=None,
        data={"challenge_id": 77, "allowed_user_ids": [111]},
    )
    query = AsyncMock(spec=CallbackQuery)
    query.data = f"menu:{PVP_ROUTE_INFO}:pvp-info"
    query.message = Mock(spec=Message)
    query.message.photo = []
    query.message.chat_id = -1001
    query.message.message_thread_id = None
    query.answer = AsyncMock()

    user = Mock(spec=User)
    user.id = 222
    user.username = "misty"

    update = Mock(spec=Update)
    update.callback_query = query
    update.effective_user = user

    application = Mock()
    application.bot_data = {"db": AsyncMock()}
    context = Mock(spec=ContextTypes.DEFAULT_TYPE)
    context.application = application
    context.bot = AsyncMock()

    await pvp_handler(update, context, session)

    assert context.bot.send_photo.called
    assert query.answer.called


@pytest.mark.asyncio
async def test_pvp_target_selection_sends_photo_battle_message_when_image_render_available(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    session = MenuSession(
        session_id="pvp-select-photo",
        chat_id=-1001,
        message_id=500,
        user_id=222,
        message_thread_id=None,
        data={
            "challenge_id": 77,
            "allowed_user_ids": [111],
            "pvp_team_options": [_team_entry(7002, "Umbreon", form_badge="Shiny").as_session_payload()],
        },
    )
    query = AsyncMock(spec=CallbackQuery)
    query.data = f"menu:{PVP_ROUTE_SELECT_FIGHTER_SECTIONS[0]}:pvp-select-photo"
    query.edit_message_text = AsyncMock()
    query.message = Mock(spec=Message)
    query.message.photo = []
    query.message.delete = AsyncMock()

    user = Mock(spec=User)
    user.id = 222
    user.username = "misty"

    update = Mock(spec=Update)
    update.callback_query = query
    update.effective_user = user

    challenge = _challenge_summary(status="battling", message_id=500)
    challenge.initiator.selected_user_pokemon_id = 7001
    challenge.initiator.selected_name = "Eevee"
    challenge.target.selected_user_pokemon_id = 7002
    challenge.target.selected_name = "Umbreon"
    challenge.target.selected_form_badge = "Shiny"
    completed_challenge = _challenge_summary(status="completed", message_id=901)
    completed_challenge.initiator.selected_user_pokemon_id = 7001
    completed_challenge.initiator.selected_name = "Eevee"
    completed_challenge.target.selected_user_pokemon_id = 7002
    completed_challenge.target.selected_name = "Umbreon"
    completed_challenge.target.selected_form_badge = "Shiny"

    challenger_entry = _team_entry(7001, "Eevee")
    challenger_entry.image_credit_id = 11
    defender_entry = _team_entry(7002, "Umbreon", form_badge="Shiny")
    defender_entry.image_credit_id = 22

    db = AsyncMock()
    db.select_pvp_challenge_fighter = AsyncMock(return_value=(challenge, True))
    db.get_user_pokemon_entry = AsyncMock(side_effect=[challenger_entry, defender_entry])
    db.settle_pvp_battle_rewards = AsyncMock(
        return_value=PvpRewardResolution(
            winner_reward_granted=True,
            winner_reward_amount=500,
            winner_daily_completed_count=1,
            loser_daily_completed_count=1,
        )
    )
    db.complete_pvp_challenge = AsyncMock(return_value=completed_challenge)

    sent_photo_message = Mock(spec=Message)
    sent_photo_message.message_id = 901
    bot = Mock()
    bot.send_photo = AsyncMock(return_value=sent_photo_message)
    bot.edit_message_caption = AsyncMock()
    bot.edit_message_media = AsyncMock()
    bot.edit_message_text = AsyncMock()

    application = Mock()
    application.bot_data = {"db": db, "pvp_playback_delay_seconds": 0}
    context = Mock(spec=ContextTypes.DEFAULT_TYPE)
    context.application = application
    context.bot = bot

    monkeypatch.setattr(pvp_module, "_render_pvp_battle_image", AsyncMock(return_value=b"battle-image"))
    monkeypatch.setattr(pvp_module, "_fetch_pvp_snapshot_image", AsyncMock(return_value=BytesIO(b"winner-image")))

    await pvp_handler(update, context, session)

    assert bot.send_photo.called
    assert bot.edit_message_caption.called
    assert bot.edit_message_media.called
    assert query.message.delete.called


@pytest.mark.asyncio
async def test_pvp_runtime_failure_aborts_battle_and_unblocks_users() -> None:
    session = MenuSession(
        session_id="pvp-select-fail",
        chat_id=-1001,
        message_id=500,
        user_id=222,
        message_thread_id=None,
        data={
            "challenge_id": 77,
            "allowed_user_ids": [111],
            "pvp_team_options": [_team_entry(7002, "Umbreon", form_badge="Shiny").as_session_payload()],
        },
    )
    query = AsyncMock(spec=CallbackQuery)
    query.data = f"menu:{PVP_ROUTE_SELECT_FIGHTER_SECTIONS[0]}:pvp-select-fail"
    query.edit_message_text = AsyncMock()
    query.message = Mock(spec=Message)
    query.message.photo = []

    user = Mock(spec=User)
    user.id = 222
    user.username = "misty"

    update = Mock(spec=Update)
    update.callback_query = query
    update.effective_user = user

    challenge = _challenge_summary(status="battling", message_id=500)
    challenge.initiator.selected_user_pokemon_id = 7001
    challenge.initiator.selected_name = "Eevee"
    challenge.target.selected_user_pokemon_id = 7002
    challenge.target.selected_name = "Umbreon"
    challenge.target.selected_form_badge = "Shiny"
    canceled_challenge = _challenge_summary(status="canceled", message_id=500)

    db = AsyncMock()
    db.select_pvp_challenge_fighter = AsyncMock(return_value=(challenge, True))
    db.get_user_pokemon_entry = AsyncMock(
        side_effect=[
            _team_entry(7001, "Eevee"),
            _team_entry(7002, "Umbreon", form_badge="Shiny"),
        ]
    )
    db.settle_pvp_battle_rewards = AsyncMock(return_value=PvpRewardResolution(True, 500, 1, 1))
    db.complete_pvp_challenge = AsyncMock(side_effect=RuntimeError("boom"))
    db.abort_pvp_challenge = AsyncMock(return_value=canceled_challenge)
    bot = Mock()
    bot.edit_message_text = AsyncMock()
    application = Mock()
    application.bot_data = {"db": db, "pvp_playback_delay_seconds": 0}
    context = Mock(spec=ContextTypes.DEFAULT_TYPE)
    context.application = application
    context.bot = bot

    await pvp_handler(update, context, session)

    db.abort_pvp_challenge.assert_awaited_once_with(77, cancel_reason="battle_runtime_error")
    final_text = bot.edit_message_text.call_args.kwargs["text"]
    assert "Бой прерван из-за ошибки" in final_text
