"""Trade section handlers and shared trade message rendering."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Optional

import structlog
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Message, Update
from telegram.error import BadRequest, TelegramError
from telegram.ext import ContextTypes

from bot.db.database import (
    Database,
    ShopError,
    TradeMaintenanceResult,
    TradeParticipantState,
    TradeSessionSummary,
)
from bot.navigation.context import extract_context
from bot.navigation.router import NavigationRouter
from bot.navigation.session import MenuSession, session_store
from bot.ui.html import escape_html

logger = structlog.get_logger()

TRADE_ROUTE_ACCEPT = "tra"
TRADE_ROUTE_REJECT = "trr"
TRADE_ROUTE_TOGGLE_READY = "trg"
TRADE_ROUTE_CANCEL = "trc"
TRADE_ROUTE_CARD_HINT = "tca"
TRADE_ROUTE_SECTIONS = [
    TRADE_ROUTE_ACCEPT,
    TRADE_ROUTE_REJECT,
    TRADE_ROUTE_TOGGLE_READY,
    TRADE_ROUTE_CANCEL,
    TRADE_ROUTE_CARD_HINT,
]


def register_trade_routes(router: NavigationRouter) -> None:
    """Register trade callback sections."""
    for section in TRADE_ROUTE_SECTIONS:
        router.register(section, trade_handler)


async def trade_handler(update: Update, context: ContextTypes.DEFAULT_TYPE, session: MenuSession) -> None:
    """Route trade callback actions."""
    query = update.callback_query
    section = _callback_section(query.data or "")
    db = _get_db(context)
    if not db or not query or not update.effective_user:
        return

    try:
        if section == TRADE_ROUTE_ACCEPT:
            trade_id = _require_trade_id(session)
            trade = await db.accept_trade_request(trade_id, update.effective_user.id)
            next_session_id = _create_trade_session(trade)
            await _edit_trade_message(
                query,
                _render_active_trade_text(trade),
                _build_active_trade_keyboard(next_session_id, trade),
            )
            logger.info("trade_request_accepted_from_ui", trade_id=trade.trade_id, actor_id=update.effective_user.id)
            return

        if section == TRADE_ROUTE_REJECT:
            trade_id = _require_trade_id(session)
            trade = await db.cancel_trade(trade_id, update.effective_user.id, cancel_reason="rejected")
            await _edit_trade_message(
                query,
                _render_trade_closed_text(trade, "❌ Заявка на обмен отклонена."),
                None,
            )
            logger.info("trade_request_rejected_from_ui", trade_id=trade.trade_id, actor_id=update.effective_user.id)
            return

        if section == TRADE_ROUTE_CANCEL:
            trade_id = _require_trade_id(session)
            trade = await db.cancel_trade(trade_id, update.effective_user.id, cancel_reason="canceled")
            await _edit_trade_message(
                query,
                _render_trade_closed_text(trade, "🛑 Обмен отменён."),
                None,
            )
            logger.info("trade_canceled_from_ui", trade_id=trade.trade_id, actor_id=update.effective_user.id)
            return

        if section == TRADE_ROUTE_TOGGLE_READY:
            result = await db.toggle_trade_ready(
                telegram_id=update.effective_user.id,
                username=update.effective_user.username,
            )
            if result.completed:
                await _edit_trade_message(
                    query,
                    _render_trade_completed_text(result.trade),
                    None,
                )
                await query.message.reply_text(
                    _render_trade_completion_announcement(result.trade),
                    parse_mode="HTML",
                    message_thread_id=getattr(query.message, "message_thread_id", None),
                )
            else:
                next_session_id = _create_trade_session(result.trade)
                await _edit_trade_message(
                    query,
                    _render_active_trade_text(result.trade),
                    _build_active_trade_keyboard(next_session_id, result.trade),
                )
            logger.info(
                "trade_ready_toggled_from_ui",
                trade_id=result.trade.trade_id,
                actor_id=update.effective_user.id,
                completed=result.completed,
            )
            return

        if section == TRADE_ROUTE_CARD_HINT:
            user_pokemon_id = session.data.get("trade_user_pokemon_id") or session.data.get("market_entry_user_pokemon_id")
            if user_pokemon_id is None:
                raise ValueError("Trade card payload is missing")
            active_trade = await db.get_active_trade_for_user(update.effective_user.id, update.effective_user.username)
            if not active_trade:
                await query.answer("У вас нет активного обмена.", show_alert=False)
                return
            await query.message.reply_text(
                "\n".join(
                    [
                        "🤝 <b>Добавить в обмен</b>",
                        "",
                        f"Используйте команду: <code>/tradeadd {int(user_pokemon_id)}</code>",
                    ]
                ),
                parse_mode="HTML",
                message_thread_id=getattr(query.message, "message_thread_id", None),
            )
            await query.answer("Команда для добавления отправлена.", show_alert=False)
            return

    except ShopError as exc:
        logger.warning(
            "trade_handler_error",
            error="trade_rule",
            error_message=str(exc),
            user_id=update.effective_user.id,
            section=section,
        )
        await query.answer(str(exc), show_alert=False)
        return
    except Exception as exc:
        logger.error(
            "trade_handler_error",
            error="unexpected",
            error_message=str(exc),
            user_id=update.effective_user.id,
            section=section,
        )
        await query.answer("Экран трейда устарел. Откройте обмен заново.", show_alert=False)


async def start_trade_request(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    *,
    target_telegram_id: int,
    target_username: Optional[str],
) -> Message:
    """Create and send a pending trade request message."""
    db = _get_db(context)
    if not db or not update.effective_user or not update.effective_chat:
        raise ShopError("Трейды временно недоступны.")
    msg_context = extract_context(update)
    trade = await db.create_trade_request(
        initiator_telegram_id=update.effective_user.id,
        initiator_username=update.effective_user.username,
        target_telegram_id=target_telegram_id,
        target_username=target_username,
        chat_id=msg_context.chat_id,
        message_thread_id=msg_context.message_thread_id,
    )
    request_session_id = session_store.create_session(
        chat_id=msg_context.chat_id,
        message_id=0,
        user_id=trade.target.telegram_id,
        message_thread_id=msg_context.message_thread_id,
        data={"trade_id": trade.trade_id, "allowed_user_ids": [trade.initiator.telegram_id]},
    )
    sent_message = await update.effective_chat.send_message(
        text=_render_pending_trade_text(trade),
        parse_mode="HTML",
        reply_markup=_build_pending_trade_keyboard(request_session_id),
        message_thread_id=msg_context.message_thread_id,
    )
    session_store.delete_session(request_session_id)
    final_session_id = session_store.create_session(
        chat_id=msg_context.chat_id,
        message_id=sent_message.message_id,
        user_id=trade.target.telegram_id,
        message_thread_id=msg_context.message_thread_id,
        data={"trade_id": trade.trade_id, "allowed_user_ids": [trade.initiator.telegram_id]},
    )
    await sent_message.edit_reply_markup(reply_markup=_build_pending_trade_keyboard(final_session_id))
    await db.attach_trade_request_message(trade.trade_id, sent_message.message_id)
    logger.info(
        "trade_request_message_sent",
        trade_id=trade.trade_id,
        request_message_id=sent_message.message_id,
        initiator_id=trade.initiator.telegram_id,
        target_id=trade.target.telegram_id,
    )
    return sent_message


async def handle_trade_add_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /tradeadd <user_pokemon_id>."""
    db = _get_db(context)
    if not db or not update.effective_user or not update.effective_chat or not update.effective_message:
        return
    user_pokemon_id = _parse_trade_pokemon_id(update.effective_message.text or "", command_name="tradeadd")
    if user_pokemon_id is None:
        await update.effective_chat.send_message(
            "🤝 Используйте команду так: <code>/tradeadd 12345</code>",
            parse_mode="HTML",
            message_thread_id=getattr(update.effective_message, "message_thread_id", None),
        )
        return
    try:
        trade = await db.add_trade_offer_pokemon(
            telegram_id=update.effective_user.id,
            username=update.effective_user.username,
            user_pokemon_id=user_pokemon_id,
        )
    except ShopError as exc:
        await update.effective_chat.send_message(
            f"⚠️ {exc}",
            message_thread_id=getattr(update.effective_message, "message_thread_id", None),
        )
        return
    await _refresh_trade_projection(context, trade)
    await update.effective_chat.send_message(
        f"✅ Покемон <code>{user_pokemon_id}</code> добавлен в обмен.",
        parse_mode="HTML",
        message_thread_id=getattr(update.effective_message, "message_thread_id", None),
    )


async def handle_trade_remove_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /traderemove <user_pokemon_id>."""
    db = _get_db(context)
    if not db or not update.effective_user or not update.effective_chat or not update.effective_message:
        return
    user_pokemon_id = _parse_trade_pokemon_id(update.effective_message.text or "", command_name="traderemove")
    if user_pokemon_id is None:
        await update.effective_chat.send_message(
            "🤝 Используйте команду так: <code>/traderemove 12345</code>",
            parse_mode="HTML",
            message_thread_id=getattr(update.effective_message, "message_thread_id", None),
        )
        return
    try:
        trade = await db.remove_trade_offer_pokemon(
            telegram_id=update.effective_user.id,
            username=update.effective_user.username,
            user_pokemon_id=user_pokemon_id,
        )
    except ShopError as exc:
        await update.effective_chat.send_message(
            f"⚠️ {exc}",
            message_thread_id=getattr(update.effective_message, "message_thread_id", None),
        )
        return
    await _refresh_trade_projection(context, trade)
    await update.effective_chat.send_message(
        f"✅ Покемон <code>{user_pokemon_id}</code> убран из обмена.",
        parse_mode="HTML",
        message_thread_id=getattr(update.effective_message, "message_thread_id", None),
    )


async def run_trade_maintenance_job(context) -> None:
    """Expire stale pending and active trades and reflect it in Telegram."""
    application = getattr(context, "application", None)
    bot_data = getattr(application, "bot_data", {}) if application else {}
    db = bot_data.get("db") if isinstance(bot_data, dict) else None
    if not db:
        return

    result = await db.process_trade_maintenance()
    await _reflect_trade_maintenance(context, result)


async def _reflect_trade_maintenance(context: ContextTypes.DEFAULT_TYPE, result: TradeMaintenanceResult) -> None:
    for trade in result.expired_requests:
        await _edit_trade_message_by_ids(
            context,
            trade.chat_id,
            trade.message_id,
            _render_trade_closed_text(trade, "⌛ Заявка на обмен истекла."),
            None,
            trade.message_thread_id,
        )
    for trade in result.expired_active_trades:
        await _edit_trade_message_by_ids(
            context,
            trade.chat_id,
            trade.message_id,
            _render_trade_closed_text(trade, "⌛ Активный обмен истёк."),
            None,
            trade.message_thread_id,
        )


async def _refresh_trade_projection(context: ContextTypes.DEFAULT_TYPE, trade: TradeSessionSummary) -> None:
    session_id = _create_trade_session(trade)
    await _edit_trade_message_by_ids(
        context,
        trade.chat_id,
        trade.message_id,
        _render_active_trade_text(trade),
        _build_active_trade_keyboard(session_id, trade),
        trade.message_thread_id,
    )


def _render_pending_trade_text(trade: TradeSessionSummary) -> str:
    seconds_left = _seconds_remaining(trade.pending_expires_at)
    return "\n".join(
        [
            "🤝 <b>Новая заявка на обмен</b>",
            "",
            f"{escape_html(trade.initiator.label)} хочет обменяться с {escape_html(trade.target.label)}.",
            f"Ответьте в течение <b>{seconds_left} сек.</b>",
        ]
    )


def _render_active_trade_text(trade: TradeSessionSummary) -> str:
    seconds_left = _seconds_remaining(trade.trade_expires_at)
    return "\n".join(
        [
            "🤝 <b>Активный обмен</b>",
            "",
            _render_trade_side("Сторона 1", trade.initiator),
            "",
            _render_trade_side("Сторона 2", trade.target),
            "",
            f"Осталось: <b>{seconds_left} сек.</b>",
        ]
    )


def _render_trade_side(title: str, participant: TradeParticipantState) -> str:
    lines = [
        f"<b>{escape_html(title)}</b>: {escape_html(participant.label)} {'✅' if participant.is_ready else '⏳'}",
    ]
    if not participant.offers:
        lines.append("• Пока пусто")
        return "\n".join(lines)
    for offer in participant.offers:
        lines.append(
            f"• {escape_html(offer.name)} [{offer.user_pokemon_id}] | {escape_html(offer.rarity)}"
        )
    return "\n".join(lines)


def _render_trade_completed_text(trade: TradeSessionSummary) -> str:
    return "\n".join(
        [
            "✅ <b>Обмен завершён</b>",
            "",
            f"{escape_html(trade.initiator.label)} ↔ {escape_html(trade.target.label)}",
            f"Передано: <b>{len(trade.initiator.offers)}</b> на <b>{len(trade.target.offers)}</b>",
        ]
    )


def _render_trade_completion_announcement(trade: TradeSessionSummary) -> str:
    return "\n".join(
        [
            "🎉 <b>Обмен совершен</b>",
            "",
            f"{escape_html(trade.initiator.label)} ⇄ {escape_html(trade.target.label)}",
            "",
            _render_trade_completion_side("Отдал 1-й участник", trade.initiator),
            "",
            _render_trade_completion_side("Отдал 2-й участник", trade.target),
        ]
    )


def _render_trade_completion_side(title: str, participant: TradeParticipantState) -> str:
    lines = [f"<b>{escape_html(title)}</b>:"]
    if not participant.offers:
        lines.append("• Ничего")
        return "\n".join(lines)
    for offer in participant.offers:
        lines.append(
            f"• {escape_html(offer.name)} [{offer.user_pokemon_id}] | {escape_html(offer.rarity)}"
        )
    return "\n".join(lines)


def _render_trade_closed_text(trade: TradeSessionSummary, title: str) -> str:
    return "\n".join(
        [
            title,
            "",
            f"{escape_html(trade.initiator.label)} ↔ {escape_html(trade.target.label)}",
        ]
    )


def _build_pending_trade_keyboard(session_id: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("✅ Принять", callback_data=f"menu:{TRADE_ROUTE_ACCEPT}:{session_id}")],
            [InlineKeyboardButton("❌ Отклонить", callback_data=f"menu:{TRADE_ROUTE_REJECT}:{session_id}")],
        ]
    )


def _build_active_trade_keyboard(session_id: str, trade: TradeSessionSummary) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("✅ Готов / ↩️ Не готов", callback_data=f"menu:{TRADE_ROUTE_TOGGLE_READY}:{session_id}")],
            [InlineKeyboardButton("🛑 Отменить", callback_data=f"menu:{TRADE_ROUTE_CANCEL}:{session_id}")],
        ]
    )


def _create_trade_session(trade: TradeSessionSummary) -> str:
    message_id = trade.message_id
    if message_id is None:
        raise ValueError("Trade message id is missing")
    return session_store.create_session(
        chat_id=trade.chat_id,
        message_id=message_id,
        user_id=trade.initiator.telegram_id,
        message_thread_id=trade.message_thread_id,
        data={
            "trade_id": trade.trade_id,
            "allowed_user_ids": [trade.target.telegram_id],
        },
    )


def _require_trade_id(session: MenuSession) -> int:
    trade_id = session.data.get("trade_id")
    if trade_id is None:
        raise ValueError("Trade payload is missing")
    return int(trade_id)


async def _edit_trade_message(query, text: str, reply_markup: Optional[InlineKeyboardMarkup]) -> None:
    await query.edit_message_text(text=text, parse_mode="HTML", reply_markup=reply_markup)


async def _edit_trade_message_by_ids(
    context: ContextTypes.DEFAULT_TYPE,
    chat_id: int,
    message_id: Optional[int],
    text: str,
    reply_markup: Optional[InlineKeyboardMarkup],
    message_thread_id: Optional[int],
) -> None:
    if message_id is None:
        return
    try:
        await context.bot.edit_message_text(
            chat_id=chat_id,
            message_id=message_id,
            text=text,
            parse_mode="HTML",
            reply_markup=reply_markup,
        )
    except BadRequest as exc:
        if "message to edit not found" not in str(exc).lower():
            logger.warning("trade_message_edit_failed", chat_id=chat_id, message_id=message_id, error=str(exc))
    except TelegramError as exc:
        logger.warning("trade_message_edit_failed", chat_id=chat_id, message_id=message_id, error=str(exc))


def _parse_trade_pokemon_id(text: str, *, command_name: str) -> Optional[int]:
    parts = text.split()
    if len(parts) != 2:
        return None
    command = parts[0].lstrip("/").split("@", maxsplit=1)[0]
    if command != command_name:
        return None
    try:
        return int(parts[1])
    except ValueError:
        return None


def _seconds_remaining(expires_at: Optional[datetime]) -> int:
    if expires_at is None:
        return 0
    return max(0, int((expires_at - datetime.now(UTC)).total_seconds()))


def _callback_section(data: str) -> str:
    parts = data.split(":")
    return parts[1] if len(parts) == 3 else ""


def _get_db(context: ContextTypes.DEFAULT_TYPE) -> Optional[Database]:
    application = getattr(context, "application", None)
    bot_data = getattr(application, "bot_data", None) if application is not None else None
    if not isinstance(bot_data, dict):
        return None
    db = bot_data.get("db")
    return db if isinstance(db, Database) or hasattr(db, "create_trade_request") else None
