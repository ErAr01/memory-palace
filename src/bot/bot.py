import logging

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode

from src.bot.handlers import router
from src.config import get_settings

logger = logging.getLogger(__name__)


def create_bot() -> Bot:
    """Create and configure the Telegram bot."""
    settings = get_settings()
    return Bot(
        token=settings.bot_token,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )


def create_dispatcher() -> Dispatcher:
    """Create and configure the dispatcher."""
    dp = Dispatcher()
    dp.include_router(router)
    return dp


async def start_bot() -> None:
    """Start the bot polling."""
    bot = create_bot()
    dp = create_dispatcher()
    
    logger.info("Starting bot...")
    
    try:
        await dp.start_polling(bot)
    finally:
        await bot.session.close()
