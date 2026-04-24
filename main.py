"""PokéCollect Bot - FastAPI application with Telegram webhook."""
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
from fastapi import FastAPI, Header, HTTPException, Request, Response, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from telegram import Update
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters

from bot.db import Database
from bot.db.database import MARKET_MAINTENANCE_INTERVAL_SECONDS, TRADE_MAINTENANCE_INTERVAL_SECONDS
from bot.utils.logging import setup_logging
from bot.handlers.chat_activity import group_message_activity_handler
from bot.handlers.commands import (
    buyprice_command,
    changename_command,
    collection_command,
    find_command,
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
from bot.handlers.sections.trade import register_trade_routes, run_trade_maintenance_job
from bot.handlers.sections.games import games_handler
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
DROP_PENDING_UPDATES = os.getenv("DROP_PENDING_UPDATES", "false").lower() == "true"

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


class TelegramAuthRequest(BaseModel):
    """Request payload for Mini App Telegram auth handshake."""

    initData: str


def _build_health_payload() -> dict[str, object]:
    """Build a shallow operational health payload for runtime dependencies."""
    bot_initialized = bot_app is not None
    db_connected = (not DB_ENABLED) or (db is not None and getattr(db, "pool", None) is not None)
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
        "coverPokemonName": profile_summary.cover_pokemon_name,
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
    if not DB_ENABLED or db is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database is not available for Mini App collection requests",
        )

    collection_page = await db.get_collection_page(telegram_id, username)
    return {
        "entries": [
            {
                "id": entry.pokemon_id,
                "userPokemonId": entry.sample_user_pokemon_id,
                "name": entry.name,
                "type": entry.pokemon_type or "Unknown",
                "level": 1,
                "rarity": entry.rarity,
                "quantity": entry.quantity,
                "baseHp": entry.base_hp,
                "baseAttack": entry.base_attack,
                "baseDefense": entry.base_defense,
                "baseStamina": entry.base_stamina,
                "imageCreditId": entry.image_credit_id,
                "isLocked": entry.is_locked,
            }
            for entry in collection_page.entries
        ],
        "pagination": {
            "totalEntries": collection_page.total_entries,
            "currentPage": collection_page.current_page,
            "totalPages": collection_page.total_pages,
        },
    }


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
    navigation_router.register("games", games_handler)
    navigation_router.register("updates", updates_handler)
    navigation_router.register("chat", chat_handler)
    navigation_router.register("support", support_handler)
    navigation_router.register("info", info_handler)
    navigation_router.register("back", back_to_menu_handler)
    
    logger.info("routes_registered", routes=navigation_router.list_routes())


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
    
    # Delete any existing webhook
    await bot_app.bot.delete_webhook(drop_pending_updates=DROP_PENDING_UPDATES)
    logger.info("webhook_deleted")
    
    try:
        await bot_app.bot.set_webhook(**webhook_kwargs)
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
        session_store.configure_redis(REDIS_URL)
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
    session_store.disable_redis()
    await bot_app.stop()
    await bot_app.shutdown()


# Create FastAPI application
app = FastAPI(title="PokéCollect Bot", lifespan=lifespan)


@app.get("/")
async def root():
    """Basic root endpoint."""
    return {"status": "ok", "bot": "PokéCollect", "docs": "/docs", "health": "/health"}


@app.get("/health")
async def health():
    """Operational health check for bot runtime and backing services."""
    payload = _build_health_payload()
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
async def mini_app_me(x_telegram_init_data: str = Header(alias="X-Telegram-Init-Data")):
    """Return the current Mini App profile using validated Telegram initData."""
    telegram_payload = _validate_telegram_init_data(x_telegram_init_data)
    telegram_id, username = _extract_mini_app_identity(telegram_payload)
    return await _build_mini_app_profile_payload(telegram_id, username)


@app.get("/api/collection")
async def mini_app_collection(x_telegram_init_data: str = Header(alias="X-Telegram-Init-Data")):
    """Return the current Mini App collection using validated Telegram initData."""
    telegram_payload = _validate_telegram_init_data(x_telegram_init_data)
    telegram_id, username = _extract_mini_app_identity(telegram_payload)
    return await _build_mini_app_collection_payload(telegram_id, username)


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
