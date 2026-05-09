"""PokéCollect Bot - FastAPI application with Telegram webhook."""
import asyncio
import hashlib
import hmac
import json
import os
from datetime import UTC, datetime
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any
from urllib.parse import parse_qsl

import structlog
from dotenv import load_dotenv
from fastapi import Body, FastAPI, Header, HTTPException, Query, Request, Response, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from telegram import Update
from telegram.error import BadRequest
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters

from bot.db import Database
from bot.db.database import (
    MARKET_MAINTENANCE_INTERVAL_SECONDS,
    PVP_MAINTENANCE_INTERVAL_SECONDS,
    TRADE_MAINTENANCE_INTERVAL_SECONDS,
    CollectionFilterState,
    MarketBrowseState,
    ShopError,
    _pokemon_release_reward,
)
from bot.utils.logging import setup_logging
from bot.handlers.chat_activity import group_message_activity_handler
from bot.handlers.commands import (
    addteam_command,
    buyprice_command,
    changename_command,
    collection_command,
    find_command,
    fight_command,
    items_command,
    menu_command,
    pokemon_command,
    profile_command,
    search_command,
    section_command,
    sellprice_command,
    shop_command,
    start_command,
    trade_command,
    tradeadd_command,
    traderemove_command,
)
from bot.handlers.navigation import handle_callback_query
from bot.navigation.router import navigation_router

# Import section handlers
from bot.handlers.sections.shop import register_shop_routes
from bot.handlers.sections.market import register_market_routes
from bot.handlers.sections.profile import handle_profile_text_input, register_profile_routes
from bot.handlers.sections.pvp import register_pvp_routes, run_pvp_maintenance_job
from bot.handlers.sections.trade import register_trade_routes, run_trade_maintenance_job
from bot.handlers.sections.games import register_games_routes
from bot.handlers.sections.collection import register_collection_routes
from bot.handlers.sections.updates import updates_handler
from bot.handlers.sections.chat import chat_handler
from bot.handlers.sections.support import support_handler
from bot.handlers.sections.info import info_handler
from bot.handlers.sections.back import back_to_menu_handler
from bot.handlers.sections.chat_encounters import handle_encounter_callback
from bot.navigation.session import session_store

# Setup logging
setup_logging()
logger = structlog.get_logger()

# Load environment variables
load_dotenv()

# Configuration
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
WEBHOOK_URL = os.getenv("WEBHOOK_URL")  # Example: https://your-domain.com
WEBHOOK_PATH = os.getenv("WEBHOOK_PATH", "/webhook")
WEBHOOK_CERT_PATH = os.getenv("WEBHOOK_CERT_PATH")
HOST = os.getenv("HOST", "0.0.0.0")
PORT = int(os.getenv("PORT", "8000"))
DB_ENABLED = os.getenv("DB_ENABLED", "false").lower() == "true"
DB_INIT_SCHEMA = os.getenv("DB_INIT_SCHEMA", "false").lower() == "true"
DB_SCHEMA_PATH = os.getenv("DB_SCHEMA_PATH", "sql/schema.sql")
REDIS_ENABLED = os.getenv("REDIS_ENABLED", "false").lower() == "true"
REDIS_URL = os.getenv("REDIS_URL", "redis://127.0.0.1:6379/0")
SESSION_REDIS_ENABLED = os.getenv("SESSION_REDIS_ENABLED", "false").lower() == "true"
DROP_PENDING_UPDATES = os.getenv("WEBHOOK_DROP_PENDING_UPDATES", "false").lower() == "true"

if not TELEGRAM_BOT_TOKEN:
    raise ValueError("TELEGRAM_BOT_TOKEN not set in .env")
if not WEBHOOK_URL:
    raise ValueError("WEBHOOK_URL not set in .env")

GROUP_ACTIVITY_FILTER = (
    (filters.ChatType.GROUP | filters.ChatType.SUPERGROUP)
    & filters.TEXT
    & ~filters.COMMAND
)

# Global bot application
bot_app: Application = None
db: Database = None

MINI_APP_AUTH_MAX_AGE_SECONDS = 24 * 60 * 60
MINI_APP_COLLECTION_PAGE_SIZE = 24
MINI_APP_DEV_FALLBACK_ENABLED = os.getenv("MINI_APP_DEV_FALLBACK_ENABLED", "false").lower() == "true"
MINI_APP_DEV_FALLBACK_TELEGRAM_ID = int(os.getenv("MINI_APP_DEV_FALLBACK_TELEGRAM_ID", "1640978922"))
MINI_APP_DEV_FALLBACK_USERNAME = os.getenv("MINI_APP_DEV_FALLBACK_USERNAME", "termenater").strip() or "termenater"
MINI_APP_ALLOWED_ORIGINS = tuple(
    origin.strip()
    for origin in os.getenv(
        "MINI_APP_ALLOWED_ORIGINS",
        "http://127.0.0.1:3000,http://localhost:3000,https://app.pokemoncollection.ru,https://pokemoncollection.ru",
    ).split(",")
    if origin.strip()
)


class TelegramAuthRequest(BaseModel):
    """Request payload for Mini App Telegram auth handshake."""

    initData: str


class MiniAppMarketSellRequest(BaseModel):
    """Request payload for creating one Mini App market listing."""

    price: int


def _build_health_payload(*, db_connected: bool | None = None, redis_configured: bool | None = None) -> dict[str, object]:
    """Build an operational health payload for runtime dependencies."""
    bot_initialized = bot_app is not None
    if db_connected is None:
        db_connected = (not DB_ENABLED) or (db is not None and getattr(db, "pool", None) is not None)
    if redis_configured is None:
        redis_configured = (not REDIS_ENABLED) or (
            (db is not None and getattr(db, "redis", None) is not None)
            or (
                bot_app is not None
                and isinstance(getattr(bot_app, "bot_data", None), dict)
                and bool(bot_app.bot_data.get("redis_url"))
            )
        )
    return {
        "status": "healthy" if bot_initialized and db_connected and redis_configured else "degraded",
        "bot_initialized": bot_initialized,
        "db_enabled": DB_ENABLED,
        "db_connected": db_connected,
        "redis_enabled": REDIS_ENABLED,
        "redis_configured": redis_configured,
    }


def _health_status_code(payload: dict[str, object]) -> int:
    """Choose HTTP status code for the health response."""
    return status.HTTP_200_OK if payload["status"] == "healthy" else status.HTTP_503_SERVICE_UNAVAILABLE


def _telegram_webapp_secret_key(bot_token: str) -> bytes:
    """Derive the Telegram Mini App secret key from the bot token."""
    return hmac.new(b"WebAppData", bot_token.encode("utf-8"), hashlib.sha256).digest()


def _validate_telegram_init_data(init_data: str) -> dict[str, Any]:
    """Validate Telegram Mini App initData and return parsed payload."""
    normalized = (init_data or "").strip()
    if not normalized:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="initData is required",
        )

    parsed_pairs = dict(parse_qsl(normalized, keep_blank_values=True))
    received_hash = parsed_pairs.pop("hash", None)
    if not received_hash:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="initData hash is missing",
        )

    data_check_string = "\n".join(
        f"{key}={value}" for key, value in sorted(parsed_pairs.items())
    )
    expected_hash = hmac.new(
        _telegram_webapp_secret_key(TELEGRAM_BOT_TOKEN),
        data_check_string.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()

    if not hmac.compare_digest(expected_hash, received_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Telegram initData signature is invalid",
        )

    auth_date_raw = parsed_pairs.get("auth_date")
    if not auth_date_raw:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="auth_date is missing from initData",
        )

    try:
        auth_date = int(auth_date_raw)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="auth_date is invalid",
        ) from exc

    age_seconds = int(datetime.now(UTC).timestamp()) - auth_date
    if age_seconds > MINI_APP_AUTH_MAX_AGE_SECONDS:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Telegram initData is too old",
        )

    user_payload: dict[str, Any] | None = None
    user_raw = parsed_pairs.get("user")
    if user_raw:
        try:
            loaded_user = json.loads(user_raw)
        except json.JSONDecodeError as exc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Telegram user payload is invalid JSON",
            ) from exc
        if not isinstance(loaded_user, dict):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Telegram user payload must be an object",
            )
        user_payload = loaded_user

    return {
        "auth_date": auth_date,
        "query_id": parsed_pairs.get("query_id"),
        "user": user_payload,
        "raw": parsed_pairs,
    }


def _extract_mini_app_identity(telegram_payload: dict[str, Any]) -> tuple[int, str | None]:
    """Extract required user identity from validated Telegram payload."""
    user = telegram_payload.get("user")
    if not isinstance(user, dict):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Telegram user payload is missing",
        )

    telegram_id = user.get("id")
    if not isinstance(telegram_id, int):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Telegram user id is missing or invalid",
        )

    username = user.get("username")
    if username is not None and not isinstance(username, str):
        username = None

    return telegram_id, username


def _resolve_mini_app_identity(
    *,
    x_telegram_init_data: str | None,
    x_dev_telegram_id: str | None,
    request_host: str | None = None,
) -> tuple[int, str | None]:
    """Resolve Mini App identity from Telegram initData or a local dev fallback."""
    normalized_init_data = (x_telegram_init_data or "").strip()
    if normalized_init_data:
        telegram_payload = _validate_telegram_init_data(normalized_init_data)
        return _extract_mini_app_identity(telegram_payload)

    normalized_host = (request_host or "").split(":", 1)[0].strip().lower()
    is_local_request = normalized_host in {"localhost", "127.0.0.1"}
    if MINI_APP_DEV_FALLBACK_ENABLED and is_local_request:
        normalized_dev_id = (x_dev_telegram_id or "").strip()
        if normalized_dev_id and normalized_dev_id == str(MINI_APP_DEV_FALLBACK_TELEGRAM_ID):
            return MINI_APP_DEV_FALLBACK_TELEGRAM_ID, MINI_APP_DEV_FALLBACK_USERNAME

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Telegram initData is required",
    )


async def _build_mini_app_profile_payload(telegram_id: int, username: str | None) -> dict[str, Any]:
    """Build the current user's Mini App profile response from DB read models."""
    if not DB_ENABLED or db is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database is not available for Mini App profile requests",
        )

    profile_summary = await db.get_profile_summary(telegram_id, username)
    shop_view = await db.get_shop_view(telegram_id, username)

    display_name = (
        profile_summary.nickname
        or profile_summary.tg_username
        or "Тренер Pokémon"
    )
    cover_image_url = await _resolve_image_url(image_credit_id=profile_summary.profile_pic_credit_id)

    return {
        "id": profile_summary.user_id,
        "telegramId": profile_summary.telegram_id,
        "name": display_name,
        "username": profile_summary.tg_username or "",
        "pokemonCount": profile_summary.total_unique_owned,
        "coins": shop_view.balance,
        "language": profile_summary.language,
        "completionPercent": profile_summary.total_unique_percent,
        "totalCatalog": profile_summary.total_catalog,
        "baseDexCount": profile_summary.total_unique_owned,
        "baseDexCatalog": profile_summary.total_catalog,
        "baseDexCompletionPercent": profile_summary.total_unique_percent,
        "totalFormCount": profile_summary.total_form_owned,
        "totalFormCatalog": profile_summary.total_form_catalog,
        "totalFormCompletionPercent": profile_summary.total_form_percent,
        "accountAgeLabel": _humanize_account_age(profile_summary.created_at),
        "coverPokemonName": profile_summary.cover_pokemon_name,
        "coverPokemonImageUrl": cover_image_url,
        "rarityProgress": [
            {
                "rarity": progress.rarity,
                "ownedUnique": progress.owned_unique,
                "totalCatalog": progress.total_catalog,
                "percent": progress.percent,
            }
            for progress in profile_summary.rarity_progress
        ],
    }


async def _build_mini_app_collection_payload(telegram_id: int, username: str | None) -> dict[str, Any]:
    """Build the current user's Mini App collection response from DB read models."""
    return await _build_mini_app_collection_payload_with_filters(
        telegram_id,
        username,
        filter_state=CollectionFilterState(),
        page_size=MINI_APP_COLLECTION_PAGE_SIZE,
    )


def _storage_endpoint_url() -> str:
    return (
        os.getenv("S3_PUBLIC_BASE_URL")
        or os.getenv("S3_ENDPOINT_URL", "http://127.0.0.1:9000")
    ).rstrip("/")


def _build_object_url(storage_bucket: str, object_key: str) -> str:
    from urllib.parse import quote

    quoted_key = quote(object_key, safe="/")
    return f"{_storage_endpoint_url()}/{storage_bucket}/{quoted_key}"


async def _resolve_image_url(
    *,
    image_credit_id: int | None,
) -> str | None:
    if image_credit_id is None or db is None:
        return None

    image_credit = await db.get_image_credit(image_credit_id)
    if not image_credit:
        return None

    storage_bucket = getattr(image_credit, "storage_bucket", None)
    object_key = getattr(image_credit, "object_key", None)
    if not isinstance(storage_bucket, str) or not isinstance(object_key, str):
        return None
    return _build_object_url(storage_bucket, object_key)


async def _build_mini_app_collection_payload_with_filters(
    telegram_id: int,
    username: str | None,
    *,
    filter_state: CollectionFilterState,
    page_size: int,
) -> dict[str, Any]:
    """Build the current user's Mini App collection response with explicit filters."""
    if not DB_ENABLED or db is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database is not available for Mini App collection requests",
        )

    collection_page = await db.get_mini_app_collection_page(
        telegram_id,
        username,
        filter_state,
        page_size=page_size,
    )
    image_urls: list[str | None] = await asyncio.gather(
        *[
            _resolve_image_url(image_credit_id=entry.image_credit_id)
            for entry in collection_page.entries
        ]
    )
    return {
        "entries": [
            {
                "id": entry.pokemon_id,
                "dexFormCode": entry.dex_form_code,
                "userPokemonId": entry.sample_user_pokemon_id,
                "name": entry.name,
                "type": entry.pokemon_type or "Unknown",
                "level": 1,
                "rarity": entry.rarity,
                "formBadge": entry.form_badge,
                "quantity": entry.quantity,
                "baseHp": entry.base_hp,
                "baseAttack": entry.base_attack,
                "baseDefense": entry.base_defense,
                "baseStamina": entry.base_stamina,
                "imageCreditId": entry.image_credit_id,
                "imageUrl": image_urls[index],
                "isLocked": entry.is_locked,
            }
            for index, entry in enumerate(collection_page.entries)
        ],
        "pageInfo": {
            "totalEntries": collection_page.total_entries,
            "currentPage": collection_page.current_page,
            "totalPages": collection_page.total_pages,
            "pageSize": collection_page.page_size,
            "hasNext": collection_page.has_next(),
            "hasPrevious": collection_page.has_previous(),
            "nextPage": collection_page.current_page + 1 if collection_page.has_next() else None,
        },
        "appliedFilters": {
            "rarities": list(collection_page.filter_state.rarities),
            "types": list(collection_page.filter_state.types),
            "duplicatesOnly": collection_page.filter_state.duplicates_only,
            "lockedOnly": collection_page.filter_state.locked_only,
        },
    }


async def _build_mini_app_market_payload(
    telegram_id: int,
    username: str | None,
    *,
    page: int,
) -> dict[str, Any]:
    """Build the current market browse response for Mini App."""
    if not DB_ENABLED or db is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database is not available for Mini App market requests",
        )

    market_page = await db.get_market_listings_page(
        telegram_id,
        username,
        filter_state=MarketBrowseState(page=page),
    )

    image_urls: list[str | None] = await asyncio.gather(
        *[
            _resolve_image_url(image_credit_id=entry.image_credit_id)
            for entry in market_page.entries
        ]
    )
    return {
        "pokecoinBalance": market_page.current_balance,
        "entries": [
            {
                "listingId": entry.listing_id,
                "pokemonId": entry.pokemon_id,
                "dexFormCode": entry.dex_form_code,
                "userPokemonId": entry.user_pokemon_id,
                "name": entry.name,
                "type": entry.pokemon_type or "Unknown",
                "rarity": entry.rarity,
                "formBadge": entry.form_badge,
                "price": entry.price,
                "sellerLabel": entry.seller_label or "Тренер",
                "daysRemaining": entry.days_remaining,
                "imageCreditId": entry.image_credit_id,
                "imageUrl": image_urls[index],
            }
            for index, entry in enumerate(market_page.entries)
        ],
        "pageInfo": {
            "totalEntries": market_page.total_entries,
            "currentPage": market_page.current_page,
            "totalPages": market_page.total_pages,
            "pageSize": 20,
            "hasNext": market_page.has_next(),
            "hasPrevious": market_page.has_previous(),
            "nextPage": market_page.current_page + 1 if market_page.has_next() else None,
        },
    }


async def _build_mini_app_my_market_listings_payload(
    telegram_id: int,
    username: str | None,
) -> dict[str, Any]:
    """Build the current user's active market listings for Mini App."""
    if not DB_ENABLED or db is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database is not available for Mini App market requests",
        )

    listings = await db.get_my_market_listings(telegram_id, username)
    shop_view = await db.get_shop_view(telegram_id, username)
    image_urls: list[str | None] = await asyncio.gather(
        *[_resolve_image_url(image_credit_id=entry.image_credit_id) for entry in listings]
    )
    return {
        "pokecoinBalance": shop_view.pokecoin_balance,
        "entries": [
            {
                "listingId": entry.listing_id,
                "pokemonId": entry.pokemon_id,
                "dexFormCode": entry.dex_form_code,
                "userPokemonId": entry.user_pokemon_id,
                "name": entry.name,
                "type": entry.pokemon_type or "Unknown",
                "rarity": entry.rarity,
                "formBadge": entry.form_badge,
                "price": entry.price,
                "sellerLabel": entry.seller_label or "Тренер",
                "daysRemaining": entry.days_remaining,
                "imageCreditId": entry.image_credit_id,
                "imageUrl": image_urls[index],
            }
            for index, entry in enumerate(listings)
        ],
    }


async def _build_mini_app_my_market_requests_payload(
    telegram_id: int,
    username: str | None,
) -> dict[str, Any]:
    """Build the current user's active market buy requests for Mini App."""
    if not DB_ENABLED or db is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database is not available for Mini App market requests",
        )

    requests = await db.get_my_market_buy_requests(telegram_id, username)
    shop_view = await db.get_shop_view(telegram_id, username)
    image_urls: list[str | None] = await asyncio.gather(
        *[_resolve_image_url(image_credit_id=entry.image_credit_id) for entry in requests]
    )
    return {
        "pokecoinBalance": shop_view.pokecoin_balance,
        "entries": [
            {
                "requestId": entry.request_id,
                "pokemonId": entry.pokemon_id,
                "dexFormCode": entry.dex_form_code,
                "name": entry.name,
                "type": entry.pokemon_type or "Unknown",
                "rarity": entry.rarity,
                "formBadge": entry.form_badge,
                "price": entry.price,
                "reservedAmount": entry.reserved_amount,
                "requesterLabel": entry.requester_label or "Тренер",
                "imageCreditId": entry.image_credit_id,
                "imageUrl": image_urls[index],
            }
            for index, entry in enumerate(requests)
        ],
    }


async def _build_mini_app_market_listing_detail_payload(
    telegram_id: int,
    username: str | None,
    *,
    listing_id: int,
) -> dict[str, Any]:
    """Build one active market listing detail payload for Mini App."""
    if not DB_ENABLED or db is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database is not available for Mini App market requests",
        )

    try:
        listing = await db.get_market_listing_summary(
            telegram_id,
            username,
            listing_id=listing_id,
        )
        pokemon = await db.get_pokemon_catalog_entry_by_id(listing.pokemon_id)
        image_selection = await db.get_pokemon_image_selection(
            telegram_id,
            username,
            pokemon_id=listing.pokemon_id,
        )
    except ShopError as exc:
        detail = str(exc)
        status_code = status.HTTP_404_NOT_FOUND if "не найден" in detail.lower() or "недоступ" in detail.lower() else status.HTTP_400_BAD_REQUEST
        raise HTTPException(status_code=status_code, detail=detail) from exc

    shop_view = await db.get_shop_view(telegram_id, username)
    active_image_credit_id = image_selection.image_credit_id or pokemon.image_credit_id
    image_url = await _resolve_image_url(image_credit_id=active_image_credit_id)

    return {
        "listingId": listing.listing_id,
        "pokecoinBalance": shop_view.pokecoin_balance,
        "userPokemonId": listing.user_pokemon_id,
        "pokemonId": listing.pokemon_id,
        "dexFormCode": pokemon.dex_form_code,
        "name": listing.name,
        "rarity": listing.rarity,
        "formBadge": pokemon.form_badge,
        "type": listing.pokemon_type or "Unknown",
        "price": listing.price,
        "sellerLabel": listing.seller_label or "Тренер",
        "daysRemaining": listing.days_remaining,
        "baseHp": pokemon.base_hp,
        "baseAttack": pokemon.base_attack,
        "baseDefense": pokemon.base_defense,
        "baseStamina": pokemon.base_stamina,
        "imageCreditId": active_image_credit_id,
        "imageUrl": image_url,
        "sourceUrl": image_selection.source_url,
        "imageVariant": {
            "position": image_selection.position,
            "total": image_selection.total,
            "canSwitch": image_selection.total > 1,
        },
    }


async def _build_mini_app_my_market_listing_detail_payload(
    telegram_id: int,
    username: str | None,
    *,
    listing_id: int,
) -> dict[str, Any]:
    """Build one active owned market listing detail payload for Mini App."""
    if not DB_ENABLED or db is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database is not available for Mini App market requests",
        )

    try:
        listing = await db.get_my_market_listing_summary(
            telegram_id,
            username,
            listing_id=listing_id,
        )
        pokemon = await db.get_pokemon_catalog_entry_by_id(listing.pokemon_id)
        image_selection = await db.get_pokemon_image_selection(
            telegram_id,
            username,
            pokemon_id=listing.pokemon_id,
        )
        shop_view = await db.get_shop_view(telegram_id, username)
    except ShopError as exc:
        detail = str(exc)
        status_code = status.HTTP_404_NOT_FOUND if "не найден" in detail.lower() else status.HTTP_400_BAD_REQUEST
        raise HTTPException(status_code=status_code, detail=detail) from exc

    active_image_credit_id = image_selection.image_credit_id or pokemon.image_credit_id
    image_url = await _resolve_image_url(image_credit_id=active_image_credit_id)

    return {
        "listingId": listing.listing_id,
        "pokecoinBalance": shop_view.pokecoin_balance,
        "userPokemonId": listing.user_pokemon_id,
        "pokemonId": listing.pokemon_id,
        "dexFormCode": pokemon.dex_form_code,
        "name": listing.name,
        "rarity": listing.rarity,
        "formBadge": pokemon.form_badge,
        "type": listing.pokemon_type or "Unknown",
        "price": listing.price,
        "sellerLabel": listing.seller_label or "Тренер",
        "daysRemaining": listing.days_remaining,
        "baseHp": pokemon.base_hp,
        "baseAttack": pokemon.base_attack,
        "baseDefense": pokemon.base_defense,
        "baseStamina": pokemon.base_stamina,
        "imageCreditId": active_image_credit_id,
        "imageUrl": image_url,
        "sourceUrl": image_selection.source_url,
        "imageVariant": {
            "position": image_selection.position,
            "total": image_selection.total,
            "canSwitch": image_selection.total > 1,
        },
    }


async def _build_mini_app_market_request_detail_payload(
    telegram_id: int,
    username: str | None,
    *,
    request_id: int,
) -> dict[str, Any]:
    """Build one active owned market buy-request detail payload for Mini App."""
    if not DB_ENABLED or db is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database is not available for Mini App market requests",
        )

    try:
        market_request = await db.get_my_market_buy_request_summary(
            telegram_id,
            username,
            request_id=request_id,
        )
        pokemon = await db.get_pokemon_catalog_entry_by_id(market_request.pokemon_id)
        image_selection = await db.get_pokemon_image_selection(
            telegram_id,
            username,
            pokemon_id=market_request.pokemon_id,
        )
        shop_view = await db.get_shop_view(telegram_id, username)
    except ShopError as exc:
        detail = str(exc)
        status_code = status.HTTP_404_NOT_FOUND if "не найден" in detail.lower() else status.HTTP_400_BAD_REQUEST
        raise HTTPException(status_code=status_code, detail=detail) from exc

    active_image_credit_id = image_selection.image_credit_id or pokemon.image_credit_id
    image_url = await _resolve_image_url(image_credit_id=active_image_credit_id)

    return {
        "requestId": market_request.request_id,
        "pokecoinBalance": shop_view.pokecoin_balance,
        "pokemonId": market_request.pokemon_id,
        "dexFormCode": pokemon.dex_form_code,
        "name": market_request.name,
        "rarity": market_request.rarity,
        "formBadge": pokemon.form_badge,
        "type": market_request.pokemon_type or "Unknown",
        "price": market_request.price,
        "reservedAmount": market_request.reserved_amount,
        "requesterLabel": market_request.requester_label or "Тренер",
        "baseHp": pokemon.base_hp,
        "baseAttack": pokemon.base_attack,
        "baseDefense": pokemon.base_defense,
        "baseStamina": pokemon.base_stamina,
        "imageCreditId": active_image_credit_id,
        "imageUrl": image_url,
        "sourceUrl": image_selection.source_url,
        "imageVariant": {
            "position": image_selection.position,
            "total": image_selection.total,
            "canSwitch": image_selection.total > 1,
        },
    }


async def _build_mini_app_pokemon_detail_payload(
    telegram_id: int,
    username: str | None,
    *,
    user_pokemon_id: int,
) -> dict[str, Any]:
    """Build one owned pokemon detail payload for Mini App."""
    if not DB_ENABLED or db is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database is not available for Mini App pokemon requests",
        )

    entry = await db.get_owned_user_pokemon_entry(
        telegram_id,
        username,
        user_pokemon_id=user_pokemon_id,
    )
    if entry is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Pokemon not found",
        )

    image_selection = await db.get_pokemon_image_selection(
        telegram_id,
        username,
        pokemon_id=entry.pokemon_id,
    )
    is_in_pvp_team = await db.is_user_pokemon_in_pvp_team(
        telegram_id,
        username,
        user_pokemon_id=user_pokemon_id,
    )
    active_image_credit_id = image_selection.image_credit_id or entry.image_credit_id
    image_url = await _resolve_image_url(image_credit_id=active_image_credit_id)

    return {
        "id": entry.pokemon_id,
        "dexFormCode": entry.dex_form_code,
        "userPokemonId": entry.sample_user_pokemon_id,
        "name": entry.name,
        "rarity": entry.rarity,
        "formBadge": entry.form_badge,
        "type": entry.pokemon_type or "Unknown",
        "quantity": entry.quantity,
        "baseHp": entry.base_hp,
        "baseAttack": entry.base_attack,
        "baseDefense": entry.base_defense,
        "baseStamina": entry.base_stamina,
        "isLocked": entry.is_locked,
        "isInPvpTeam": is_in_pvp_team,
        "releaseRewardAmount": _pokemon_release_reward(entry.rarity),
        "imageCreditId": active_image_credit_id,
        "imageUrl": image_url,
        "sourceUrl": image_selection.source_url,
        "imageVariant": {
            "position": image_selection.position,
            "total": image_selection.total,
            "canSwitch": bool(image_selection.total > 1),
        },
    }


async def _build_mini_app_pokemon_instances_payload(
    telegram_id: int,
    username: str | None,
    *,
    user_pokemon_id: int,
) -> dict[str, Any]:
    """Build same-species owned instances payload for one current user pokemon."""
    if not DB_ENABLED or db is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database is not available for Mini App pokemon requests",
        )

    entry = await db.get_owned_user_pokemon_entry(
        telegram_id,
        username,
        user_pokemon_id=user_pokemon_id,
    )
    if entry is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Pokemon not found",
        )

    instances = await db.get_user_pokemon_instances_for_species(
        telegram_id,
        username,
        pokemon_id=entry.pokemon_id,
        limit=24,
    )
    team_flags = await asyncio.gather(
        *[
            db.is_user_pokemon_in_pvp_team(
                telegram_id,
                username,
                user_pokemon_id=instance.sample_user_pokemon_id,
            )
            for instance in instances
        ]
    )
    return {
        "entries": [
            {
                "userPokemonId": instance.sample_user_pokemon_id,
                "pokemonId": instance.pokemon_id,
                "dexFormCode": instance.dex_form_code,
                "name": instance.name,
                "rarity": instance.rarity,
                "type": instance.pokemon_type or "Unknown",
                "formBadge": instance.form_badge,
                "isLocked": instance.is_locked,
                "isInPvpTeam": team_flags[index],
            }
            for index, instance in enumerate(instances)
        ],
    }


def _parse_csv_query_values(values: list[str] | None) -> tuple[str, ...]:
    if not values:
        return ()

    parsed: list[str] = []
    for raw_value in values:
        for part in raw_value.split(","):
            normalized = part.strip()
            if normalized:
                parsed.append(normalized)
    return tuple(parsed)


def _pluralize_ru(value: int, singular: str, paucal: str, plural: str) -> str:
    remainder_100 = value % 100
    remainder_10 = value % 10
    if 11 <= remainder_100 <= 14:
        return plural
    if remainder_10 == 1:
        return singular
    if 2 <= remainder_10 <= 4:
        return paucal
    return plural


def _humanize_account_age(created_at: datetime) -> str:
    now = datetime.now(UTC)
    delta_days = max(0, (now - created_at.astimezone(UTC)).days)
    if delta_days < 30:
        return f"{delta_days} {_pluralize_ru(delta_days, 'день', 'дня', 'дней')}"

    months = delta_days // 30
    if months < 12:
        return f"{months} {_pluralize_ru(months, 'месяц', 'месяца', 'месяцев')}"

    years = months // 12
    return f"{years} {_pluralize_ru(years, 'год', 'года', 'лет')}"


async def run_market_maintenance_job(context) -> None:
    """Charge due commissions and expire market listings in the background."""
    application = getattr(context, "application", None)
    bot_data = getattr(application, "bot_data", {}) if application else {}
    market_db = bot_data.get("db") if isinstance(bot_data, dict) else None
    if not market_db:
        return

    stats = await market_db.process_market_listing_maintenance()
    if any(stats.values()):
        logger.info("market_maintenance_cycle", **stats)


def register_routes() -> None:
    """Register all section handlers with navigation router."""
    register_shop_routes(navigation_router)
    register_collection_routes(navigation_router)
    register_profile_routes(navigation_router)
    register_market_routes(navigation_router)
    register_trade_routes(navigation_router)
    register_pvp_routes(navigation_router)
    register_games_routes(navigation_router)
    navigation_router.register("updates", updates_handler)
    navigation_router.register("chat", chat_handler)
    navigation_router.register("support", support_handler)
    navigation_router.register("info", info_handler)
    navigation_router.register("back", back_to_menu_handler)
    
    logger.debug("routes_registered", routes=navigation_router.list_routes())


async def setup_bot_commands(application: Application) -> None:
    """Set up bot commands for the menu."""
    from telegram import BotCommand
    
    commands = [
        BotCommand("menu", "Открыть главное меню"),
        BotCommand("shop", "Открыть магазин"),
        BotCommand("market", "Открыть рынок"),
        BotCommand("profile", "Открыть профиль"),
        BotCommand("collection", "Открыть коллекцию"),
        BotCommand("find", "Поиск покемона в чате"),
        BotCommand("fight", "Вызвать игрока на бой"),
        BotCommand("search", "Поиск покемона по имени"),
        BotCommand("trade", "Создать обмен в чате"),
        BotCommand("info", "Открыть информацию"),
    ]
    
    await application.bot.set_my_commands(commands)
    logger.info("bot_commands_registered", commands=[c.command for c in commands])


async def setup_webhook() -> None:
    """Set up webhook for Telegram bot."""
    webhook_full_url = f"{WEBHOOK_URL}{WEBHOOK_PATH}"
    webhook_kwargs = {
        "url": webhook_full_url,
        "allowed_updates": ["message", "callback_query"],
        "drop_pending_updates": DROP_PENDING_UPDATES,
    }

    if WEBHOOK_CERT_PATH:
        cert_path = Path(WEBHOOK_CERT_PATH)
        if not cert_path.exists():
            raise ValueError(f"WEBHOOK_CERT_PATH does not exist: {cert_path}")
        webhook_kwargs["certificate"] = cert_path.open("rb")
    
    try:
        for attempt in range(1, 4):
            try:
                await bot_app.bot.set_webhook(**webhook_kwargs)
                break
            except BadRequest as exc:
                message = str(exc).lower()
                is_dns_failure = "failed to resolve host" in message
                if not is_dns_failure or attempt == 3:
                    if is_dns_failure:
                        existing_webhook = await bot_app.bot.get_webhook_info()
                        if existing_webhook.url == webhook_full_url:
                            logger.warning(
                                "webhook_reuse_existing",
                                url=existing_webhook.url,
                                attempt=attempt,
                                error=str(exc),
                            )
                            return
                    raise
                logger.warning(
                    "webhook_set_retry",
                    attempt=attempt,
                    url=webhook_full_url,
                    error=str(exc),
                )
                await asyncio.sleep(attempt)
    finally:
        certificate = webhook_kwargs.get("certificate")
        if certificate:
            certificate.close()
    
    webhook_info = await bot_app.bot.get_webhook_info()
    logger.info(
        "webhook_configured",
        url=webhook_info.url,
        has_custom_certificate=webhook_info.has_custom_certificate,
        pending_update_count=webhook_info.pending_update_count,
        webhook_cert_path=WEBHOOK_CERT_PATH,
        drop_pending_updates=DROP_PENDING_UPDATES,
    )


@asynccontextmanager
async def lifespan(app: FastAPI):
    """FastAPI lifespan context manager."""
    global bot_app, db
    
    logger.info("bot_starting")
    logger.info(
        "startup_config",
        mode="webhook",
        db_enabled=DB_ENABLED,
        redis_enabled=REDIS_ENABLED,
        session_redis_enabled=SESSION_REDIS_ENABLED,
        drop_pending_updates=DROP_PENDING_UPDATES,
        db_init_schema=DB_INIT_SCHEMA,
    )
    
    # Register navigation routes
    register_routes()
    
    # Create Telegram application
    bot_app = Application.builder().token(TELEGRAM_BOT_TOKEN).build()
    
    # Register command handlers
    bot_app.add_handler(CommandHandler("start", start_command))
    bot_app.add_handler(CommandHandler("menu", menu_command))
    bot_app.add_handler(CommandHandler("shop", shop_command))
    bot_app.add_handler(CommandHandler("pokemon", pokemon_command))
    bot_app.add_handler(CommandHandler("items", items_command))
    bot_app.add_handler(CommandHandler("find", find_command))
    bot_app.add_handler(CommandHandler("fight", fight_command))
    bot_app.add_handler(CommandHandler("addteam", addteam_command))
    bot_app.add_handler(CommandHandler("search", search_command))
    bot_app.add_handler(CommandHandler("trade", trade_command))
    bot_app.add_handler(CommandHandler("tradeadd", tradeadd_command))
    bot_app.add_handler(CommandHandler("traderemove", traderemove_command))
    bot_app.add_handler(CommandHandler("changename", changename_command))
    bot_app.add_handler(CommandHandler("sellprice", sellprice_command))
    bot_app.add_handler(CommandHandler("buyprice", buyprice_command))
    bot_app.add_handler(CommandHandler("collection", collection_command))
    bot_app.add_handler(CommandHandler("profile", profile_command))
    bot_app.add_handler(CommandHandler(["market", "games", "updates", "chat", "support", "info"], section_command))
    
    # Register callback query handler
    bot_app.add_handler(CallbackQueryHandler(handle_encounter_callback, pattern=r"^enc:"))
    bot_app.add_handler(CallbackQueryHandler(handle_callback_query))
    bot_app.add_handler(MessageHandler(filters.ChatType.PRIVATE & filters.TEXT & ~filters.COMMAND, handle_profile_text_input))
    bot_app.add_handler(
        MessageHandler(
            GROUP_ACTIVITY_FILTER,
            group_message_activity_handler,
        )
    )
    
    logger.info("handlers_registered")
    
    # Initialize bot application
    await bot_app.initialize()
    await bot_app.start()

    # Initialize database (optional)
    session_store.disable_redis()
    if REDIS_ENABLED and SESSION_REDIS_ENABLED:
        await session_store.configure_redis_async(REDIS_URL)
        bot_app.bot_data["redis_url"] = REDIS_URL
        logger.info("redis_ready", redis_url=REDIS_URL, mode="session_store")

    if DB_ENABLED:
        db = Database()
        await db.connect()
        if DB_INIT_SCHEMA:
            await db.init_schema(DB_SCHEMA_PATH)
        bot_app.bot_data["db"] = db
        if getattr(db, "redis", None) is not None:
            bot_app.bot_data["redis_url"] = REDIS_URL
        maintenance_stats = await db.process_market_listing_maintenance()
        if any(maintenance_stats.values()):
            logger.info("market_maintenance_cycle", **maintenance_stats)
        logger.info("db_ready", schema_init=DB_INIT_SCHEMA)
        if bot_app.job_queue:
            bot_app.job_queue.run_repeating(
                run_market_maintenance_job,
                interval=MARKET_MAINTENANCE_INTERVAL_SECONDS,
                first=MARKET_MAINTENANCE_INTERVAL_SECONDS,
                name="market-maintenance",
            )
            bot_app.job_queue.run_repeating(
                run_trade_maintenance_job,
                interval=TRADE_MAINTENANCE_INTERVAL_SECONDS,
                first=TRADE_MAINTENANCE_INTERVAL_SECONDS,
                name="trade-maintenance",
            )
            bot_app.job_queue.run_repeating(
                run_pvp_maintenance_job,
                interval=PVP_MAINTENANCE_INTERVAL_SECONDS,
                first=PVP_MAINTENANCE_INTERVAL_SECONDS,
                name="pvp-maintenance",
            )
    logger.info("runtime_dependency_state", **_build_health_payload())
    
    # Set up bot commands
    await setup_bot_commands(bot_app)
    
    # Set up webhook
    await setup_webhook()
    
    logger.info("bot_started", mode="webhook", port=PORT)
    
    yield
    
    # Shutdown
    logger.info("bot_shutting_down")
    if db:
        await db.close()
    await session_store.disable_redis_async()
    await bot_app.stop()
    await bot_app.shutdown()


# Create FastAPI application
app = FastAPI(title="PokéCollect Bot", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=list(MINI_APP_ALLOWED_ORIGINS),
    allow_credentials=False,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
)


@app.get("/")
async def root():
    """Basic root endpoint."""
    return {"status": "ok", "bot": "PokéCollect", "docs": "/docs", "health": "/health"}


@app.get("/health")
async def health():
    """Operational health check for bot runtime and backing services."""
    db_connected = not DB_ENABLED
    redis_configured = not REDIS_ENABLED
    if DB_ENABLED and db is not None:
        probe = await db.probe()
        db_connected = probe["db_ok"]
        redis_configured = probe["redis_ok"] if REDIS_ENABLED else True
    payload = _build_health_payload(
        db_connected=db_connected,
        redis_configured=redis_configured,
    )
    return JSONResponse(status_code=_health_status_code(payload), content=payload)


@app.post("/auth/telegram")
async def telegram_mini_app_auth(payload: TelegramAuthRequest):
    """Validate Telegram Mini App initData and return the authenticated user snapshot."""
    telegram_payload = _validate_telegram_init_data(payload.initData)
    telegram_id, username = _extract_mini_app_identity(telegram_payload)

    profile_payload: dict[str, Any] | None = None
    if DB_ENABLED and db is not None:
        profile_payload = await _build_mini_app_profile_payload(telegram_id, username)

    return {
        "authenticated": True,
        "authDate": telegram_payload["auth_date"],
        "telegramUser": telegram_payload["user"],
        "profile": profile_payload,
    }


@app.get("/api/me")
async def mini_app_me(
    request: Request,
    x_telegram_init_data: str | None = Header(default=None, alias="X-Telegram-Init-Data"),
    x_dev_telegram_id: str | None = Header(default=None, alias="X-Dev-Telegram-Id"),
):
    """Return the current Mini App profile using validated Telegram initData."""
    telegram_id, username = _resolve_mini_app_identity(
        x_telegram_init_data=x_telegram_init_data,
        x_dev_telegram_id=x_dev_telegram_id,
        request_host=request.headers.get("host"),
    )
    return await _build_mini_app_profile_payload(telegram_id, username)


@app.get("/api/collection")
async def mini_app_collection(
    request: Request,
    x_telegram_init_data: str | None = Header(default=None, alias="X-Telegram-Init-Data"),
    x_dev_telegram_id: str | None = Header(default=None, alias="X-Dev-Telegram-Id"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=MINI_APP_COLLECTION_PAGE_SIZE, ge=1, le=100),
    locked: bool = Query(default=False),
    duplicates_only: bool = Query(default=False),
    rarities: list[str] | None = Query(default=None),
    types: list[str] | None = Query(default=None),
):
    """Return the current Mini App collection using validated Telegram initData."""
    telegram_id, username = _resolve_mini_app_identity(
        x_telegram_init_data=x_telegram_init_data,
        x_dev_telegram_id=x_dev_telegram_id,
        request_host=request.headers.get("host"),
    )
    filter_state = CollectionFilterState(
        rarities=_parse_csv_query_values(rarities),
        types=_parse_csv_query_values(types),
        duplicates_only=duplicates_only,
        locked_only=locked,
        page=page,
    )
    return await _build_mini_app_collection_payload_with_filters(
        telegram_id,
        username,
        filter_state=filter_state,
        page_size=page_size,
    )


@app.get("/api/market")
async def mini_app_market(
    request: Request,
    x_telegram_init_data: str | None = Header(default=None, alias="X-Telegram-Init-Data"),
    x_dev_telegram_id: str | None = Header(default=None, alias="X-Dev-Telegram-Id"),
    page: int = Query(default=1, ge=1),
):
    """Return active market listings for Mini App browsing."""
    telegram_id, username = _resolve_mini_app_identity(
        x_telegram_init_data=x_telegram_init_data,
        x_dev_telegram_id=x_dev_telegram_id,
        request_host=request.headers.get("host"),
    )
    return await _build_mini_app_market_payload(
        telegram_id,
        username,
        page=page,
    )


@app.get("/api/market/{listing_id}")
async def mini_app_market_detail(
    listing_id: int,
    request: Request,
    x_telegram_init_data: str | None = Header(default=None, alias="X-Telegram-Init-Data"),
    x_dev_telegram_id: str | None = Header(default=None, alias="X-Dev-Telegram-Id"),
):
    """Return one active market listing detail payload for Mini App."""
    telegram_id, username = _resolve_mini_app_identity(
        x_telegram_init_data=x_telegram_init_data,
        x_dev_telegram_id=x_dev_telegram_id,
        request_host=request.headers.get("host"),
    )
    return await _build_mini_app_market_listing_detail_payload(
        telegram_id,
        username,
        listing_id=listing_id,
    )


@app.get("/api/market/my/listings")
async def mini_app_my_market_listings(
    request: Request,
    x_telegram_init_data: str | None = Header(default=None, alias="X-Telegram-Init-Data"),
    x_dev_telegram_id: str | None = Header(default=None, alias="X-Dev-Telegram-Id"),
):
    """Return active market listings created by the current Mini App user."""
    telegram_id, username = _resolve_mini_app_identity(
        x_telegram_init_data=x_telegram_init_data,
        x_dev_telegram_id=x_dev_telegram_id,
        request_host=request.headers.get("host"),
    )
    return await _build_mini_app_my_market_listings_payload(
        telegram_id,
        username,
    )


@app.get("/api/market/my/listings/{listing_id}")
async def mini_app_my_market_listing_detail(
    listing_id: int,
    request: Request,
    x_telegram_init_data: str | None = Header(default=None, alias="X-Telegram-Init-Data"),
    x_dev_telegram_id: str | None = Header(default=None, alias="X-Dev-Telegram-Id"),
):
    """Return one owned active market listing detail payload for Mini App."""
    telegram_id, username = _resolve_mini_app_identity(
        x_telegram_init_data=x_telegram_init_data,
        x_dev_telegram_id=x_dev_telegram_id,
        request_host=request.headers.get("host"),
    )
    return await _build_mini_app_my_market_listing_detail_payload(
        telegram_id,
        username,
        listing_id=listing_id,
    )


@app.get("/api/market/my/requests")
async def mini_app_my_market_requests(
    request: Request,
    x_telegram_init_data: str | None = Header(default=None, alias="X-Telegram-Init-Data"),
    x_dev_telegram_id: str | None = Header(default=None, alias="X-Dev-Telegram-Id"),
):
    """Return active market buy requests created by the current Mini App user."""
    telegram_id, username = _resolve_mini_app_identity(
        x_telegram_init_data=x_telegram_init_data,
        x_dev_telegram_id=x_dev_telegram_id,
        request_host=request.headers.get("host"),
    )
    return await _build_mini_app_my_market_requests_payload(
        telegram_id,
        username,
    )


@app.get("/api/market/my/requests/{request_id}")
async def mini_app_my_market_request_detail(
    request_id: int,
    request: Request,
    x_telegram_init_data: str | None = Header(default=None, alias="X-Telegram-Init-Data"),
    x_dev_telegram_id: str | None = Header(default=None, alias="X-Dev-Telegram-Id"),
):
    """Return one owned active market buy-request detail payload for Mini App."""
    telegram_id, username = _resolve_mini_app_identity(
        x_telegram_init_data=x_telegram_init_data,
        x_dev_telegram_id=x_dev_telegram_id,
        request_host=request.headers.get("host"),
    )
    return await _build_mini_app_market_request_detail_payload(
        telegram_id,
        username,
        request_id=request_id,
    )


@app.get("/api/pokemon")
async def mini_app_pokemon_detail(
    request: Request,
    user_pokemon_id: int = Query(..., ge=1),
    x_telegram_init_data: str | None = Header(default=None, alias="X-Telegram-Init-Data"),
    x_dev_telegram_id: str | None = Header(default=None, alias="X-Dev-Telegram-Id"),
):
    """Return one owned pokemon detail payload for Mini App."""
    telegram_id, username = _resolve_mini_app_identity(
        x_telegram_init_data=x_telegram_init_data,
        x_dev_telegram_id=x_dev_telegram_id,
        request_host=request.headers.get("host"),
    )
    return await _build_mini_app_pokemon_detail_payload(
        telegram_id,
        username,
        user_pokemon_id=user_pokemon_id,
    )


@app.get("/api/pokemon/{user_pokemon_id}/instances")
async def mini_app_pokemon_instances(
    user_pokemon_id: int,
    request: Request,
    x_telegram_init_data: str | None = Header(default=None, alias="X-Telegram-Init-Data"),
    x_dev_telegram_id: str | None = Header(default=None, alias="X-Dev-Telegram-Id"),
):
    """Return owned instances for the same pokemon species in Mini App."""
    telegram_id, username = _resolve_mini_app_identity(
        x_telegram_init_data=x_telegram_init_data,
        x_dev_telegram_id=x_dev_telegram_id,
        request_host=request.headers.get("host"),
    )
    return await _build_mini_app_pokemon_instances_payload(
        telegram_id,
        username,
        user_pokemon_id=user_pokemon_id,
    )


@app.post("/api/pokemon/{user_pokemon_id}/lock-toggle")
async def mini_app_pokemon_lock_toggle(
    user_pokemon_id: int,
    request: Request,
    x_telegram_init_data: str | None = Header(default=None, alias="X-Telegram-Init-Data"),
    x_dev_telegram_id: str | None = Header(default=None, alias="X-Dev-Telegram-Id"),
):
    """Toggle one owned pokemon lock state for Mini App."""
    telegram_id, username = _resolve_mini_app_identity(
        x_telegram_init_data=x_telegram_init_data,
        x_dev_telegram_id=x_dev_telegram_id,
        request_host=request.headers.get("host"),
    )
    try:
        await db.toggle_user_pokemon_lock(
            telegram_id,
            username,
            user_pokemon_id=user_pokemon_id,
        )
    except ShopError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    return await _build_mini_app_pokemon_detail_payload(
        telegram_id,
        username,
        user_pokemon_id=user_pokemon_id,
    )


@app.post("/api/pokemon/{user_pokemon_id}/image-cycle")
async def mini_app_pokemon_image_cycle(
    user_pokemon_id: int,
    request: Request,
    x_telegram_init_data: str | None = Header(default=None, alias="X-Telegram-Init-Data"),
    x_dev_telegram_id: str | None = Header(default=None, alias="X-Dev-Telegram-Id"),
):
    """Cycle the active pokemon image variant for Mini App."""
    telegram_id, username = _resolve_mini_app_identity(
        x_telegram_init_data=x_telegram_init_data,
        x_dev_telegram_id=x_dev_telegram_id,
        request_host=request.headers.get("host"),
    )
    entry = await db.get_owned_user_pokemon_entry(
        telegram_id,
        username,
        user_pokemon_id=user_pokemon_id,
    )
    if entry is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Pokemon not found",
        )

    await db.cycle_pokemon_image_selection(
        telegram_id,
        username,
        pokemon_id=entry.pokemon_id,
    )
    return await _build_mini_app_pokemon_detail_payload(
        telegram_id,
        username,
        user_pokemon_id=user_pokemon_id,
    )


@app.post("/api/pokemon/{user_pokemon_id}/release")
async def mini_app_pokemon_release(
    user_pokemon_id: int,
    request: Request,
    x_telegram_init_data: str | None = Header(default=None, alias="X-Telegram-Init-Data"),
    x_dev_telegram_id: str | None = Header(default=None, alias="X-Dev-Telegram-Id"),
):
    """Release one owned pokemon from Mini App."""
    telegram_id, username = _resolve_mini_app_identity(
        x_telegram_init_data=x_telegram_init_data,
        x_dev_telegram_id=x_dev_telegram_id,
        request_host=request.headers.get("host"),
    )
    try:
        result = await db.release_user_pokemon(
            telegram_id,
            username,
            user_pokemon_id=user_pokemon_id,
        )
    except ShopError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    return {
        "userPokemonId": result.user_pokemon_id,
        "pokemonId": result.pokemon_id,
        "name": result.name,
        "rarity": result.rarity,
        "rewardAmount": result.reward_amount,
    }


@app.get("/api/pokemon/{user_pokemon_id}/sell-precheck")
async def mini_app_pokemon_sell_precheck(
    user_pokemon_id: int,
    request: Request,
    x_telegram_init_data: str | None = Header(default=None, alias="X-Telegram-Init-Data"),
    x_dev_telegram_id: str | None = Header(default=None, alias="X-Dev-Telegram-Id"),
):
    """Return whether one owned pokemon can enter Mini App sell flow."""
    telegram_id, username = _resolve_mini_app_identity(
        x_telegram_init_data=x_telegram_init_data,
        x_dev_telegram_id=x_dev_telegram_id,
        request_host=request.headers.get("host"),
    )
    error = await db.get_market_sell_precheck_error(
        telegram_id,
        username,
        user_pokemon_id=user_pokemon_id,
    )
    return {
        "ok": error is None,
        "error": error,
    }


@app.post("/api/pokemon/{user_pokemon_id}/sell")
async def mini_app_pokemon_sell(
    user_pokemon_id: int,
    request: Request,
    payload: MiniAppMarketSellRequest = Body(...),
    x_telegram_init_data: str | None = Header(default=None, alias="X-Telegram-Init-Data"),
    x_dev_telegram_id: str | None = Header(default=None, alias="X-Dev-Telegram-Id"),
):
    """Create one market listing from Mini App."""
    telegram_id, username = _resolve_mini_app_identity(
        x_telegram_init_data=x_telegram_init_data,
        x_dev_telegram_id=x_dev_telegram_id,
        request_host=request.headers.get("host"),
    )
    try:
        listing = await db.create_market_listing(
            telegram_id,
            username,
            user_pokemon_id=user_pokemon_id,
            price=payload.price,
        )
    except ShopError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    return {
        "listingId": listing.listing_id,
        "userPokemonId": listing.user_pokemon_id,
        "pokemonId": listing.pokemon_id,
        "price": listing.price,
        "sellerLabel": listing.seller_label or "Тренер",
        "daysRemaining": listing.days_remaining,
    }


@app.post("/api/market/{listing_id}/buy")
async def mini_app_market_purchase(
    listing_id: int,
    request: Request,
    x_telegram_init_data: str | None = Header(default=None, alias="X-Telegram-Init-Data"),
    x_dev_telegram_id: str | None = Header(default=None, alias="X-Dev-Telegram-Id"),
):
    """Purchase one active market listing from Mini App."""
    telegram_id, username = _resolve_mini_app_identity(
        x_telegram_init_data=x_telegram_init_data,
        x_dev_telegram_id=x_dev_telegram_id,
        request_host=request.headers.get("host"),
    )
    try:
        result = await db.purchase_market_listing(
            telegram_id,
            username,
            listing_id=listing_id,
        )
    except ShopError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    return {
        "listingId": result.listing.listing_id,
        "userPokemonId": result.listing.user_pokemon_id,
        "pokemonId": result.listing.pokemon_id,
        "price": result.price,
    }


@app.post("/api/market/my/listings/{listing_id}/remove")
async def mini_app_market_remove_listing(
    listing_id: int,
    request: Request,
    x_telegram_init_data: str | None = Header(default=None, alias="X-Telegram-Init-Data"),
    x_dev_telegram_id: str | None = Header(default=None, alias="X-Dev-Telegram-Id"),
):
    """Remove one owned active market listing from Mini App."""
    telegram_id, username = _resolve_mini_app_identity(
        x_telegram_init_data=x_telegram_init_data,
        x_dev_telegram_id=x_dev_telegram_id,
        request_host=request.headers.get("host"),
    )
    try:
        listing = await db.remove_market_listing(
            telegram_id,
            username,
            listing_id=listing_id,
        )
    except ShopError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    return {
        "listingId": listing.listing_id,
        "userPokemonId": listing.user_pokemon_id,
        "pokemonId": listing.pokemon_id,
    }


@app.post("/api/market/my/requests/{request_id}/cancel")
async def mini_app_market_cancel_request(
    request_id: int,
    request: Request,
    x_telegram_init_data: str | None = Header(default=None, alias="X-Telegram-Init-Data"),
    x_dev_telegram_id: str | None = Header(default=None, alias="X-Dev-Telegram-Id"),
):
    """Cancel one owned active market buy request from Mini App."""
    telegram_id, username = _resolve_mini_app_identity(
        x_telegram_init_data=x_telegram_init_data,
        x_dev_telegram_id=x_dev_telegram_id,
        request_host=request.headers.get("host"),
    )
    try:
        market_request = await db.cancel_market_buy_request(
            telegram_id,
            username,
            request_id=request_id,
        )
    except ShopError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    return {
        "requestId": market_request.request_id,
        "pokemonId": market_request.pokemon_id,
        "reservedAmount": market_request.reserved_amount,
    }


@app.post(WEBHOOK_PATH)
async def telegram_webhook(request: Request):
    """Handle incoming Telegram webhook updates."""
    try:
        # Parse incoming update
        data = await request.json()
        update = Update.de_json(data, bot_app.bot)
        
        # Process update
        await bot_app.update_queue.put(update)
        
        return Response(status_code=status.HTTP_200_OK)
    
    except Exception as e:
        logger.error("webhook_error", error=str(e))
        return Response(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR)


if __name__ == "__main__":
    import uvicorn
    
    uvicorn.run(
        "main:app",
        host=HOST,
        port=PORT,
        reload=False,
        log_level="info",
    )
