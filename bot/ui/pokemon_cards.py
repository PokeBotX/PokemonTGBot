"""Shared non-shop pokemon card rendering helpers."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from io import BytesIO
import os
from pathlib import Path
from typing import Optional
from urllib.parse import quote
from urllib.request import urlopen

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Message
from telegram.ext import ContextTypes

from bot.ui.html import escape_html

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
    image_credit_id: Optional[int] = None
    extra_lines: tuple[str, ...] = ()


def render_pokemon_card_caption(card: PokemonCardData) -> str:
    """Render a compact pokemon card caption."""
    lines = [
        f"📘 <b>{escape_html(card.name)}</b>",
        (f"Тренер: <b>{escape_html(card.trainer_label)}</b>" if card.trainer_label else ""),
        f"Редкость: <b>{escape_html(card.rarity)}</b>",
        f"Тип: <b>{escape_html(card.pokemon_type or 'unknown')}</b>",
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


def _storage_endpoint_url() -> str:
    return os.getenv("S3_ENDPOINT_URL", "http://127.0.0.1:9000").rstrip("/")


def _build_object_url(storage_bucket: str, object_key: str) -> str:
    quoted_key = quote(object_key, safe="/")
    return f"{_storage_endpoint_url()}/{storage_bucket}/{quoted_key}"


def _fetch_remote_bytes(url: str) -> bytes:
    with urlopen(url, timeout=10) as response:
        return response.read()


async def _fetch_image_bytes_from_storage(
    context: ContextTypes.DEFAULT_TYPE,
    image_credit_id: int,
) -> Optional[tuple[bytes, str]]:
    application = getattr(context, "application", None)
    bot_data = getattr(application, "bot_data", None) if application is not None else None
    if not isinstance(bot_data, dict):
        return None
    db = bot_data.get("db")
    if not db or not hasattr(db, "get_image_credit"):
        return None

    image_credit = await db.get_image_credit(image_credit_id)
    if not image_credit:
        return None

    object_url = _build_object_url(image_credit.storage_bucket, image_credit.object_key)
    try:
        image_bytes = await asyncio.to_thread(_fetch_remote_bytes, object_url)
    except Exception:
        return None
    return image_bytes, Path(image_credit.object_key).name or "pokemon-image"


async def send_captioned_image(
    context: ContextTypes.DEFAULT_TYPE,
    *,
    chat_id: int,
    message_thread_id: Optional[int],
    caption: str,
    reply_markup: Optional[InlineKeyboardMarkup] = None,
    image_credit_id: Optional[int] = None,
    image_path: Optional[Path] = None,
) -> Message:
    """Send a captioned image from object storage, explicit path, or fallback image."""
    if image_credit_id is not None:
        remote_image = await _fetch_image_bytes_from_storage(context, image_credit_id)
        if remote_image is not None:
            image_bytes, filename = remote_image
            file_obj = BytesIO(image_bytes)
            file_obj.name = filename
            return await context.bot.send_photo(
                chat_id=chat_id,
                message_thread_id=message_thread_id,
                photo=file_obj,
                caption=caption,
                parse_mode="HTML",
                reply_markup=reply_markup,
            )

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
    return await send_captioned_image(
        context,
        chat_id=chat_id,
        message_thread_id=message_thread_id,
        caption=caption,
        reply_markup=reply_markup,
        image_credit_id=card.image_credit_id,
        image_path=image_path,
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
