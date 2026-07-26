from pyrogram import Client
from loguru import logger
from config import settings


class PyrogramClient:
    def __init__(self):
        self.client = Client(
            name="content_forward_bot",
            api_id=settings.API_ID,
            api_hash=settings.API_HASH,
            phone_number=settings.PHONE_NUMBER,
        )

    async def start(self):
        logger.info("Starting Pyrogram client...")
        await self.client.start()
        logger.info("Pyrogram client started")

    async def stop(self):
        logger.info("Stopping Pyrogram client...")
        await self.client.stop()
        logger.info("Pyrogram client stopped")
