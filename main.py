"""PokéCollect Bot - FastAPI application with Telegram webhook."""
import os
import structlog
from contextlib import asynccontextmanager
from dotenv import load_dotenv
from fastapi import FastAPI, Request, Response, status
from telegram import Update
from telegram.ext import Application, CommandHandler, CallbackQueryHandler

from bot.db import Database
from bot.utils.logging import setup_logging
from bot.handlers.commands import start_command, menu_command
from bot.handlers.navigation import handle_callback_query
from bot.navigation.router import navigation_router

# Import section handlers
from bot.handlers.sections.shop import shop_handler
from bot.handlers.sections.market import market_handler
from bot.handlers.sections.profile import profile_handler
from bot.handlers.sections.games import games_handler
from bot.handlers.sections.collection import collection_handler
from bot.handlers.sections.updates import updates_handler
from bot.handlers.sections.chat import chat_handler
from bot.handlers.sections.support import support_handler
from bot.handlers.sections.info import info_handler
from bot.handlers.sections.back import back_to_menu_handler

# Setup logging
setup_logging()
logger = structlog.get_logger()

# Load environment variables
load_dotenv()

# Configuration
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
WEBHOOK_URL = os.getenv("WEBHOOK_URL")  # Example: https://your-domain.com
WEBHOOK_PATH = os.getenv("WEBHOOK_PATH", "/webhook")
HOST = os.getenv("HOST", "0.0.0.0")
PORT = int(os.getenv("PORT", "8000"))
DB_ENABLED = os.getenv("DB_ENABLED", "false").lower() == "true"
DB_INIT_SCHEMA = os.getenv("DB_INIT_SCHEMA", "false").lower() == "true"
DB_SCHEMA_PATH = os.getenv("DB_SCHEMA_PATH", "sql/schema.sql")

if not TELEGRAM_BOT_TOKEN:
    raise ValueError("TELEGRAM_BOT_TOKEN not set in .env")
if not WEBHOOK_URL:
    raise ValueError("WEBHOOK_URL not set in .env")

# Global bot application
bot_app: Application = None
db: Database = None


def register_routes() -> None:
    """Register all section handlers with navigation router."""
    navigation_router.register("shop", shop_handler)
    navigation_router.register("market", market_handler)
    navigation_router.register("profile", profile_handler)
    navigation_router.register("games", games_handler)
    navigation_router.register("collection", collection_handler)
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
    ]
    
    await application.bot.set_my_commands(commands)
    logger.info("bot_commands_registered", commands=[c.command for c in commands])


async def setup_webhook() -> None:
    """Set up webhook for Telegram bot."""
    webhook_full_url = f"{WEBHOOK_URL}{WEBHOOK_PATH}"
    
    # Delete any existing webhook
    await bot_app.bot.delete_webhook(drop_pending_updates=True)
    logger.info("webhook_deleted")
    
    # Set new webhook
    await bot_app.bot.set_webhook(
        url=webhook_full_url,
        allowed_updates=["message", "callback_query"],
        drop_pending_updates=False,
    )
    
    webhook_info = await bot_app.bot.get_webhook_info()
    logger.info(
        "webhook_configured",
        url=webhook_info.url,
        has_custom_certificate=webhook_info.has_custom_certificate,
        pending_update_count=webhook_info.pending_update_count,
    )


@asynccontextmanager
async def lifespan(app: FastAPI):
    """FastAPI lifespan context manager."""
    global bot_app, db
    
    logger.info("bot_starting")
    
    # Register navigation routes
    register_routes()
    
    # Create Telegram application
    bot_app = Application.builder().token(TELEGRAM_BOT_TOKEN).build()
    
    # Register command handlers
    bot_app.add_handler(CommandHandler("start", start_command))
    bot_app.add_handler(CommandHandler("menu", menu_command))
    
    # Register callback query handler
    bot_app.add_handler(CallbackQueryHandler(handle_callback_query))
    
    logger.info("handlers_registered")
    
    # Initialize bot application
    await bot_app.initialize()
    await bot_app.start()

    # Initialize database (optional)
    if DB_ENABLED:
        db = Database()
        await db.connect()
        if DB_INIT_SCHEMA:
            await db.init_schema(DB_SCHEMA_PATH)
        bot_app.bot_data["db"] = db
        logger.info("db_ready", schema_init=DB_INIT_SCHEMA)
    
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
    await bot_app.stop()
    await bot_app.shutdown()


# Create FastAPI application
app = FastAPI(title="PokéCollect Bot", lifespan=lifespan)


@app.get("/")
async def root():
    """Health check endpoint."""
    return {"status": "ok", "bot": "PokéCollect"}


@app.get("/health")
async def health():
    """Health check endpoint."""
    return {"status": "healthy"}


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
