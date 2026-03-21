"""Shared non-shop pokemon card rendering helpers."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Message
from telegram.ext import ContextTypes

FALLBACK_IMAGE_PATH = Path("image.png")
MARKET_CARD_SECTION = "mce"
RELEASE_CARD_SECTION = "pkr"
EXTRA_CARD_SECTION = "pkm"


@dataclass(slots=True)
class PokemonCardData:
    """Shared read model for non-shop pokemon cards."""

    pokemon_id: int
    name: str
    rarity: str
    pokemon_type: Optional[str]
    base_hp: int
    base_attack: int
    base_defense: int
    base_stamina: int
    trainer_label: Optional[str] = None
    quantity: Optional[int] = None
    user_pokemon_id: Optional[int] = None
    extra_lines: tuple[str, ...] = ()


def render_pokemon_card_caption(card: PokemonCardData) -> str:
    """Render a compact pokemon card caption."""
    lines = [
        f"📘 <b>{card.name}</b>",
        (f"Тренер: <b>{card.trainer_label}</b>" if card.trainer_label else ""),
        f"Редкость: <b>{card.rarity}</b>",
        f"Тип: <b>{card.pokemon_type or 'unknown'}</b>",
        (f"Количество: <b>{card.quantity}</b>" if card.quantity is not None else ""),
        f"HP: <b>{card.base_hp}</b>",
        f"ATK: <b>{card.base_attack}</b>",
        f"DEF: <b>{card.base_defense}</b>",
        f"SPD: <b>{card.base_stamina}</b>",
        f"ID покемона: <b>{card.pokemon_id}</b>",
        (f"ID экземпляра: <b>{card.user_pokemon_id}</b>" if card.user_pokemon_id is not None else ""),
        *card.extra_lines,
    ]
    return "\n".join(line for line in lines if line)


async def send_pokemon_card(
    context: ContextTypes.DEFAULT_TYPE,
    *,
    chat_id: int,
    message_thread_id: Optional[int],
    card: PokemonCardData,
    reply_markup: Optional[InlineKeyboardMarkup] = None,
    image_path: Optional[Path] = None,
) -> Message:
    """Send a shared non-shop pokemon card as photo or text fallback."""
    caption = render_pokemon_card_caption(card)
    resolved_image = image_path or FALLBACK_IMAGE_PATH
    if resolved_image.exists():
        with resolved_image.open("rb") as image_file:
            return await context.bot.send_photo(
                chat_id=chat_id,
                message_thread_id=message_thread_id,
                photo=image_file,
                caption=caption,
                parse_mode="HTML",
                reply_markup=reply_markup,
            )
    return await context.bot.send_message(
        chat_id=chat_id,
        message_thread_id=message_thread_id,
        text=caption,
        parse_mode="HTML",
        reply_markup=reply_markup,
    )


def build_pokemon_card_keyboard(
    session_id: str,
    *,
    include_market_button: bool = False,
    include_release_button: bool = False,
    include_extra_button: bool = False,
) -> InlineKeyboardMarkup:
    """Build a shared keyboard for non-shop pokemon cards."""
    rows: list[list[InlineKeyboardButton]] = []
    if include_market_button:
        rows.append([InlineKeyboardButton("🏪 Рынок", callback_data=f"menu:{MARKET_CARD_SECTION}:{session_id}")])
    if include_release_button:
        rows.append([InlineKeyboardButton("🕊 Отпустить", callback_data=f"menu:{RELEASE_CARD_SECTION}:{session_id}")])
    if include_extra_button:
        rows.append([InlineKeyboardButton("⚙️ Дополнительно", callback_data=f"menu:{EXTRA_CARD_SECTION}:{session_id}")])
    return InlineKeyboardMarkup(rows)
