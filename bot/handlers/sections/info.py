"""Info section handler."""
from __future__ import annotations

import structlog
from telegram import Message, Update
from telegram.error import BadRequest, TelegramError
from telegram.ext import ContextTypes

from bot.navigation.context import extract_context
from bot.navigation.session import MenuSession, session_store
from bot.ui.html import display_name, escape_html
from bot.ui.menu import build_back_button

logger = structlog.get_logger()


async def show_info_screen(update: Update, context: ContextTypes.DEFAULT_TYPE) -> Message:
    """Send a fresh info/guide message for direct `/info` usage."""
    msg_context = extract_context(update)
    sent_message = await update.effective_chat.send_message(
        text=_render_info_text(_display_user(update)),
        parse_mode="HTML",
        message_thread_id=msg_context.message_thread_id,
    )
    session_id = session_store.create_session(
        chat_id=msg_context.chat_id,
        message_id=sent_message.message_id,
        user_id=msg_context.user_id,
        message_thread_id=msg_context.message_thread_id,
    )
    await sent_message.edit_reply_markup(reply_markup=build_back_button(session_id))
    logger.info("info_command_sent", session_id=session_id, user_id=msg_context.user_id)
    return sent_message


async def info_handler(update: Update, context: ContextTypes.DEFAULT_TYPE, session: MenuSession) -> None:
    """Handle info section from inline navigation."""
    query = update.callback_query

    try:
        new_session_id = session_store.create_session(
            chat_id=session.chat_id,
            message_id=session.message_id,
            user_id=session.user_id,
            message_thread_id=session.message_thread_id,
        )
        await query.edit_message_text(
            text=_render_info_text(_display_user(update)),
            parse_mode="HTML",
            reply_markup=build_back_button(new_session_id),
        )
        logger.info(
            "section_displayed",
            section="info",
            session_id=new_session_id,
            user_id=session.user_id,
        )
    except BadRequest as e:
        logger.warning(
            "section_handler_error",
            section="info",
            error="bad_request",
            error_message=str(e),
            user_id=session.user_id,
            chat_id=session.chat_id,
        )
    except TelegramError as e:
        logger.error(
            "section_handler_error",
            section="info",
            error="telegram_api",
            error_message=str(e),
            user_id=session.user_id,
        )
    except Exception as e:
        logger.error(
            "section_handler_error",
            section="info",
            error="unexpected",
            error_message=str(e),
            user_id=session.user_id,
        )


def _display_user(update: Update) -> str:
    user = update.effective_user
    if not user:
        return "тренер"
    return display_name(getattr(user, "username", None), getattr(user, "first_name", None))


def _render_info_text(user_label: str) -> str:
    return "\n".join(
        [
            f"ℹ️ <b>{escape_html(user_label)}</b>, общий гайд по боту:",
            "",
            "• 👀 Время от времени в беседе появляются дикие покемоны в виде сообщения с картинкой.",
            "Поймать их может любой участник чата: нажмите на подходящий покебол и попробуйте забрать покемона себе.",
            "У каждого игрока только одна попытка на одного покемона.",
            "",
            "• 🎁 В магазине можно забирать бонус и тратить валюту на крутки:",
            "<code>/shop</code> — забирайте бонус, покупайте мячи и выбивайте новых покемонов.",
            "",
            "• 🏰 Посмотреть свой профиль, прогресс и настройки можно здесь:",
            "<code>/profile</code> — профиль и настройки.",
            "<code>/collection</code> — вся ваша коллекция покемонов.",
            "",
            "• 🤝 Для торговли используйте рынок:",
            "<code>/market</code> — покупка, продажа, свои лоты и заявки.",
            "Покемона можно выставить на рынок прямо из его карточки.",
            "<code>/trade</code> — предложить обмен другому пользователю в групповом чате.",
            "<code>/tradeadd id_экземпляра</code> — добавить покемона в активный обмен.",
            "<code>/traderemove id_экземпляра</code> — убрать покемона из активного обмена.",
            "",
            "• 🔎 Найти нужного покемона и узнать его ID можно через поиск:",
            "<code>/search имя_покемона</code> — поиск по имени.",
            "",
            "• 🎯 Если хотите ускорить появление покемона в чате, используйте:",
            "<code>/find</code> — запускает проверку появления покемона в групповом чате.",
        ]
    )
