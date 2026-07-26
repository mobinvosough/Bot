import asyncio
from typing import Callable, Awaitable

from pathlib import Path

from pyrogram import Client
from pyrogram.types import Message
from pyrogram.enums import MessageMediaType
from loguru import logger

from config import settings
from core.database import (
    get_source_channels,
    is_message_processed,
    save_pending_message,
)
from utils.cleaner import clean_text

POLL_INTERVAL = 20
RECONNECT_INTERVAL = 30
SESSION_NAME = "content_forward_bot"
SUPPORTED_TYPES = {MessageMediaType.PHOTO, MessageMediaType.VIDEO, None}
TYPE_LABELS = {
    None: "Text",
    MessageMediaType.PHOTO: "Photo",
    MessageMediaType.VIDEO: "Video",
}


class SourceWatcher:
    def __init__(self, app: Client, send_preview: Callable[..., Awaitable]):
        self.app = app
        self.send_preview = send_preview
        self._task: asyncio.Task | None = None
        self._seen: set[tuple[str, int]] = set()
        self._running = False

    async def start(self):
        self._running = True
        self._task = asyncio.create_task(self._poll_loop())
        logger.info("SourceWatcher started (interval={}s)", POLL_INTERVAL)

    async def stop(self):
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        logger.info("SourceWatcher stopped")

    async def _poll_loop(self):
        while self._running:
            try:
                await self._scan_sources()
            except asyncio.CancelledError:
                break
            except Exception:
                logger.exception("Error in poll loop")
            await asyncio.sleep(POLL_INTERVAL)

    async def _scan_sources(self):
        sources = await get_source_channels()
        if not sources:
            return

        for src in sources:
            try:
                await self._check_channel(src)
            except Exception:
                logger.exception("Failed to check channel {}", src)

    async def _check_channel(self, source: str):
        try:
            chat = await self.app.get_chat(source)
        except Exception:
            logger.warning("Cannot resolve source channel: {}", source)
            return

        count = 0
        async for msg in self.app.get_chat_history(chat.id, limit=10):
            if count >= 5:
                break
            if not self._is_supported(msg):
                continue

            key = (str(chat.id), msg.id)
            if key in self._seen:
                continue
            if await is_message_processed(str(chat.id), msg.id):
                self._seen.add(key)
                continue

            self._seen.add(key)
            await self._process_message(msg, chat)
            count += 1

    def _is_supported(self, msg: Message) -> bool:
        if msg.media is None:
            return True
        return msg.media in SUPPORTED_TYPES

    async def _process_message(self, msg: Message, chat):
        content_type = TYPE_LABELS.get(msg.media, "Unknown")
        text = clean_text(msg.text or msg.caption)
        media_id = None

        if msg.media == MessageMediaType.PHOTO:
            media_id = msg.photo.file_id if msg.photo else None
        elif msg.media == MessageMediaType.VIDEO:
            media_id = msg.video.file_id if msg.video else None

        pending_id = await save_pending_message(
            source_channel=str(chat.id),
            message_id=msg.id,
            content_type=content_type,
            text_or_caption=text,
            media_file_id=media_id,
        )

        source_label = chat.username or chat.title or str(chat.id)
        await self.send_preview(
            pending_id=pending_id,
            source_label=source_label,
            content_type=content_type,
            text=text,
            pyrogram_msg=msg,
        )
        logger.info(
            "New {} from {}: pending_id={}", content_type, source_label, pending_id
        )


class PyrogramClient:
    def __init__(self):
        self.client = Client(
            name=SESSION_NAME,
            api_id=settings.API_ID,
            api_hash=settings.API_HASH,
            phone_number=settings.PHONE_NUMBER,
        )
        self.watcher: SourceWatcher | None = None
        self._reconnect_task: asyncio.Task | None = None

    async def start(self, send_preview: Callable[..., Awaitable]):
        logger.info("Starting Pyrogram client...")
        await self._connect_with_retry()
        self.watcher = SourceWatcher(self.client, send_preview)
        await self.watcher.start()
        self._reconnect_task = asyncio.create_task(self._reconnect_loop())

    async def stop(self):
        logger.info("Stopping Pyrogram client...")
        if self._reconnect_task:
            self._reconnect_task.cancel()
            try:
                await self._reconnect_task
            except asyncio.CancelledError:
                pass
        if self.watcher:
            await self.watcher.stop()
        try:
            await self.client.stop()
        except Exception:
            pass
        logger.info("Pyrogram client stopped")

    async def _connect_with_retry(self):
        while True:
            try:
                await self.client.start()
                logger.info("Pyrogram client connected")
                return
            except Exception:
                logger.warning("Pyrogram connect failed, retrying in {}s", RECONNECT_INTERVAL)
                await asyncio.sleep(RECONNECT_INTERVAL)

    async def _reconnect_loop(self):
        while True:
            await asyncio.sleep(60)
            try:
                if not self.client.is_connected:
                    logger.warning("Pyrogram disconnected, reconnecting...")
                    await self._connect_with_retry()
            except asyncio.CancelledError:
                break
            except Exception:
                logger.exception("Reconnect check failed")
