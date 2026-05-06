"""PvP challenge handlers and shared battle-team selection flow."""

from __future__ import annotations

import asyncio
import random
import subprocess
from dataclasses import dataclass
from datetime import UTC, datetime
from io import BytesIO
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Optional

import structlog
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, InputMediaPhoto, Message, Update
from telegram.error import BadRequest, TelegramError
from telegram.ext import ContextTypes

from bot.db.database import (
    CollectionEntry,
    Database,
    PvpChallengeSummary,
    PvpChallengeMaintenanceResult,
    PvpRewardResolution,
    PVP_CHALLENGE_STATUS_SELECTING_INITIATOR,
    PVP_WIN_REWARD_POKEDOLLAR,
    ShopError,
)
from bot.navigation.context import extract_context
from bot.navigation.router import NavigationRouter
from bot.navigation.session import MenuSession, session_store
from bot.ui.html import escape_html
from bot.ui.pokemon_cards import _fetch_image_bytes_from_storage
from bot.ui.pokemon_cards import format_pokemon_display_name

logger = structlog.get_logger()

TYPE_EFFECTIVE_AGAINST: dict[str, set[str]] = {
    "poison": {"fairy"},
    "steel": {"fairy", "ice", "rock"},
    "fire": {"steel", "ice", "grass"},
    "fight": {"steel", "dark", "rock", "ice", "normal"},
    "ground": {"steel", "rock", "poison", "electr", "fire"},
    "bug": {"dark", "psychic", "grass"},
    "fairy": {"dark", "dragon", "fight"},
    "ice": {"dragon", "ground", "grass", "flying"},
    "dragon": {"dragon"},
    "ghost": {"ghost", "psychic"},
    "water": {"rock", "ground", "fire"},
    "grass": {"rock", "water", "ground"},
    "electr": {"flying", "water"},
    "flying": {"fight", "bug", "grass"},
    "psychic": {"poison", "fight"},
    "rock": {"flying", "bug", "fire", "ice"},
}

ROLL_BAND_MISS_MAX = -1
ROLL_BAND_WEAK_MAX = 5
ROLL_BAND_NORMAL_MAX = 11
ROLL_BAND_EFFECTIVE_MAX = 17


@dataclass(slots=True)
class PvpBattleSnapshot:
    """Temporary combat snapshot for one selected fighter."""

    user_pokemon_id: int
    pokemon_id: int
    image_credit_id: Optional[int]
    name: str
    form_badge: Optional[str]
    pokemon_types: tuple[str, ...]
    max_hp: int
    current_hp: int
    attack: int
    defense: int
    speed: int

    @property
    def display_name(self) -> str:
        return format_pokemon_display_name(self.name, self.form_badge)


@dataclass(slots=True)
class PvpTurnOutcome:
    """One resolved attack turn inside PvP battle playback."""

    attacker_name: str
    defender_name: str
    roll: int
    final_roll: int
    result_label: str
    damage: int
    defender_hp_after: int
    log_line: str


@dataclass(slots=True)
class PvpBattleResult:
    """Resolved PvP battle outcome."""

    challenger: PvpBattleSnapshot
    defender: PvpBattleSnapshot
    turns: list[PvpTurnOutcome]
    winner_side: str


@dataclass(slots=True)
class PvpBattleMessageTarget:
    """Where ongoing PvP playback should be rendered."""

    chat_id: int
    message_id: int
    message_thread_id: Optional[int]
    is_photo: bool

PVP_ROUTE_ACCEPT = "pfa"
PVP_ROUTE_REJECT = "pfr"
PVP_ROUTE_CANCEL = "pfc"
PVP_ROUTE_INFO = "pfi"
PVP_ROUTE_SELECT_FIGHTER_SECTIONS = [f"pfs{index}" for index in range(1, 6)]
PVP_ROUTE_SECTIONS = [
    PVP_ROUTE_ACCEPT,
    PVP_ROUTE_REJECT,
    PVP_ROUTE_CANCEL,
    PVP_ROUTE_INFO,
    *PVP_ROUTE_SELECT_FIGHTER_SECTIONS,
]
PVP_INFO_IMAGE_PATH = Path(__file__).resolve().parents[3] / "pokeinfo.png"


def register_pvp_routes(router: NavigationRouter) -> None:
    """Register all PvP callback sections."""
    for section in PVP_ROUTE_SECTIONS:
        router.register(section, pvp_handler)


async def pvp_handler(update: Update, context: ContextTypes.DEFAULT_TYPE, session: MenuSession) -> None:
    """Route PvP callback actions."""
    query = update.callback_query
    section = _callback_section(query.data or "")
    db = _get_db(context)
    if not db or not query or not update.effective_user:
        return

    try:
        if section == PVP_ROUTE_ACCEPT:
            challenge_id = _require_challenge_id(session)
            challenge = await db.accept_pvp_challenge(challenge_id, update.effective_user.id)
            options = await db.get_pvp_team_selection_options(challenge.initiator.telegram_id, challenge.initiator.username)
            next_session_id = await _create_pvp_session(
                challenge,
                user_id=challenge.initiator.telegram_id,
                allowed_user_ids=[challenge.target.telegram_id],
                options=options,
            )
            await _edit_pvp_message(
                query,
                _render_selection_text(challenge, options),
                _build_fighter_selection_keyboard(next_session_id, options),
            )
            logger.info("pvp_challenge_accepted_from_ui", challenge_id=challenge.challenge_id, actor_id=update.effective_user.id)
            return

        if section == PVP_ROUTE_REJECT:
            challenge_id = _require_challenge_id(session)
            challenge = await db.cancel_pvp_challenge(challenge_id, update.effective_user.id, cancel_reason="rejected")
            await _edit_pvp_message(query, _render_closed_text(challenge, "❌ Вызов на бой отклонён."), None)
            logger.info("pvp_challenge_rejected_from_ui", challenge_id=challenge.challenge_id, actor_id=update.effective_user.id)
            return

        if section == PVP_ROUTE_CANCEL:
            challenge_id = _require_challenge_id(session)
            challenge = await db.cancel_pvp_challenge(challenge_id, update.effective_user.id, cancel_reason="canceled")
            await _edit_pvp_message(query, _render_closed_text(challenge, "🛑 Бой отменён."), None)
            logger.info("pvp_challenge_canceled_from_ui", challenge_id=challenge.challenge_id, actor_id=update.effective_user.id)
            return

        if section == PVP_ROUTE_INFO:
            await _send_pvp_info_image(query, context)
            return

        if section in PVP_ROUTE_SELECT_FIGHTER_SECTIONS:
            challenge_id = _require_challenge_id(session)
            selection_payloads = session.data.get("pvp_team_options")
            if not isinstance(selection_payloads, list):
                raise ShopError("Меню выбора бойца устарело.")
            option_index = int(section.removeprefix("pfs")) - 1
            if option_index < 0 or option_index >= len(selection_payloads):
                raise ShopError("Этого бойца больше нельзя выбрать.")
            selected_entry = CollectionEntry.from_payload(selection_payloads[option_index])
            challenge, battle_ready = await db.select_pvp_challenge_fighter(
                challenge_id=challenge_id,
                telegram_id=update.effective_user.id,
                username=update.effective_user.username,
                user_pokemon_id=selected_entry.sample_user_pokemon_id,
            )
            if battle_ready:
                battle_message: Optional[PvpBattleMessageTarget] = None
                try:
                    if challenge.initiator.selected_user_pokemon_id is None or challenge.target.selected_user_pokemon_id is None:
                        raise ShopError("Бойцы ещё не выбраны полностью.")
                    challenger_entry = await db.get_user_pokemon_entry(challenge.initiator.selected_user_pokemon_id)
                    defender_entry = await db.get_user_pokemon_entry(challenge.target.selected_user_pokemon_id)
                    if challenger_entry is None or defender_entry is None:
                        raise ShopError("Один из выбранных бойцов больше недоступен.")
                    battle = _run_pvp_battle(
                        challenger=_build_battle_snapshot(challenger_entry),
                        defender=_build_battle_snapshot(defender_entry),
                    )
                    battle_message = await _send_battle_message(
                        context,
                        query,
                        challenge,
                        battle,
                    )
                    await _play_pvp_battle(
                        context,
                        battle_message,
                        challenge,
                        battle,
                        delay_seconds=_playback_delay_seconds(context),
                    )
                    reward_resolution = await db.settle_pvp_battle_rewards(
                        winner_telegram_id=challenge.initiator.telegram_id if battle.winner_side == "challenger" else challenge.target.telegram_id,
                        winner_username=challenge.initiator.username if battle.winner_side == "challenger" else challenge.target.username,
                        loser_telegram_id=challenge.target.telegram_id if battle.winner_side == "challenger" else challenge.initiator.telegram_id,
                        loser_username=challenge.target.username if battle.winner_side == "challenger" else challenge.initiator.username,
                    )
                    challenge = await db.complete_pvp_challenge(challenge.challenge_id)
                    await _finalize_battle_message(
                        context,
                        battle_message,
                        battle,
                        _render_completed_text(challenge, battle, reward_resolution),
                    )
                    logger.info("pvp_challenge_completed", challenge_id=challenge.challenge_id, winner_side=battle.winner_side)
                except ShopError:
                    raise
                except Exception:
                    logger.exception(
                        "pvp_battle_runtime_failed",
                        challenge_id=challenge.challenge_id,
                        initiator_telegram_id=challenge.initiator.telegram_id,
                        target_telegram_id=challenge.target.telegram_id,
                    )
                    closed_challenge = await db.abort_pvp_challenge(
                        challenge.challenge_id,
                        cancel_reason="battle_runtime_error",
                    )
                    failure_text = _render_closed_text(
                        closed_challenge,
                        "⚠️ Бой прерван из-за ошибки. Попробуйте начать заново.",
                    )
                    if battle_message is not None:
                        await _edit_battle_message(context, battle_message, failure_text)
                    else:
                        await _edit_pvp_message(query, failure_text, None)
                return
            options = await db.get_pvp_team_selection_options(challenge.target.telegram_id, challenge.target.username)
            next_session_id = await _create_pvp_session(
                challenge,
                user_id=challenge.target.telegram_id,
                allowed_user_ids=[challenge.initiator.telegram_id],
                options=options,
            )
            await _edit_pvp_message(
                query,
                _render_selection_text(challenge, options),
                _build_fighter_selection_keyboard(next_session_id, options),
            )
            logger.info("pvp_challenge_selection_progressed", challenge_id=challenge.challenge_id, actor_id=update.effective_user.id)
            return
    except ShopError as exc:
        logger.warning(
            "pvp_handler_error",
            error="pvp_rule",
            error_message=str(exc),
            user_id=update.effective_user.id,
            section=section,
        )
        await query.answer(str(exc), show_alert=False)
        return
    except Exception as exc:
        logger.exception(
            "pvp_handler_error",
            error="unexpected",
            error_message=str(exc),
            user_id=update.effective_user.id,
            section=section,
        )
        await query.answer("Экран PvP устарел. Откройте бой заново.", show_alert=False)


async def start_pvp_challenge(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    *,
    target_telegram_id: int,
    target_username: Optional[str],
) -> Message:
    """Create and send a pending PvP challenge."""
    db = _get_db(context)
    if not db or not update.effective_user or not update.effective_chat:
        raise ShopError("PvP временно недоступен.")
    msg_context = extract_context(update)
    challenge = await db.create_pvp_challenge(
        initiator_telegram_id=update.effective_user.id,
        initiator_username=update.effective_user.username,
        target_telegram_id=target_telegram_id,
        target_username=target_username,
        chat_id=msg_context.chat_id,
        message_thread_id=msg_context.message_thread_id,
    )
    request_session_id = await _create_pvp_session(
        challenge,
        user_id=challenge.target.telegram_id,
        allowed_user_ids=[challenge.initiator.telegram_id],
        options=(),
        message_id=0,
    )
    sent_message = await update.effective_chat.send_message(
        text=_render_pending_text(challenge),
        parse_mode="HTML",
        reply_markup=_build_pending_keyboard(request_session_id),
        message_thread_id=msg_context.message_thread_id,
    )
    await session_store.delete_session_async(request_session_id)
    final_session_id = await _create_pvp_session(
        challenge,
        user_id=challenge.target.telegram_id,
        allowed_user_ids=[challenge.initiator.telegram_id],
        options=(),
        message_id=sent_message.message_id,
    )
    await sent_message.edit_reply_markup(reply_markup=_build_pending_keyboard(final_session_id))
    await db.attach_pvp_challenge_message(challenge.challenge_id, sent_message.message_id)
    logger.info(
        "pvp_challenge_message_sent",
        challenge_id=challenge.challenge_id,
        message_id=sent_message.message_id,
        initiator_id=challenge.initiator.telegram_id,
        target_id=challenge.target.telegram_id,
    )
    return sent_message


async def run_pvp_maintenance_job(context) -> None:
    """Expire stale PvP challenges and reflect that in Telegram."""
    application = getattr(context, "application", None)
    bot_data = getattr(application, "bot_data", {}) if application else {}
    db = bot_data.get("db") if isinstance(bot_data, dict) else None
    if not db:
        return
    result = await db.process_pvp_challenge_maintenance()
    await _reflect_pvp_maintenance(context, result)


def _render_pending_text(challenge: PvpChallengeSummary) -> str:
    seconds_left = _seconds_remaining(challenge.pending_expires_at)
    return "\n".join(
        [
            "⚔️ <b>Вызов на бой</b>",
            "",
            f"{escape_html(challenge.initiator.label)} вызывает {escape_html(challenge.target.label)} на PvP.",
            f"Срок ответа: <b>{seconds_left} сек.</b>",
            "",
            "После принятия первый выбирает бойца вызывающий игрок.",
        ]
    )


def _render_selection_text(challenge: PvpChallengeSummary, options: tuple[CollectionEntry, ...]) -> str:
    seconds_left = _seconds_remaining(challenge.selection_expires_at)
    chooser = challenge.initiator if challenge.status == PVP_CHALLENGE_STATUS_SELECTING_INITIATOR else challenge.target
    opponent = challenge.target if challenge.status == PVP_CHALLENGE_STATUS_SELECTING_INITIATOR else challenge.initiator
    lines = [
        "⚔️ <b>Подготовка к бою</b>",
        "",
        f"Сейчас выбирает: <b>{escape_html(chooser.label)}</b>",
        f"Осталось времени: <b>{seconds_left} сек.</b>",
        "",
        f"Доступная команда {escape_html(chooser.label)}:",
        *[_render_team_option_line(index, option) for index, option in enumerate(options, start=1)],
    ]
    opponent_pick = _render_selected_fighter(opponent)
    if opponent.selected_name:
        lines.extend(
            [
                "",
                f"Уже выбрал {escape_html(opponent.label)}: {opponent_pick}",
                _render_selected_fighter_details(opponent),
            ]
        )
    return "\n".join(lines)


def _render_ready_text(challenge: PvpChallengeSummary) -> str:
    return "\n".join(
        [
            "⚔️ <b>Бой собран</b>",
            "",
            f"{escape_html(challenge.initiator.label)}: {_render_selected_fighter(challenge.initiator)}",
            f"{escape_html(challenge.target.label)}: {_render_selected_fighter(challenge.target)}",
            "",
            "Автобой и награды подключим следующим срезом. Сейчас pipeline вызова и выбора бойца уже готов.",
        ]
    )


def _render_battle_text(
    challenge: PvpChallengeSummary,
    battle: PvpBattleResult,
    log_lines: list[str],
    *,
    challenger_hp: int,
    defender_hp: int,
) -> str:
    challenger_name = escape_html(battle.challenger.display_name)
    defender_name = escape_html(battle.defender.display_name)
    rendered_logs = _render_battle_log_lines(log_lines)
    return "\n".join(
        [
            "⚔️ <b>PvP-бой</b>",
            "",
            f"{escape_html(challenge.initiator.label)}: <b>{challenger_name}</b> | HP <b>{challenger_hp}/{battle.challenger.max_hp}</b>",
            f"{escape_html(challenge.target.label)}: <b>{defender_name}</b> | HP <b>{defender_hp}/{battle.defender.max_hp}</b>",
            "",
            "<b>Лог боя:</b>",
            *(rendered_logs or ["<i>Бой начинается...</i>"]),
        ]
    )


def _render_completed_text(
    challenge: PvpChallengeSummary,
    battle: PvpBattleResult,
    reward_resolution: PvpRewardResolution,
) -> str:
    winner_label = challenge.initiator.label if battle.winner_side == "challenger" else challenge.target.label
    reward_line = (
        f"🏆 Победитель получил <b>{PVP_WIN_REWARD_POKEDOLLAR}</b> PokéDollar."
        if reward_resolution.winner_reward_granted
        else "🏁 Дневной PvP-лимит исчерпан, награда не выдана."
    )
    final_log_lines = _render_battle_log_lines([escape_html(turn.log_line) for turn in battle.turns[-5:]])
    return "\n".join(
        [
            "⚔️ <b>Бой завершён</b>",
            "",
            f"Победитель: <b>{escape_html(winner_label)}</b>",
            reward_line,
            "",
            f"{escape_html(challenge.initiator.label)}: <b>{escape_html(battle.challenger.display_name)}</b> | HP <b>{battle.challenger.current_hp}/{battle.challenger.max_hp}</b>",
            f"{escape_html(challenge.target.label)}: <b>{escape_html(battle.defender.display_name)}</b> | HP <b>{battle.defender.current_hp}/{battle.defender.max_hp}</b>",
            "",
            "<b>Последние ходы:</b>",
            *final_log_lines,
        ]
    )


def _render_closed_text(challenge: PvpChallengeSummary, title: str) -> str:
    return "\n".join(
        [
            title,
            "",
            f"{escape_html(challenge.initiator.label)} ↔ {escape_html(challenge.target.label)}",
        ]
    )


def _render_selected_fighter(participant) -> str:
    if not participant.selected_name:
        return "<i>ещё не выбрано</i>"
    return f"<b>{escape_html(format_pokemon_display_name(participant.selected_name, participant.selected_form_badge))}</b>"


def _render_selected_fighter_details(participant) -> str:
    if not participant.selected_name:
        return ""
    return (
        f"{escape_html(_format_pvp_type_line(participant.selected_pokemon_type))} | "
        f"HP {participant.selected_base_hp or 0} "
        f"ATK {participant.selected_base_attack or 0} "
        f"DEF {participant.selected_base_defense or 0} "
        f"SPD {participant.selected_base_stamina or 0}"
    )


def _render_team_option_line(index: int, entry: CollectionEntry) -> str:
    return (
        f"{index}. <b>{escape_html(format_pokemon_display_name(entry.name, entry.form_badge))}</b> | "
        f"{escape_html(_format_pvp_type_line(entry.pokemon_type))} | "
        f"HP {entry.base_hp} ATK {entry.base_attack} DEF {entry.base_defense} SPD {entry.base_stamina}"
    )


def _render_battle_log_lines(log_lines: list[str]) -> list[str]:
    rendered: list[str] = []
    for index, line in enumerate(log_lines):
        rendered.append(f"• {line}")
        if index < len(log_lines) - 1:
            rendered.append("")
    return rendered


def _format_pvp_type_line(pokemon_type: Optional[str]) -> str:
    if not pokemon_type:
        return "unknown"
    parts = [
        type_part.strip().title()
        for type_part in pokemon_type.replace("/", ",").split(",")
        if type_part.strip()
    ]
    return " / ".join(parts) or "unknown"


def _build_pending_keyboard(session_id: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("✅ Принять", callback_data=f"menu:{PVP_ROUTE_ACCEPT}:{session_id}"),
                InlineKeyboardButton("❌ Отклонить", callback_data=f"menu:{PVP_ROUTE_REJECT}:{session_id}"),
            ],
        ]
    )


def _build_fighter_selection_keyboard(session_id: str, options: tuple[CollectionEntry, ...]) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []
    for index, option in enumerate(options, start=1):
        rows.append(
            [
                InlineKeyboardButton(
                    f"{index}. {format_pokemon_display_name(option.name, option.form_badge)}",
                    callback_data=f"menu:pfs{index}:{session_id}",
                )
            ]
        )
    rows.append([InlineKeyboardButton("🧠 Памятка", callback_data=f"menu:{PVP_ROUTE_INFO}:{session_id}")])
    return InlineKeyboardMarkup(rows)


async def _send_pvp_info_image(query, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not PVP_INFO_IMAGE_PATH.exists():
        await query.answer("Памятка пока недоступна.", show_alert=False)
        return
    with PVP_INFO_IMAGE_PATH.open("rb") as image_file:
        await context.bot.send_photo(
            chat_id=query.message.chat_id,
            photo=image_file,
            message_thread_id=getattr(query.message, "message_thread_id", None),
        )
    await query.answer("Памятка отправлена.", show_alert=False)


async def _reflect_pvp_maintenance(context: ContextTypes.DEFAULT_TYPE, result: PvpChallengeMaintenanceResult) -> None:
    for challenge in result.expired_pending_challenges:
        if challenge.message_id is None:
            continue
        await _edit_pvp_message_by_ids(
            context,
            challenge.chat_id,
            challenge.message_id,
            _render_closed_text(challenge, "⌛ Вызов на бой истёк."),
            challenge.message_thread_id,
        )
    for challenge in result.expired_selecting_challenges:
        if challenge.message_id is None:
            continue
        await _edit_pvp_message_by_ids(
            context,
            challenge.chat_id,
            challenge.message_id,
            _render_closed_text(challenge, "⌛ Время на выбор бойца истекло."),
            challenge.message_thread_id,
        )
    for challenge in result.expired_battling_challenges:
        if challenge.message_id is None:
            continue
        await _edit_pvp_message_by_ids(
            context,
            challenge.chat_id,
            challenge.message_id,
            _render_closed_text(challenge, "⌛ Бой истёк и был завершён автоматически."),
            challenge.message_thread_id,
        )


async def _create_pvp_session(
    challenge: PvpChallengeSummary,
    *,
    user_id: int,
    allowed_user_ids: list[int],
    options: tuple[CollectionEntry, ...],
    message_id: Optional[int] = None,
) -> str:
    return await session_store.create_session_async(
        chat_id=challenge.chat_id,
        message_id=message_id or challenge.message_id or 0,
        user_id=user_id,
        message_thread_id=challenge.message_thread_id,
        data={
            "challenge_id": challenge.challenge_id,
            "allowed_user_ids": allowed_user_ids,
            "pvp_team_options": [entry.as_session_payload() for entry in options],
        },
    )


async def _edit_pvp_message(query, text: str, reply_markup: Optional[InlineKeyboardMarkup]) -> None:
    if query.message and getattr(query.message, "photo", None):
        await query.edit_message_caption(caption=text, parse_mode="HTML", reply_markup=reply_markup)
    else:
        await query.edit_message_text(text=text, parse_mode="HTML", reply_markup=reply_markup)


async def _edit_pvp_message_by_ids(
    context: ContextTypes.DEFAULT_TYPE,
    chat_id: int,
    message_id: int,
    text: str,
    message_thread_id: Optional[int],
) -> None:
    bot = getattr(context, "bot", None)
    if bot is None:
        return
    try:
        await bot.edit_message_text(
            chat_id=chat_id,
            message_id=message_id,
            text=text,
            parse_mode="HTML",
        )
    except BadRequest:
        try:
            await bot.edit_message_caption(
                chat_id=chat_id,
                message_id=message_id,
                caption=text,
                parse_mode="HTML",
            )
        except TelegramError as exc:
            logger.warning("pvp_message_edit_failed", chat_id=chat_id, message_id=message_id, error=str(exc))
    except TelegramError as exc:
        logger.warning("pvp_message_edit_failed", chat_id=chat_id, message_id=message_id, error=str(exc))


async def _play_pvp_battle(
    context: ContextTypes.DEFAULT_TYPE,
    target: PvpBattleMessageTarget,
    challenge: PvpChallengeSummary,
    battle: PvpBattleResult,
    *,
    delay_seconds: float,
) -> None:
    visible_logs: list[str] = []
    challenger_hp = battle.challenger.max_hp
    defender_hp = battle.defender.max_hp
    await _edit_battle_message(
        context,
        target,
        _render_battle_text(
            challenge,
            battle,
            visible_logs,
            challenger_hp=challenger_hp,
            defender_hp=defender_hp,
        ),
    )
    if delay_seconds > 0:
        await asyncio.sleep(delay_seconds)
    for turn in battle.turns:
        visible_logs.append(escape_html(turn.log_line))
        visible_logs = visible_logs[-5:]
        if turn.attacker_name == battle.challenger.display_name:
            defender_hp = turn.defender_hp_after
        else:
            challenger_hp = turn.defender_hp_after
        await _edit_battle_message(
            context,
            target,
            _render_battle_text(
                challenge,
                battle,
                visible_logs,
                challenger_hp=challenger_hp,
                defender_hp=defender_hp,
            ),
        )
        if delay_seconds > 0:
            await asyncio.sleep(delay_seconds)


async def _send_battle_message(
    context: ContextTypes.DEFAULT_TYPE,
    query,
    challenge: PvpChallengeSummary,
    battle: PvpBattleResult,
) -> PvpBattleMessageTarget:
    initial_text = _render_battle_text(
        challenge,
        battle,
        [],
        challenger_hp=battle.challenger.max_hp,
        defender_hp=battle.defender.max_hp,
    )
    rendered_image = await _render_pvp_battle_image(context, battle.challenger, battle.defender)
    if rendered_image is None:
        await _edit_pvp_message(query, initial_text, None)
        message = getattr(query, "message", None)
        return PvpBattleMessageTarget(
            chat_id=challenge.chat_id,
            message_id=message.message_id if message is not None else challenge.message_id or 0,
            message_thread_id=challenge.message_thread_id,
            is_photo=bool(getattr(message, "photo", None)),
        )

    file_obj = BytesIO(rendered_image)
    file_obj.name = "pvp-battle.jpg"
    sent_message = await context.bot.send_photo(
        chat_id=challenge.chat_id,
        message_thread_id=challenge.message_thread_id,
        photo=file_obj,
        caption=initial_text,
        parse_mode="HTML",
    )
    try:
        if getattr(query, "message", None) is not None:
            await query.message.delete()
    except TelegramError:
        logger.warning(
            "pvp_battle_message_delete_failed",
            challenge_id=challenge.challenge_id,
            message_id=getattr(getattr(query, "message", None), "message_id", None),
        )
    return PvpBattleMessageTarget(
        chat_id=challenge.chat_id,
        message_id=sent_message.message_id,
        message_thread_id=challenge.message_thread_id,
        is_photo=True,
    )


async def _edit_battle_message(
    context: ContextTypes.DEFAULT_TYPE,
    target: PvpBattleMessageTarget,
    text: str,
) -> None:
    bot = getattr(context, "bot", None)
    if bot is None:
        return
    try:
        if target.is_photo:
            await bot.edit_message_caption(
                chat_id=target.chat_id,
                message_id=target.message_id,
                caption=text,
                parse_mode="HTML",
            )
        else:
            await bot.edit_message_text(
                chat_id=target.chat_id,
                message_id=target.message_id,
                text=text,
                parse_mode="HTML",
            )
    except TelegramError as exc:
        logger.warning(
            "pvp_battle_message_edit_failed",
            chat_id=target.chat_id,
            message_id=target.message_id,
            error=str(exc),
        )

async def _render_pvp_battle_image(
    context: ContextTypes.DEFAULT_TYPE,
    challenger: PvpBattleSnapshot,
    defender: PvpBattleSnapshot,
) -> Optional[bytes]:
    if challenger.image_credit_id is None or defender.image_credit_id is None:
        return None
    challenger_image = await _fetch_image_bytes_from_storage(context, challenger.image_credit_id)
    defender_image = await _fetch_image_bytes_from_storage(context, defender.image_credit_id)
    if challenger_image is None or defender_image is None:
        return None
    return await asyncio.to_thread(
        _compose_battle_image_bytes,
        challenger_image[0],
        Path(challenger_image[1]).suffix or ".jpg",
        defender_image[0],
        Path(defender_image[1]).suffix or ".jpg",
    )


def _compose_battle_image_bytes(
    challenger_bytes: bytes,
    challenger_suffix: str,
    defender_bytes: bytes,
    defender_suffix: str,
) -> Optional[bytes]:
    with TemporaryDirectory(prefix="pokemonbot-pvp-") as temp_dir:
        temp_path = Path(temp_dir)
        challenger_path = temp_path / f"challenger{challenger_suffix}"
        defender_path = temp_path / f"defender{defender_suffix}"
        output_path = temp_path / "battle.jpg"
        challenger_path.write_bytes(challenger_bytes)
        defender_path.write_bytes(defender_bytes)
        command = [
            "ffmpeg",
            "-hide_banner",
            "-loglevel",
            "error",
            "-y",
            "-i",
            str(challenger_path),
            "-i",
            str(defender_path),
            "-filter_complex",
            (
                "[0:v]scale=512:512:force_original_aspect_ratio=decrease,"
                "pad=512:512:(ow-iw)/2:(oh-ih)/2:color=0x0f172a[left];"
                "[1:v]scale=512:512:force_original_aspect_ratio=decrease,"
                "pad=512:512:(ow-iw)/2:(oh-ih)/2:color=0x0f172a[right];"
                "[left][right]hstack=inputs=2[out]"
            ),
            "-map",
            "[out]",
            "-frames:v",
            "1",
            str(output_path),
        ]
        result = subprocess.run(command, check=False, capture_output=True)
        if result.returncode != 0 or not output_path.exists():
            return None
        return output_path.read_bytes()


async def _fetch_pvp_snapshot_image(
    context: ContextTypes.DEFAULT_TYPE,
    snapshot: PvpBattleSnapshot,
) -> Optional[BytesIO]:
    if snapshot.image_credit_id is None:
        return None
    image = await _fetch_image_bytes_from_storage(context, snapshot.image_credit_id)
    if image is None:
        return None
    file_obj = BytesIO(image[0])
    file_obj.name = Path(image[1]).name or "pokemon.jpg"
    return file_obj


async def _finalize_battle_message(
    context: ContextTypes.DEFAULT_TYPE,
    target: PvpBattleMessageTarget,
    battle: PvpBattleResult,
    text: str,
) -> None:
    if not target.is_photo:
        await _edit_battle_message(context, target, text)
        return
    bot = getattr(context, "bot", None)
    if bot is None:
        return
    winner_snapshot = battle.challenger if battle.winner_side == "challenger" else battle.defender
    winner_image = await _fetch_pvp_snapshot_image(context, winner_snapshot)
    if winner_image is None:
        await _edit_battle_message(context, target, text)
        return
    try:
        await bot.edit_message_media(
            chat_id=target.chat_id,
            message_id=target.message_id,
            media=InputMediaPhoto(media=winner_image, caption=text, parse_mode="HTML"),
        )
    except TelegramError as exc:
        logger.warning(
            "pvp_battle_winner_media_edit_failed",
            chat_id=target.chat_id,
            message_id=target.message_id,
            error=str(exc),
        )
        await _edit_battle_message(context, target, text)


def _playback_delay_seconds(context: ContextTypes.DEFAULT_TYPE) -> float:
    application = getattr(context, "application", None)
    bot_data = getattr(application, "bot_data", None)
    if isinstance(bot_data, dict):
        raw_value = bot_data.get("pvp_playback_delay_seconds")
        if isinstance(raw_value, (int, float)):
            return max(0.0, float(raw_value))
    return 1.5


def _build_battle_snapshot(entry: CollectionEntry) -> PvpBattleSnapshot:
    pokemon_types = tuple(
        normalized
        for normalized in (
            type_part.strip().lower()
            for type_part in (entry.pokemon_type or "").replace("/", ",").split(",")
        )
        if normalized
    )
    max_hp = max(1, int(entry.base_hp))
    return PvpBattleSnapshot(
        user_pokemon_id=entry.sample_user_pokemon_id,
        pokemon_id=entry.pokemon_id,
        image_credit_id=entry.image_credit_id,
        name=entry.name,
        form_badge=entry.form_badge,
        pokemon_types=pokemon_types,
        max_hp=max_hp,
        current_hp=max_hp,
        attack=max(1, int(entry.base_attack)),
        defense=max(1, int(entry.base_defense)),
        speed=max(1, int(entry.base_stamina)),
    )


def _run_pvp_battle(*, challenger: PvpBattleSnapshot, defender: PvpBattleSnapshot) -> PvpBattleResult:
    challenger_state = _clone_battle_snapshot(challenger)
    defender_state = _clone_battle_snapshot(defender)
    turns: list[PvpTurnOutcome] = []
    attacker_side = "defender"

    while challenger_state.current_hp > 0 and defender_state.current_hp > 0:
        attacker = defender_state if attacker_side == "defender" else challenger_state
        attacked = challenger_state if attacker_side == "defender" else defender_state
        turn = _resolve_attack_turn(attacker, attacked)
        turns.append(turn)
        if attacked.current_hp <= 0:
            break
        attacker_side = "challenger" if attacker_side == "defender" else "defender"

    winner_side = "challenger" if challenger_state.current_hp > 0 else "defender"
    return PvpBattleResult(
        challenger=challenger_state,
        defender=defender_state,
        turns=turns,
        winner_side=winner_side,
    )


def _clone_battle_snapshot(snapshot: PvpBattleSnapshot) -> PvpBattleSnapshot:
    return PvpBattleSnapshot(
        user_pokemon_id=snapshot.user_pokemon_id,
        pokemon_id=snapshot.pokemon_id,
        image_credit_id=snapshot.image_credit_id,
        name=snapshot.name,
        form_badge=snapshot.form_badge,
        pokemon_types=tuple(snapshot.pokemon_types),
        max_hp=snapshot.max_hp,
        current_hp=snapshot.current_hp,
        attack=snapshot.attack,
        defense=snapshot.defense,
        speed=snapshot.speed,
    )


def _resolve_attack_turn(attacker: PvpBattleSnapshot, defender: PvpBattleSnapshot) -> PvpTurnOutcome:
    base_roll = random.randint(1, 20)
    final_roll = base_roll + _type_roll_modifier(attacker.pokemon_types, defender.pokemon_types) + _stat_triangle_modifier(attacker, defender)
    result_label = _roll_result_label(final_roll)
    damage = _damage_from_roll(attacker, defender, final_roll)
    defender.current_hp = max(0, defender.current_hp - damage)
    log_line = _format_turn_log(
        attacker_name=attacker.display_name,
        defender_name=defender.display_name,
        result_label=result_label,
        damage=damage,
        hp_after=defender.current_hp,
    )
    return PvpTurnOutcome(
        attacker_name=attacker.display_name,
        defender_name=defender.display_name,
        roll=base_roll,
        final_roll=final_roll,
        result_label=result_label,
        damage=damage,
        defender_hp_after=defender.current_hp,
        log_line=log_line,
    )


def _type_roll_modifier(attacker_types: tuple[str, ...], defender_types: tuple[str, ...]) -> int:
    relation_score = 0
    for attacker_type in attacker_types:
        for defender_type in defender_types:
            if defender_type in TYPE_EFFECTIVE_AGAINST.get(attacker_type, set()):
                relation_score += 1
            if attacker_type in TYPE_EFFECTIVE_AGAINST.get(defender_type, set()):
                relation_score -= 1
    if relation_score > 0:
        return 3
    if relation_score < 0:
        return -3
    return 0


def _stat_triangle_modifier(attacker: PvpBattleSnapshot, defender: PvpBattleSnapshot) -> int:
    bonus = 0
    if attacker.attack > defender.speed:
        bonus += 2
    if attacker.speed > defender.defense:
        bonus += 2
    if attacker.defense > defender.attack:
        bonus += 2
    if defender.attack > attacker.speed:
        bonus -= 2
    if defender.speed > attacker.defense:
        bonus -= 2
    if defender.defense > attacker.attack:
        bonus -= 2
    return bonus


def _roll_result_label(final_roll: int) -> str:
    if final_roll <= ROLL_BAND_MISS_MAX:
        return "miss"
    if final_roll <= ROLL_BAND_WEAK_MAX:
        return "weak"
    if final_roll <= ROLL_BAND_NORMAL_MAX:
        return "normal"
    if final_roll <= ROLL_BAND_EFFECTIVE_MAX:
        return "effective"
    return "supereffective"


def _damage_from_roll(attacker: PvpBattleSnapshot, defender: PvpBattleSnapshot, final_roll: int) -> int:
    result_label = _roll_result_label(final_roll)
    if result_label == "miss":
        return 0
    multiplier = {
        "weak": 0.7,
        "normal": 1.0,
        "effective": 1.3,
        "supereffective": 1.7,
    }[result_label]
    raw_damage = (2 + (attacker.attack / 12)) * (100 / (100 + defender.defense)) * multiplier
    return max(1, int(round(raw_damage)))


def _format_turn_log(*, attacker_name: str, defender_name: str, result_label: str, damage: int, hp_after: int) -> str:
    label_map = {
        "miss": "промахнулся",
        "weak": "бьёт слабо",
        "normal": "бьёт обычно",
        "effective": "бьёт эффективно",
        "supereffective": "бьёт суперэффективно",
    }
    return f"{attacker_name} {label_map[result_label]} по {defender_name}: {damage} урона, HP цели {hp_after}."


def _seconds_remaining(expires_at: Optional[datetime]) -> int:
    if expires_at is None:
        return 0
    return max(0, int((expires_at - datetime.now(UTC)).total_seconds()))


def _callback_section(callback_data: str) -> str:
    parts = callback_data.split(":")
    return parts[1] if len(parts) == 3 else ""


def _require_challenge_id(session: MenuSession) -> int:
    challenge_id = session.data.get("challenge_id")
    if challenge_id is None:
        raise ValueError("Challenge payload is missing")
    return int(challenge_id)


def _get_db(context: ContextTypes.DEFAULT_TYPE) -> Optional[Database]:
    application = getattr(context, "application", None)
    bot_data = getattr(application, "bot_data", None)
    if not isinstance(bot_data, dict):
        return None
    db = bot_data.get("db")
    return db if isinstance(db, Database) or hasattr(db, "create_pvp_challenge") else None
