import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from loguru import logger
from config import settings
from utils.logger import setup_logger
from core.database import get_db, close_db


async def main():
    setup_logger()
    logger.info("Starting ContentForwardBot...")
    await get_db()
    logger.info("Bot initialized. Ready for further development.")
    await close_db()
    logger.info("Shutdown complete")


if __name__ == "__main__":
    asyncio.run(main())
