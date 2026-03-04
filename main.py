"""PokéCollect Bot - Main application."""
import os
import structlog
from dotenv import load_dotenv
from telegram.ext import Application, CommandHandler, CallbackQueryHandler

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

logger = structlog.get_logger()


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


def main() -> None:
    """Start the bot."""
    # Setup logging first
    setup_logging()
    
    # Load environment variables
    load_dotenv()
    
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    if not token:
        raise ValueError("TELEGRAM_BOT_TOKEN not set in .env")
    
    logger.info("bot_starting")
    
    # Register navigation routes
    register_routes()
    
    # Create application
    application = Application.builder().token(token).build()
    
    # Register command handlers
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("menu", menu_command))
    
    # Register callback query handler
    application.add_handler(CallbackQueryHandler(handle_callback_query))
    
    logger.info("handlers_registered")
    
    # Set up bot commands menu (run after bot starts)
    application.post_init = setup_bot_commands
    
    # Start bot
    logger.info("bot_polling_started")
    application.run_polling(allowed_updates=["message", "callback_query"])


if __name__ == "__main__":
    main()
