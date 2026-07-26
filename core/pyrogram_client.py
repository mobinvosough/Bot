import asyncio
from typing import Callable, Awaitable

from pathlib import Path

import core.pyrogram_patch  # noqa: F401

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
        logger.info(
            "New {} from {}: pending_id={}, sending preview to admins...",
            content_type, source_label, pending_id,
        )
        try:
            await self.send_preview(
                pending_id=pending_id,
                source_label=source_label,
                content_type=content_type,
                text=text,
                pyrogram_msg=msg,
            )
            logger.info("Preview sent successfully for pending_id={}", pending_id)
        except Exception:
            logger.exception("Failed to send preview for pending_id={}", pending_id)


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

    async def start(self, send_preview: Callable[..., Awaitable] | None = None):
        logger.info("Starting Pyrogram client...")
        await self._connect_with_retry()
        if send_preview:
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
        max_retries = 3
        for attempt in range(1, max_retries + 1):
            try:
                await self.client.start()
                logger.info("Pyrogram client connected")
                await self._cache_peers()
                return
            except Exception:
                if attempt < max_retries:
                    logger.warning("Pyrogram connect failed (attempt {}/{}), retrying in {}s", attempt, max_retries, RECONNECT_INTERVAL)
                    await asyncio.sleep(RECONNECT_INTERVAL)
                else:
                    logger.error("Pyrogram connect failed after {} attempts. Run 'python login.py' on a machine with a terminal to authenticate, then copy the .session file to this server.", max_retries)
                    return

    async def _cache_peers(self):
        try:
            count = 0
            async for dialog in self.client.get_dialogs(limit=200):
                count += 1
            logger.info("Cached {} peers from dialogs", count)
        except Exception:
            logger.exception("Failed to cache peers")

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
