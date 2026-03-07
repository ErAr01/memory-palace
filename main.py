import asyncio
import logging
import sys

from src.bot.bot import start_bot


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
    ],
)

logging.getLogger("telethon").setLevel(logging.WARNING)
logging.getLogger("aiogram").setLevel(logging.INFO)


def main() -> None:
    """Entry point for the bot."""
    asyncio.run(start_bot())


if __name__ == "__main__":
    main()
