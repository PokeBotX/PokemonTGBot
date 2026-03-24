"""Shop section handler."""

from __future__ import annotations

from pathlib import Path
from typing import Optional

import structlog
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Message, Update
from telegram.error import BadRequest, TelegramError
from telegram.ext import ContextTypes

from bot.db.database import (
    BonusClaimResult,
    BonusNotReadyError,
    Database,
    InsufficientFundsError,
    ItemPurchaseResult,
    MASTERBALL_PRICE,
    POKEDOLLAR_CODE,
    PokemonReward,
    SPIN_PRICE,
    SpinResult,
    SummarySessionError,
    ULTRABALL_PRICE,
    ShopView,
)
from bot.navigation.router import NavigationRouter, parse_callback_data
from bot.navigation.context import extract_context
from bot.navigation.session import MenuSession, session_store
from bot.ui.menu import build_back_button
from bot.ui.pokemon_cards import send_captioned_image

logger = structlog.get_logger()

SHOP_ROUTE_SECTIONS = [
    "shop",
    "shop_pokemon",
    "shop_items",
    "shop_bonus",
    "shop_spin_1",
    "shop_spin_5",
    "shop_buy_ultraball",
    "shop_buy_masterball",
    "shop_vip",
    "shop_detail_1",
    "shop_detail_2",
    "shop_detail_3",
    "shop_detail_4",
    "shop_detail_5",
]

FALLBACK_IMAGE_PATH = Path("image.png")
SHOP_VIEW_MAIN = "main"
SHOP_VIEW_POKEMON = "pokemon"
SHOP_VIEW_ITEMS = "items"


def register_shop_routes(router: NavigationRouter) -> None:
    """Register all shop-related callback sections."""
    for section in SHOP_ROUTE_SECTIONS:
        router.register(section, shop_handler)


async def show_shop_screen(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    screen: str = SHOP_VIEW_MAIN,
    status_text: Optional[str] = None,
) -> Message:
    """Send a fresh shop message for direct commands like /shop."""
    msg_context = extract_context(update)
    username = update.effective_user.username if update.effective_user else None
    user_label = _display_user(update)
    db = _get_db(context)

    if not db:
        text = "🛒 <b>Магазин временно недоступен</b>\n\nБаза данных не подключена."
        sent_message = await update.effective_chat.send_message(
            text=text,
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
        return sent_message

    logger.info("shop_command_fetch_start", screen=screen, user_id=msg_context.user_id)
    shop_view = await db.get_shop_view(msg_context.user_id, username)
    logger.info("shop_command_fetch_done", screen=screen, user_id=msg_context.user_id)
    sent_message = await update.effective_chat.send_message(
        text=_render_shop_text(shop_view, status_text, screen, user_label),
        parse_mode="HTML",
        message_thread_id=msg_context.message_thread_id,
    )
    session_id = session_store.create_session(
        chat_id=msg_context.chat_id,
        message_id=sent_message.message_id,
        user_id=msg_context.user_id,
        message_thread_id=msg_context.message_thread_id,
    )
    await sent_message.edit_reply_markup(
        reply_markup=_build_shop_keyboard(session_id, shop_view, screen)
    )
    logger.info("shop_command_sent", screen=screen, session_id=session_id, user_id=msg_context.user_id)
    return sent_message


async def shop_handler(update: Update, context: ContextTypes.DEFAULT_TYPE, session: MenuSession) -> None:
    """Handle shop screen, shop actions, and x5 spin detail views."""
    query = update.callback_query
    callback_data = parse_callback_data(query.data)
    section = callback_data.section if callback_data else "shop"

    try:
        logger.info("shop_handler_start", section=section, user_id=session.user_id, session_id=session.session_id)
        if section.startswith("shop_detail_"):
            await _handle_spin_detail(update, context, session, section)
            return

        db = _get_db(context)
        if not db:
            logger.info("shop_db_missing", section=section, user_id=session.user_id)
            await _edit_shop_message(
                query,
                session,
                "🛒 <b>Магазин временно недоступен</b>\n\nБаза данных не подключена.",
                build_back_button(_create_session(session)),
            )
            return

        username = update.effective_user.username if update.effective_user else None
        status_text: Optional[str] = None

        if section == "shop":
            logger.info("shop_db_fetch_start", section=section, user_id=session.user_id)
            shop_view = await db.get_shop_view(session.user_id, username)
            logger.info("shop_db_fetch_done", section=section, user_id=session.user_id)
            screen = SHOP_VIEW_MAIN
        elif section == "shop_pokemon":
            logger.info("shop_db_fetch_start", section=section, user_id=session.user_id)
            shop_view = await db.get_shop_view(session.user_id, username)
            logger.info("shop_db_fetch_done", section=section, user_id=session.user_id)
            screen = SHOP_VIEW_POKEMON
        elif section == "shop_items":
            logger.info("shop_db_fetch_start", section=section, user_id=session.user_id)
            shop_view = await db.get_shop_view(session.user_id, username)
            logger.info("shop_db_fetch_done", section=section, user_id=session.user_id)
            screen = SHOP_VIEW_ITEMS
        elif section == "shop_bonus":
            logger.info("shop_bonus_claim_start", user_id=session.user_id)
            bonus_result = await db.claim_daily_bonus(session.user_id, username)
            logger.info("shop_bonus_claim_done", user_id=session.user_id, amount_claimed=bonus_result.amount_claimed)
            shop_view = bonus_result.shop_view
            screen = SHOP_VIEW_MAIN
            status_text = _render_bonus_claim_text(
                _display_user(update),
                bonus_result,
            )
        elif section == "shop_buy_ultraball":
            logger.info("shop_purchase_start", user_id=session.user_id, item_code="ultraball")
            purchase_result = await db.purchase_item(session.user_id, username, "ultraball")
            logger.info("shop_purchase_done", user_id=session.user_id, item_code="ultraball")
            shop_view = purchase_result.shop_view
            screen = SHOP_VIEW_ITEMS
            status_text = _format_purchase_status(purchase_result)
        elif section == "shop_buy_masterball":
            logger.info("shop_purchase_start", user_id=session.user_id, item_code="masterball")
            purchase_result = await db.purchase_item(session.user_id, username, "masterball")
            logger.info("shop_purchase_done", user_id=session.user_id, item_code="masterball")
            shop_view = purchase_result.shop_view
            screen = SHOP_VIEW_ITEMS
            status_text = _format_purchase_status(purchase_result)
        elif section == "shop_spin_1":
            logger.info("shop_spin_start", user_id=session.user_id, spin_count=1)
            spin_result = await db.spin_gacha(session.user_id, username, 1)
            logger.info("shop_spin_done", user_id=session.user_id, spin_count=1)
            shop_view = spin_result.shop_view
            screen = SHOP_VIEW_POKEMON
            status_text = None
            logger.info("shop_reward_card_start", user_id=session.user_id, reward_name=spin_result.rewards[0].name)
            await _send_reward_card(context, session, spin_result.rewards[0], shop_view, _display_user(update))
            logger.info("shop_reward_card_done", user_id=session.user_id, reward_name=spin_result.rewards[0].name)
        elif section == "shop_spin_5":
            logger.info("shop_spin_start", user_id=session.user_id, spin_count=5)
            spin_result = await db.spin_gacha(session.user_id, username, 5)
            logger.info("shop_spin_done", user_id=session.user_id, spin_count=5)
            shop_view = spin_result.shop_view
            screen = SHOP_VIEW_POKEMON
            status_text = f"🎰 Выполнено <b>5</b> круток. Списано <b>{spin_result.spent_amount} {POKEDOLLAR_CODE}</b>."
            logger.info("shop_batch_summary_start", user_id=session.user_id, rewards_count=len(spin_result.rewards))
            await _send_batch_summary(context, session, spin_result)
            logger.info("shop_batch_summary_done", user_id=session.user_id, rewards_count=len(spin_result.rewards))
        elif section == "shop_vip":
            logger.info("shop_db_fetch_start", section=section, user_id=session.user_id)
            shop_view = await db.get_shop_view(session.user_id, username)
            logger.info("shop_db_fetch_done", section=section, user_id=session.user_id)
            screen = SHOP_VIEW_MAIN
            status_text = "⭐ VIP пока недоступен. Этот раздел будет добавлен позже."
        else:
            logger.info("shop_db_fetch_start", section=section, user_id=session.user_id)
            shop_view = await db.get_shop_view(session.user_id, username)
            logger.info("shop_db_fetch_done", section=section, user_id=session.user_id)
            screen = SHOP_VIEW_MAIN
            status_text = "⚠️ Неизвестное действие магазина."

        logger.info("shop_edit_start", section=section, user_id=session.user_id, screen=screen)
        await _edit_shop_message(
            query,
            session,
            _render_shop_text(shop_view, status_text, screen, _display_user(update)),
            _build_shop_keyboard(_create_session(session), shop_view, screen),
        )
        logger.info("shop_edit_done", section=section, user_id=session.user_id, screen=screen)
        logger.info("shop_action_completed", section=section, user_id=session.user_id)

    except BonusNotReadyError as exc:
        logger.info("shop_bonus_cooldown_fetch_start", user_id=session.user_id)
        shop_view = await db.get_shop_view(session.user_id, username)
        logger.info("shop_bonus_cooldown_fetch_done", user_id=session.user_id)
        logger.info("shop_edit_start", section=section, user_id=session.user_id, screen=SHOP_VIEW_MAIN)
        await _edit_shop_message(
            query,
            session,
            _render_shop_text(
                shop_view,
                _render_bonus_cooldown_text(_display_user(update), exc.remaining_seconds, shop_view.balance),
                SHOP_VIEW_MAIN,
                _display_user(update),
            ),
            _build_shop_keyboard(_create_session(session), shop_view, SHOP_VIEW_MAIN),
        )
        logger.info("shop_edit_done", section=section, user_id=session.user_id, screen=SHOP_VIEW_MAIN)
        logger.info("shop_bonus_not_ready", user_id=session.user_id, remaining_seconds=exc.remaining_seconds)
    except InsufficientFundsError:
        try:
            await query.answer("💸 Недостаточно PokéDollar для этого действия.", show_alert=False)
        except TelegramError:
            pass
        logger.info("shop_insufficient_fetch_start", user_id=session.user_id, section=section)
        shop_view = await db.get_shop_view(session.user_id, username)
        logger.info("shop_insufficient_fetch_done", user_id=session.user_id, section=section)
        target_screen = SHOP_VIEW_POKEMON if section.startswith("shop_spin_") else SHOP_VIEW_ITEMS
        logger.info("shop_edit_start", section=section, user_id=session.user_id, screen=target_screen)
        await _edit_shop_message(
            query,
            session,
            _render_shop_text(
                shop_view,
                "💸 Недостаточно PokéDollar для этого действия.",
                target_screen,
                _display_user(update),
            ),
            _build_shop_keyboard(_create_session(session), shop_view, target_screen),
        )
        logger.info("shop_edit_done", section=section, user_id=session.user_id, screen=target_screen)
        logger.info("shop_insufficient_funds", section=section, user_id=session.user_id)
    except SummarySessionError as exc:
        logger.warning("shop_summary_error", user_id=session.user_id, error=str(exc))
    except BadRequest as exc:
        logger.warning(
            "shop_handler_error",
            section=section,
            error="bad_request",
            error_message=str(exc),
            user_id=session.user_id,
            chat_id=session.chat_id,
        )
    except TelegramError as exc:
        logger.error(
            "shop_handler_error",
            section=section,
            error="telegram_api",
            error_message=str(exc),
            user_id=session.user_id,
        )
    except Exception as exc:
        logger.error(
            "shop_handler_error",
            section=section,
            error="unexpected",
            error_message=str(exc),
            user_id=session.user_id,
        )


def _display_user(update: Optional[Update]) -> str:
    if update and update.effective_user:
        username = getattr(update.effective_user, "username", None)
        if username:
            return f"@{username}"
        first_name = getattr(update.effective_user, "first_name", None)
        if first_name:
            return first_name
    return "тренер"


def _display_user_text(update: Optional[Update]) -> str:
    return _display_user(update)


def _render_main_shop_text(user_label: str, shop_view: ShopView) -> str:
    return "\n".join([
        f"🛍 {user_label}, добро пожаловать в магазин!",
        f"👛 Ваш баланс: 💵{shop_view.balance}  🪙{shop_view.pokecoin_balance}",
        "",
        "Выберите желаемый раздел:",
    ])


def _render_pokemon_shop_text(user_label: str, shop_view: ShopView) -> str:
    lines = [
        f"🎟 {user_label}, выберите желаемую опцию:",
        f"🎲 - случайный персонаж: 💵{SPIN_PRICE}",
    ]
    if shop_view.balance >= SPIN_PRICE * 5:
        lines.append(f"🎲 - случайный персонаж x5: 💵{SPIN_PRICE * 5}")
    lines.extend(["", f"👛 Ваш баланс: 💵{shop_view.balance}"])
    return "\n".join(lines)


def _render_items_shop_text(user_label: str, shop_view: ShopView) -> str:
    return "\n".join([
        f"🎒 {user_label}, выберите нужный предмет:",
        f"🟡 Ultraball: 💵{ULTRABALL_PRICE}",
        f"🟣 Masterball: 💵{MASTERBALL_PRICE}",
        "",
        f"👛 Ваш баланс: 💵{shop_view.balance}",
    ])


def _render_bonus_claim_text(user_label: str, bonus_result: BonusClaimResult) -> str:
    return "\n".join([
        f"🎁 {user_label}, Вы получили 💵 {bonus_result.amount_claimed}, теперь у вас 💵{bonus_result.shop_view.balance}",
        "⌛️ Можно забрать снова через: 1 час",
        "⏰ Будет накапливаться до: 6 часов",
    ])


def _render_bonus_cooldown_text(user_label: str, remaining_seconds: int, balance: int) -> str:
    return "\n".join([
        f"🎁 {user_label}, бонус пока недоступен.",
        f"⌛️ Можно забрать снова через: {_format_duration(remaining_seconds)}",
        "⏰ Будет накапливаться до: 6 часов",
        "",
        f"👛 Ваш баланс: 💵{balance}",
    ])


def _build_reward_continue_keyboard(shop_view: ShopView, session_id: str) -> InlineKeyboardMarkup:
    keyboard = []
    if shop_view.balance >= SPIN_PRICE:
        keyboard.append([InlineKeyboardButton(f"🎲 Крутка: 💵{SPIN_PRICE}", callback_data=f"menu:shop_spin_1:{session_id}")])
    if shop_view.balance >= SPIN_PRICE * 5:
        keyboard.append([InlineKeyboardButton(f"🎲 Крутка x5: 💵{SPIN_PRICE * 5}", callback_data=f"menu:shop_spin_5:{session_id}")])
    return InlineKeyboardMarkup(keyboard)


def _get_db(context: ContextTypes.DEFAULT_TYPE) -> Optional[Database]:
    application = getattr(context, "application", None)
    if not application or not hasattr(application, "bot_data"):
        return None
    bot_data = getattr(application, "bot_data", None)
    if not isinstance(bot_data, dict):
        return None
    db = bot_data.get("db")
    if not db or not hasattr(db, "get_shop_view"):
        return None
    return db


def _create_session(session: MenuSession, data: Optional[dict[str, object]] = None) -> str:
    return session_store.create_session(
        chat_id=session.chat_id,
        message_id=session.message_id,
        user_id=session.user_id,
        message_thread_id=session.message_thread_id,
        data=data,
    )


def _build_shop_keyboard(session_id: str, shop_view: ShopView, screen: str) -> InlineKeyboardMarkup:
    keyboard: list[list[InlineKeyboardButton]] = []

    if screen == SHOP_VIEW_MAIN:
        keyboard.append([InlineKeyboardButton("🎮 Покемоны", callback_data=f"menu:shop_pokemon:{session_id}")])
        keyboard.append([InlineKeyboardButton("🎁 Бонус", callback_data=f"menu:shop_bonus:{session_id}")])
        keyboard.append([InlineKeyboardButton("🎒 Предметы", callback_data=f"menu:shop_items:{session_id}")])
        keyboard.append([InlineKeyboardButton("⭐ VIP", callback_data=f"menu:shop_vip:{session_id}")])
        keyboard.extend(build_back_button(session_id).inline_keyboard)
        return InlineKeyboardMarkup(keyboard)

    if screen == SHOP_VIEW_POKEMON:
        keyboard.append([InlineKeyboardButton(f"🎲 Случайный персонаж: 💵{SPIN_PRICE}", callback_data=f"menu:shop_spin_1:{session_id}")])
        if shop_view.balance >= SPIN_PRICE * 5:
            keyboard.append([InlineKeyboardButton(f"🎲 Случайный персонаж x5: 💵{SPIN_PRICE * 5}", callback_data=f"menu:shop_spin_5:{session_id}")])
        keyboard.append([InlineKeyboardButton("🔙 Назад в магазин", callback_data=f"menu:shop:{session_id}")])
        return InlineKeyboardMarkup(keyboard)

    if screen == SHOP_VIEW_ITEMS:
        keyboard.append([InlineKeyboardButton(f"🟡 Ultraball: 💵{ULTRABALL_PRICE}", callback_data=f"menu:shop_buy_ultraball:{session_id}")])
        keyboard.append([InlineKeyboardButton(f"🟣 Masterball: 💵{MASTERBALL_PRICE}", callback_data=f"menu:shop_buy_masterball:{session_id}")])
        keyboard.append([InlineKeyboardButton("🔙 Назад в магазин", callback_data=f"menu:shop:{session_id}")])
        return InlineKeyboardMarkup(keyboard)

    return InlineKeyboardMarkup(keyboard)


def _render_shop_text(shop_view: ShopView, status_text: Optional[str] = None, screen: str = SHOP_VIEW_MAIN, user_label: str = "тренер") -> str:
    if status_text and screen == SHOP_VIEW_MAIN and status_text.startswith("🎁"):
        return status_text

    if screen == SHOP_VIEW_MAIN:
        base_text = _render_main_shop_text(user_label, shop_view)
    elif screen == SHOP_VIEW_POKEMON:
        base_text = _render_pokemon_shop_text(user_label, shop_view)
    elif screen == SHOP_VIEW_ITEMS:
        base_text = _render_items_shop_text(user_label, shop_view)
    else:
        base_text = ""

    if status_text:
        return f"{base_text}\n\n{status_text}" if base_text else status_text
    return base_text


async def _edit_shop_message(
    query, session: MenuSession, text: str, reply_markup: InlineKeyboardMarkup
) -> None:
    await query.edit_message_text(
        text=text,
        parse_mode="HTML",
        reply_markup=reply_markup,
    )


def _format_purchase_status(result: ItemPurchaseResult) -> str:
    return (
        f"✅ Куплен <b>{result.item_name}</b> за <b>{result.item_price} {POKEDOLLAR_CODE}</b>.\n"
        f"Теперь у вас: <b>{result.quantity_after}</b>"
    )


def _format_duration(total_seconds: int) -> str:
    if total_seconds <= 0:
        return "00:00"
    hours, remainder = divmod(total_seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    if hours:
        return f"{hours:02d}:{minutes:02d}:{seconds:02d}"
    return f"{minutes:02d}:{seconds:02d}"


async def _send_reward_card(
    context: ContextTypes.DEFAULT_TYPE, session: MenuSession, reward: PokemonReward, shop_view: Optional[ShopView] = None, user_label: Optional[str] = None
) -> Message:
    caption = _render_reward_caption(reward, user_label)
    logger.info("shop_reward_send_start", user_id=session.user_id, reward_name=reward.name, image_credit_id=reward.image_credit_id)
    message = await send_captioned_image(
        context,
        chat_id=session.chat_id,
        message_thread_id=session.message_thread_id,
        caption=caption,
        image_credit_id=reward.image_credit_id,
        image_path=FALLBACK_IMAGE_PATH,
    )
    logger.info("shop_reward_send_done", user_id=session.user_id, reward_name=reward.name, image_credit_id=reward.image_credit_id)

    if shop_view is not None:
        reward_session_id = session_store.create_session(
            chat_id=session.chat_id,
            message_id=message.message_id,
            user_id=session.user_id,
            message_thread_id=session.message_thread_id,
        )
        logger.info("shop_reward_markup_start", user_id=session.user_id, reward_name=reward.name, reward_session_id=reward_session_id)
        await message.edit_reply_markup(reply_markup=_build_reward_continue_keyboard(shop_view, reward_session_id))
        logger.info("shop_reward_markup_done", user_id=session.user_id, reward_name=reward.name, reward_session_id=reward_session_id)
    return message


def _render_reward_caption(reward: PokemonReward, user_label: Optional[str] = None) -> str:
    return "\n".join(line for line in [
            f"🏆 <b>{reward.name}</b>",
            (f"Тренер: <b>{user_label}</b>" if user_label else ""),
            f"Редкость: <b>{reward.rarity}</b>",
            f"Тип: <b>{reward.pokemon_type or 'unknown'}</b>",
            f"HP: <b>{reward.base_hp}</b>",
            f"ATK: <b>{reward.base_attack}</b>",
            f"DEF: <b>{reward.base_defense}</b>",
            f"SPD: <b>{reward.base_stamina}</b>",
            f"ID экземпляра: <b>{reward.user_pokemon_id}</b>",
        ] if line
    )


async def _send_batch_summary(
    context: ContextTypes.DEFAULT_TYPE, session: MenuSession, spin_result: SpinResult
) -> None:
    summary_lines = ["🎰 <b>Результаты x5 крутки</b>", ""]
    for index, reward in enumerate(spin_result.rewards, start=1):
        summary_lines.append(f"{index}. <b>{reward.name}</b> — {reward.rarity}")
    summary_text = "\n".join(summary_lines)

    logger.info("shop_summary_send_start", user_id=session.user_id, rewards_count=len(spin_result.rewards))
    sent_message = await context.bot.send_message(
        chat_id=session.chat_id,
        message_thread_id=session.message_thread_id,
        text=summary_text,
        parse_mode="HTML",
    )
    logger.info("shop_summary_send_done", user_id=session.user_id, rewards_count=len(spin_result.rewards))
    summary_session_id = session_store.create_session(
        chat_id=session.chat_id,
        message_id=sent_message.message_id,
        user_id=session.user_id,
        message_thread_id=session.message_thread_id,
        data={"spin_results": [reward.as_session_payload() for reward in spin_result.rewards]},
    )
    logger.info("shop_summary_markup_start", user_id=session.user_id, summary_session_id=summary_session_id)
    await sent_message.edit_reply_markup(reply_markup=_build_summary_keyboard(summary_session_id))
    logger.info("shop_summary_markup_done", user_id=session.user_id, summary_session_id=summary_session_id)


def _build_summary_keyboard(session_id: str) -> InlineKeyboardMarkup:
    keyboard = [
        [
            InlineKeyboardButton(f"#{index}", callback_data=f"menu:shop_detail_{index}:{session_id}")
            for index in range(1, 6)
        ]
    ]
    return InlineKeyboardMarkup(keyboard)


async def _handle_spin_detail(
    update: Update, context: ContextTypes.DEFAULT_TYPE, session: MenuSession, section: str
) -> None:
    index = int(section.rsplit("_", maxsplit=1)[-1]) - 1
    rewards = session.data.get("spin_results")
    if not rewards or not isinstance(rewards, list) or index >= len(rewards):
        raise SummarySessionError("Spin result details are no longer available")
    reward = PokemonReward(
        user_pokemon_id=int(rewards[index]["user_pokemon_id"]),
        pokemon_id=int(rewards[index]["pokemon_id"]),
        name=str(rewards[index]["name"]),
        rarity=str(rewards[index]["rarity"]),
        pokemon_type=rewards[index].get("pokemon_type"),
        base_hp=int(rewards[index]["base_hp"]),
        base_attack=int(rewards[index]["base_attack"]),
        base_defense=int(rewards[index]["base_defense"]),
        base_stamina=int(rewards[index]["base_stamina"]),
        image_credit_id=rewards[index].get("image_credit_id"),
    )
    logger.info("shop_detail_send_start", user_id=session.user_id, reward_name=reward.name, index=index + 1)
    db = _get_db(context)
    shop_view = await db.get_shop_view(session.user_id, update.effective_user.username if update.effective_user else None) if db else None
    await _send_reward_card(context, session, reward, shop_view, _display_user(update))
    logger.info("shop_spin_detail_sent", user_id=session.user_id, reward_name=reward.name, index=index + 1)
