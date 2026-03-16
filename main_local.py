"""PokéCollect Bot - local polling entrypoint for development."""
import os

import structlog
from dotenv import load_dotenv
from telegram import BotCommand
from telegram.ext import Application, CallbackQueryHandler, CommandHandler

from bot.db import Database
from bot.handlers.commands import (
    collection_command,
    items_command,
    menu_command,
    pokemon_command,
    section_command,
    shop_command,
    start_command,
)
from bot.handlers.navigation import handle_callback_query
from bot.handlers.sections.back import back_to_menu_handler
from bot.handlers.sections.chat import chat_handler
from bot.handlers.sections.collection import register_collection_routes
from bot.handlers.sections.games import games_handler
from bot.handlers.sections.info import info_handler
from bot.handlers.sections.market import market_handler
from bot.handlers.sections.profile import profile_handler
from bot.handlers.sections.shop import register_shop_routes
from bot.handlers.sections.support import support_handler
from bot.handlers.sections.updates import updates_handler
from bot.navigation.router import navigation_router
from bot.navigation.session import session_store
from bot.utils.logging import setup_logging

setup_logging()
logger = structlog.get_logger()
load_dotenv()

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
DB_ENABLED = os.getenv("DB_ENABLED", "false").lower() == "true"
DB_INIT_SCHEMA = os.getenv("DB_INIT_SCHEMA", "false").lower() == "true"
DB_SCHEMA_PATH = os.getenv("DB_SCHEMA_PATH", "sql/schema.sql")
REDIS_ENABLED = os.getenv("REDIS_ENABLED", "false").lower() == "true"
REDIS_URL = os.getenv("REDIS_URL", "redis://127.0.0.1:6379/0")
if not TELEGRAM_BOT_TOKEN:
    raise ValueError("TELEGRAM_BOT_TOKEN not set in .env")


def register_routes() -> None:
    """Register all section handlers with navigation router."""
    register_shop_routes(navigation_router)
    register_collection_routes(navigation_router)
    navigation_router.register("market", market_handler)
    navigation_router.register("profile", profile_handler)
    navigation_router.register("games", games_handler)
    navigation_router.register("updates", updates_handler)
    navigation_router.register("chat", chat_handler)
    navigation_router.register("support", support_handler)
    navigation_router.register("info", info_handler)
    navigation_router.register("back", back_to_menu_handler)
    logger.info("routes_registered", routes=navigation_router.list_routes())


async def post_init(application: Application) -> None:
    """Prepare bot state for local polling."""
    session_store.disable_redis()
    if REDIS_ENABLED:
        session_store.configure_redis(REDIS_URL)
        application.bot_data["redis_url"] = REDIS_URL
        logger.info("redis_ready", redis_url=REDIS_URL)

    if DB_ENABLED:
        db = Database()
        await db.connect()
        if DB_INIT_SCHEMA:
            await db.init_schema(DB_SCHEMA_PATH)
        application.bot_data["db"] = db
        logger.info("db_ready", schema_init=DB_INIT_SCHEMA)

    await application.bot.delete_webhook(drop_pending_updates=True)
    await application.bot.set_my_commands([
        BotCommand("menu", "Открыть главное меню"),
        BotCommand("shop", "Открыть магазин"),
        BotCommand("pokemon", "Открыть раздел покемонов"),
        BotCommand("items", "Открыть раздел предметов"),
        BotCommand("market", "Открыть рынок"),
        BotCommand("profile", "Открыть профиль"),
        BotCommand("games", "Открыть мини-игры"),
        BotCommand("collection", "Открыть коллекцию"),
        BotCommand("updates", "Открыть обновления"),
        BotCommand("chat", "Открыть чат"),
        BotCommand("support", "Открыть поддержку"),
        BotCommand("info", "Открыть информацию"),
    ])
    logger.info("bot_ready", mode="polling")


async def post_shutdown(application: Application) -> None:
    """Close DB pool on polling shutdown."""
    db = application.bot_data.get("db")
    if db:
        await db.close()
    session_store.disable_redis()


def build_application() -> Application:
    """Build Telegram application with all handlers."""
    register_routes()
    application = (
        Application.builder()
        .token(TELEGRAM_BOT_TOKEN)
        .post_init(post_init)
        .post_shutdown(post_shutdown)
        .build()
    )
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("menu", menu_command))
    application.add_handler(CommandHandler("shop", shop_command))
    application.add_handler(CommandHandler("pokemon", pokemon_command))
    application.add_handler(CommandHandler("items", items_command))
    application.add_handler(CommandHandler("collection", collection_command))
    application.add_handler(CommandHandler(["market", "profile", "games", "updates", "chat", "support", "info"], section_command))
    application.add_handler(CallbackQueryHandler(handle_callback_query))
    return application


def main() -> None:
    """Run bot in local long polling mode."""
    app = build_application()
    logger.info("bot_starting", mode="polling")
    app.run_polling(allowed_updates=["message", "callback_query"], drop_pending_updates=True)


if __name__ == "__main__":
    main()
