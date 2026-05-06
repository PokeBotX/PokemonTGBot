"""Мини-игры section handler."""

from __future__ import annotations

import structlog
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.error import BadRequest, TelegramError
from telegram.ext import ContextTypes

from bot.navigation.session import MenuSession, session_store
from bot.ui.menu import build_back_button

logger = structlog.get_logger()

GAMES_ROUTE_ROOT = "games"
GAMES_ROUTE_FIGHTS = "gmf"
GAMES_ROUTE_SECTIONS = [GAMES_ROUTE_ROOT, GAMES_ROUTE_FIGHTS]


def register_games_routes(router) -> None:
    """Register mini-games routes."""
    for section in GAMES_ROUTE_SECTIONS:
        router.register(section, games_handler)


async def show_games_screen(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Send a fresh mini-games root screen for direct commands."""
    if not update.effective_chat or not update.effective_user or not update.effective_message:
        return
    text, remaining = await _build_games_root_text(context, update.effective_user.id, update.effective_user.username)
    sent_message = await update.effective_chat.send_message(
        text=text,
        parse_mode="HTML",
        message_thread_id=getattr(update.effective_message, "message_thread_id", None),
    )
    session_id = await session_store.create_session_async(
        chat_id=update.effective_chat.id,
        message_id=sent_message.message_id,
        user_id=update.effective_user.id,
        message_thread_id=getattr(update.effective_message, "message_thread_id", None),
        data={"games_remaining_rewarded_battles": remaining},
    )
    await sent_message.edit_reply_markup(reply_markup=_build_games_root_keyboard(session_id))


async def games_handler(update: Update, context: ContextTypes.DEFAULT_TYPE, session: MenuSession) -> None:
    """Handle mini-games root and battle info screens."""
    query = update.callback_query
    section = (query.data or "").split(":")[1] if query and query.data else GAMES_ROUTE_ROOT

    try:
        if section == GAMES_ROUTE_ROOT:
            text, remaining = await _build_games_root_text(context, session.user_id, getattr(update.effective_user, "username", None))
            new_session_id = await session_store.create_session_async(
                chat_id=session.chat_id,
                message_id=session.message_id,
                user_id=session.user_id,
                message_thread_id=session.message_thread_id,
                data={"games_remaining_rewarded_battles": remaining},
            )
            await query.edit_message_text(
                text=text,
                parse_mode="HTML",
                reply_markup=_build_games_root_keyboard(new_session_id),
            )
            return

        if section == GAMES_ROUTE_FIGHTS:
            remaining = int(session.data.get("games_remaining_rewarded_battles", 0) or 0)
            new_session_id = await session_store.create_session_async(
                chat_id=session.chat_id,
                message_id=session.message_id,
                user_id=session.user_id,
                message_thread_id=session.message_thread_id,
                data={"games_remaining_rewarded_battles": remaining},
            )
            await query.edit_message_text(
                text=_render_fights_info_text(remaining),
                parse_mode="HTML",
                reply_markup=_build_games_fights_keyboard(new_session_id),
            )
            return

    except BadRequest as exc:
        logger.warning(
            "games_handler_error",
            section=section,
            error="bad_request",
            error_message=str(exc),
            user_id=session.user_id,
            chat_id=session.chat_id,
        )
    except TelegramError as exc:
        logger.error(
            "games_handler_error",
            section=section,
            error="telegram_api",
            error_message=str(exc),
            user_id=session.user_id,
        )
    except Exception as exc:
        logger.error(
            "games_handler_error",
            section=section,
            error="unexpected",
            error_message=str(exc),
            user_id=session.user_id,
        )


async def _build_games_root_text(
    context: ContextTypes.DEFAULT_TYPE,
    telegram_id: int,
    username: str | None,
) -> tuple[str, int]:
    db = getattr(getattr(context, "application", None), "bot_data", {}).get("db")
    remaining = 0
    if db and hasattr(db, "get_remaining_pvp_reward_battles"):
        try:
            remaining = await db.get_remaining_pvp_reward_battles(telegram_id, username)
        except Exception as exc:
            logger.warning("games_reward_counter_failed", telegram_id=telegram_id, error=str(exc))
            remaining = 0
    return (
        "\n".join(
            [
                "🎮 <b>Миниигры</b>",
                "",
                "Выберите миниигру.",
                f"Боев со ставкой осталось сегодня: <b>{remaining}</b> из <b>3</b>.",
            ]
        ),
        remaining,
    )


def _render_fights_info_text(remaining: int) -> str:
    return "\n".join(
        [
            "⚔️ <b>Бои</b>",
            "",
            f"Боев со ставкой осталось сегодня: <b>{remaining}</b> из <b>3</b>.",
            "",
            "Как играть:",
            "1. Соберите полную боевую команду из 5 покемонов в профиле.",
            "2. В групповом чате ответьте <code>/fight</code> на сообщение игрока или используйте <code>/fight @username</code>.",
            "3. Вы по очереди выбираете одного бойца из своей команды.",
            "4. После выбора начинается автобой, а победитель может получить <b>500</b> PokéDollar.",
        ]
    )


def _build_games_root_keyboard(session_id: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("⚔️ Бои", callback_data=f"menu:{GAMES_ROUTE_FIGHTS}:{session_id}")],
            build_back_button(session_id).inline_keyboard[0],
        ]
    )


def _build_games_fights_keyboard(session_id: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("🔙 Назад к минииграм", callback_data=f"menu:{GAMES_ROUTE_ROOT}:{session_id}")],
        ]
    )
