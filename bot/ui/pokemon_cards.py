"""Shared non-shop pokemon card rendering helpers."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from io import BytesIO
import os
from pathlib import Path
from types import SimpleNamespace
from typing import Optional
from urllib.parse import quote
from urllib.request import urlopen

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, InputMediaPhoto, Message
from telegram.ext import ContextTypes

from bot.ui.html import escape_html

FALLBACK_IMAGE_PATH = Path("image.png")
MARKET_CARD_SECTION = "mce"
RELEASE_CARD_SECTION = "pkr"
EXTRA_CARD_SECTION = "pkm"
TRADE_CARD_SECTION = "tca"
IMAGE_CARD_SECTION = "pki"
CARD_KIND_OWNED = "owned"
CARD_KIND_SEARCH = "search"


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
    dex_form_code: Optional[str] = None
    image_credit_id: Optional[int] = None
    image_variant_position: Optional[int] = None
    image_variant_total: Optional[int] = None
    form_badge: Optional[str] = None
    extra_lines: tuple[str, ...] = ()


def format_pokemon_display_name(name: str, form_badge: Optional[str]) -> str:
    """Build the player-facing pokemon name with optional form in parentheses."""
    normalized_name = name.strip()
    if not form_badge:
        return normalized_name
    return f"{normalized_name} ({form_badge.lower()})"


def format_pokemon_display_id(pokemon_id: int, dex_form_code: Optional[str]) -> str:
    """Build the player-facing id line for one pokemon."""
    if isinstance(dex_form_code, str) and dex_form_code.strip():
        return dex_form_code.strip().split("-", 1)[0]
    return str(pokemon_id)


def render_pokemon_card_caption(card: PokemonCardData) -> str:
    """Render a compact pokemon card caption."""
    lines = [
        f"📘 <b>{escape_html(format_pokemon_display_name(card.name, card.form_badge))}</b>",
        (f"Тренер: <b>{escape_html(card.trainer_label)}</b>" if card.trainer_label else ""),
        f"Редкость: <b>{escape_html(card.rarity)}</b>",
        f"Тип: <b>{escape_html(card.pokemon_type or 'unknown')}</b>",
        (f"Количество: <b>{card.quantity}</b>" if card.quantity is not None else ""),
        f"HP: <b>{card.base_hp}</b>",
        f"ATK: <b>{card.base_attack}</b>",
        f"DEF: <b>{card.base_defense}</b>",
        f"SPD: <b>{card.base_stamina}</b>",
        f"ID покемона: <b>{escape_html(format_pokemon_display_id(card.pokemon_id, card.dex_form_code))}</b>",
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
    storage_bucket = getattr(image_credit, "storage_bucket", None)
    object_key = getattr(image_credit, "object_key", None)
    if not isinstance(storage_bucket, str) or not isinstance(object_key, str):
        return None

    object_url = _build_object_url(storage_bucket, object_key)
    try:
        image_bytes = await asyncio.to_thread(_fetch_remote_bytes, object_url)
    except Exception:
        return None
    return image_bytes, Path(object_key).name or "pokemon-image"


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


async def edit_captioned_image(
    query,
    context: ContextTypes.DEFAULT_TYPE,
    *,
    caption: str,
    reply_markup: Optional[InlineKeyboardMarkup] = None,
    image_credit_id: Optional[int] = None,
    image_path: Optional[Path] = None,
) -> None:
    """Edit an existing image/text message with refreshed media when available."""
    message = getattr(query, "message", None)
    if getattr(message, "photo", None):
        if image_credit_id is not None:
            remote_image = await _fetch_image_bytes_from_storage(context, image_credit_id)
            if remote_image is not None:
                image_bytes, filename = remote_image
                file_obj = BytesIO(image_bytes)
                file_obj.name = filename
                await query.edit_message_media(
                    media=InputMediaPhoto(media=file_obj, caption=caption, parse_mode="HTML"),
                    reply_markup=reply_markup,
                )
                return

        resolved_image = image_path or FALLBACK_IMAGE_PATH
        if resolved_image.exists():
            with resolved_image.open("rb") as image_file:
                await query.edit_message_media(
                    media=InputMediaPhoto(media=image_file, caption=caption, parse_mode="HTML"),
                    reply_markup=reply_markup,
                )
                return

        await query.edit_message_caption(
            caption=caption,
            parse_mode="HTML",
            reply_markup=reply_markup,
        )
        return

    await query.edit_message_text(
        text=caption,
        parse_mode="HTML",
        reply_markup=reply_markup,
    )


async def edit_pokemon_card(
    query,
    context: ContextTypes.DEFAULT_TYPE,
    *,
    card: PokemonCardData,
    reply_markup: Optional[InlineKeyboardMarkup] = None,
    image_path: Optional[Path] = None,
) -> None:
    """Edit an existing shared non-shop pokemon card message."""
    await edit_captioned_image(
        query,
        context,
        caption=render_pokemon_card_caption(card),
        reply_markup=reply_markup,
        image_credit_id=card.image_credit_id,
        image_path=image_path,
    )


def build_image_switch_label(position: Optional[int], total: Optional[int]) -> Optional[str]:
    """Build the compact image-switch label for multi-art cards."""
    if not isinstance(position, int) or not isinstance(total, int) or position < 1 or total <= 1:
        return None
    return f"🖼 {position}/{total}"


def normalize_image_selection(image_selection) -> SimpleNamespace:
    """Coerce DB/mock image selection objects into a stable shape for card rendering."""
    image_credit_id = getattr(image_selection, "image_credit_id", None)
    source_url = getattr(image_selection, "source_url", None)
    position = getattr(image_selection, "position", 1)
    total = getattr(image_selection, "total", 1)
    if not isinstance(image_credit_id, int):
        image_credit_id = None
    if not isinstance(source_url, str):
        source_url = None
    if not isinstance(position, int) or position < 1:
        position = 1
    if not isinstance(total, int) or total < 1:
        total = 1
    return SimpleNamespace(
        image_credit_id=image_credit_id,
        source_url=source_url,
        position=position,
        total=total,
        can_switch=total > 1,
    )


def build_owned_card_session_payload(
    *,
    pokemon_id: int,
    user_pokemon_id: int,
    user_label: Optional[str],
    read_only: bool,
) -> dict[str, object]:
    """Serialize the minimum context needed to rebuild one owned/read-only card."""
    return {
        "card_kind": CARD_KIND_OWNED,
        "card_pokemon_id": pokemon_id,
        "card_user_pokemon_id": user_pokemon_id,
        "card_user_label": user_label,
        "card_read_only": read_only,
    }


def build_search_card_session_payload(
    *,
    pokemon_id: int,
    dex_form_code: Optional[str],
    name: str,
    rarity: str,
    form_badge: Optional[str],
    pokemon_type: Optional[str],
    base_hp: int,
    base_attack: int,
    base_defense: int,
    base_stamina: int,
    user_label: Optional[str],
) -> dict[str, object]:
    """Serialize catalog-card context so the card can be rebuilt after image switching."""
    return {
        "card_kind": CARD_KIND_SEARCH,
        "card_pokemon_id": pokemon_id,
        "card_dex_form_code": dex_form_code,
        "card_name": name,
        "card_rarity": rarity,
        "card_form_badge": form_badge,
        "card_pokemon_type": pokemon_type,
        "card_base_hp": base_hp,
        "card_base_attack": base_attack,
        "card_base_defense": base_defense,
        "card_base_stamina": base_stamina,
        "card_user_label": user_label,
    }


def build_pokemon_card_keyboard(
    session_id: str,
    *,
    image_switch_label: Optional[str] = None,
    include_market_button: bool = False,
    include_trade_button: bool = False,
    include_release_button: bool = False,
    include_extra_button: bool = False,
) -> InlineKeyboardMarkup:
    """Build a shared keyboard for non-shop pokemon cards."""
    rows: list[list[InlineKeyboardButton]] = []
    if image_switch_label:
        rows.append([InlineKeyboardButton(image_switch_label, callback_data=f"menu:{IMAGE_CARD_SECTION}:{session_id}")])
    if include_market_button:
        rows.append([InlineKeyboardButton("🏪 Рынок", callback_data=f"menu:{MARKET_CARD_SECTION}:{session_id}")])
    if include_trade_button:
        rows.append([InlineKeyboardButton("🤝 Добавить в обмен", callback_data=f"menu:{TRADE_CARD_SECTION}:{session_id}")])
    if include_release_button:
        rows.append([InlineKeyboardButton("🕊 Отпустить", callback_data=f"menu:{RELEASE_CARD_SECTION}:{session_id}")])
    if include_extra_button:
        rows.append([InlineKeyboardButton("⚙️ Дополнительно", callback_data=f"menu:{EXTRA_CARD_SECTION}:{session_id}")])
    return InlineKeyboardMarkup(rows)
