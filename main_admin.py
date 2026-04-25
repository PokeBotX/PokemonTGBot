"""PokéCollect Admin Bot - FastAPI application with Telegram webhook."""

from __future__ import annotations

import os
from contextlib import asynccontextmanager
from pathlib import Path

import structlog
from dotenv import load_dotenv
from fastapi import FastAPI, Request, Response
from fastapi.responses import JSONResponse
from telegram import BotCommand, Update
from telegram.ext import Application, CallbackQueryHandler, CommandHandler, MessageHandler, filters

from bot.admin.config import load_admin_bot_settings
from bot.admin.handlers import (
    handle_admin_callback_query,
    handle_admin_media_input,
    handle_admin_text_input,
    menu_admin_command,
    register_admin_routes,
    start_admin_command,
)
from bot.admin.session import admin_session_store
from bot.db import Database
from bot.utils.logging import setup_logging

setup_logging()
logger = structlog.get_logger()
load_dotenv()

settings = load_admin_bot_settings()
DB_ENABLED = os.getenv("DB_ENABLED", "false").lower() == "true"
DB_INIT_SCHEMA = os.getenv("DB_INIT_SCHEMA", "false").lower() == "true"
DB_SCHEMA_PATH = os.getenv("DB_SCHEMA_PATH", "sql/schema.sql")
REDIS_ENABLED = os.getenv("REDIS_ENABLED", "false").lower() == "true"
REDIS_URL = os.getenv("REDIS_URL", "redis://127.0.0.1:6379/0")
SESSION_REDIS_ENABLED = os.getenv("SESSION_REDIS_ENABLED", "false").lower() == "true"
DROP_PENDING_UPDATES = os.getenv("DROP_PENDING_UPDATES", "false").lower() == "true"

admin_bot_app: Application | None = None
db: Database | None = None


async def setup_webhook() -> None:
    """Configure Telegram webhook for the admin bot."""
    webhook_full_url = f"{settings.webhook_url}{settings.webhook_path}"
    webhook_kwargs = {"url": webhook_full_url}
    certificate = None
    if settings.webhook_cert_path:
        cert_path = Path(settings.webhook_cert_path)
        if cert_path.exists():
            certificate = cert_path.open("rb")
            webhook_kwargs["certificate"] = certificate
    await admin_bot_app.bot.delete_webhook(drop_pending_updates=DROP_PENDING_UPDATES)
    try:
        await admin_bot_app.bot.set_webhook(**webhook_kwargs)
    finally:
        if certificate is not None:
            certificate.close()
    logger.info("admin_webhook_configured", url=webhook_full_url)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Start and stop the admin Telegram bot application."""
    global admin_bot_app, db

    logger.info(
        "admin_startup_config",
        mode="webhook",
        db_enabled=DB_ENABLED,
        redis_enabled=REDIS_ENABLED,
        session_redis_enabled=SESSION_REDIS_ENABLED,
        drop_pending_updates=DROP_PENDING_UPDATES,
    )
    register_admin_routes()
    admin_session_store.disable_redis()
    if REDIS_ENABLED and SESSION_REDIS_ENABLED:
        admin_session_store.configure_redis(REDIS_URL)

    admin_bot_app = Application.builder().token(settings.token).build()
    admin_bot_app.add_handler(CommandHandler("start", start_admin_command))
    admin_bot_app.add_handler(CommandHandler("menu", menu_admin_command))
    admin_bot_app.add_handler(CallbackQueryHandler(handle_admin_callback_query))
    admin_bot_app.add_handler(MessageHandler(filters.ChatType.PRIVATE & filters.TEXT & ~filters.COMMAND, handle_admin_text_input))
    admin_bot_app.add_handler(MessageHandler(filters.ChatType.PRIVATE & (filters.PHOTO | filters.Document.ALL), handle_admin_media_input))
    await admin_bot_app.initialize()
    await admin_bot_app.start()

    if DB_ENABLED:
        db = Database()
        await db.connect()
        if DB_INIT_SCHEMA:
            await db.init_schema(DB_SCHEMA_PATH)
        admin_bot_app.bot_data["db"] = db
        logger.info("admin_db_ready", schema_init=DB_INIT_SCHEMA)

    await admin_bot_app.bot.set_my_commands(
        [
            BotCommand("start", "Открыть админ-бота"),
            BotCommand("menu", "Открыть админ-меню"),
        ]
    )
    if settings.webhook_url:
        await setup_webhook()

    logger.info("admin_bot_started", mode="webhook", port=settings.port)
    try:
        yield
    finally:
        if admin_bot_app is not None:
            await admin_bot_app.stop()
            await admin_bot_app.shutdown()
            admin_bot_app = None
        if db is not None:
            await db.close()
            db = None
        admin_session_store.disable_redis()


app = FastAPI(title="PokéCollect Admin Bot", lifespan=lifespan)


@app.get("/")
async def root() -> dict[str, str]:
    """Basic status endpoint."""
    return {"message": "PokéCollect Admin Bot is running"}


@app.get("/health")
async def health_check() -> JSONResponse:
    """Operational health endpoint for the admin bot."""
    healthy = admin_bot_app is not None and ((not DB_ENABLED) or db is not None)
    payload = {
        "status": "healthy" if healthy else "degraded",
        "bot_initialized": admin_bot_app is not None,
        "db_enabled": DB_ENABLED,
        "db_connected": (not DB_ENABLED) or db is not None,
    }
    return JSONResponse(content=payload, status_code=200 if healthy else 503)


@app.post(settings.webhook_path)
async def telegram_admin_webhook(request: Request) -> Response:
    """Handle incoming Telegram webhook updates for the admin bot."""
    try:
        payload = await request.json()
        update = Update.de_json(payload, admin_bot_app.bot)
        await admin_bot_app.process_update(update)
        return Response(status_code=200)
    except Exception as exc:
        logger.exception("admin_webhook_error", error=str(exc))
        return Response(status_code=500)
