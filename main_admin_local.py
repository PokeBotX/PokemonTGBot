"""PokéCollect Admin Bot - local polling entrypoint for development."""

from __future__ import annotations

import os

import structlog
from dotenv import load_dotenv
from telegram import Bot, BotCommand
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
broadcast_bot: Bot | None = None


async def post_init(application: Application) -> None:
    """Prepare admin-bot state for local polling."""
    global broadcast_bot
    logger.info(
        "admin_startup_config",
        mode="polling",
        db_enabled=DB_ENABLED,
        redis_enabled=REDIS_ENABLED,
        session_redis_enabled=SESSION_REDIS_ENABLED,
        drop_pending_updates=DROP_PENDING_UPDATES,
    )
    admin_session_store.disable_redis()
    if REDIS_ENABLED and SESSION_REDIS_ENABLED:
        admin_session_store.configure_redis(REDIS_URL)
        application.bot_data["redis_url"] = REDIS_URL

    if DB_ENABLED:
        db = Database()
        await db.connect()
        if DB_INIT_SCHEMA:
            await db.init_schema(DB_SCHEMA_PATH)
        application.bot_data["db"] = db
        logger.info("admin_db_ready", schema_init=DB_INIT_SCHEMA)

    main_bot_token = (os.getenv("TELEGRAM_BOT_TOKEN") or "").strip()
    if main_bot_token:
        broadcast_bot = Bot(token=main_bot_token)
        if main_bot_token != settings.token:
            await broadcast_bot.initialize()
        application.bot_data["broadcast_bot"] = broadcast_bot
        logger.info("admin_broadcast_bot_ready", shared_token=main_bot_token == settings.token)

    await application.bot.delete_webhook(drop_pending_updates=DROP_PENDING_UPDATES)
    await application.bot.set_my_commands(
        [
            BotCommand("start", "Открыть админ-бота"),
            BotCommand("menu", "Открыть админ-меню"),
        ]
    )
    logger.info("admin_bot_ready", mode="polling")


async def post_shutdown(application: Application) -> None:
    """Close admin-bot resources on shutdown."""
    global broadcast_bot
    db = application.bot_data.get("db")
    if db is not None:
        await db.close()
    if broadcast_bot is not None:
        if broadcast_bot.token != settings.token:
            await broadcast_bot.shutdown()
        broadcast_bot = None
    admin_session_store.disable_redis()


def build_application() -> Application:
    """Build the admin Telegram application."""
    register_admin_routes()
    application = (
        Application.builder()
        .token(settings.token)
        .post_init(post_init)
        .post_shutdown(post_shutdown)
        .build()
    )
    application.add_handler(CommandHandler("start", start_admin_command))
    application.add_handler(CommandHandler("menu", menu_admin_command))
    application.add_handler(CallbackQueryHandler(handle_admin_callback_query))
    application.add_handler(MessageHandler(filters.ChatType.PRIVATE & filters.TEXT & ~filters.COMMAND, handle_admin_text_input))
    application.add_handler(MessageHandler(filters.ChatType.PRIVATE & (filters.PHOTO | filters.Document.ALL), handle_admin_media_input))
    return application


def main() -> None:
    """Run the admin bot in polling mode."""
    app = build_application()
    logger.info("admin_bot_starting", mode="polling")
    app.run_polling(
        allowed_updates=["message", "callback_query"],
        drop_pending_updates=DROP_PENDING_UPDATES,
    )


if __name__ == "__main__":
    main()
