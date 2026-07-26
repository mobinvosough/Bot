import asyncio
import json
from typing import Callable, Awaitable

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


def _extract_text(msg: Message) -> str | None:
    for attr in ("text", "caption", "description"):
        val = getattr(msg, attr, None)
        if val:
            return val
    return None


class SourceWatcher:
    def __init__(
        self,
        app: Client,
        send_preview: Callable[..., Awaitable],
        send_album_preview: Callable[..., Awaitable] | None = None,
    ):
        self.app = app
        self.send_preview = send_preview
        self.send_album_preview = send_album_preview
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

            if msg.media_group_id:
                await self._process_album(msg, chat)
            else:
                await self._process_message(msg, chat)
            count += 1

    def _is_supported(self, msg: Message) -> bool:
        if msg.media is None:
            return True
        return msg.media in SUPPORTED_TYPES

    async def _process_album(self, msg: Message, chat):
        try:
            album_msgs = await self.app.get_media_group(chat.id, msg.id)
        except Exception:
            logger.exception("Failed to get media group for msg_id={}", msg.id)
            return

        for m in album_msgs:
            self._seen.add((str(chat.id), m.id))

        text = clean_text(_extract_text(msg))

        media_items = []
        for m in album_msgs:
            if m.photo:
                media_items.append({"type": "photo", "file_id": m.photo.file_id})
            elif m.video:
                media_items.append({"type": "video", "file_id": m.video.file_id})

        if not media_items:
            return

        media_ids_json = json.dumps(media_items)
        first_type = media_items[0]["type"].capitalize()

        pending_id = await save_pending_message(
            source_channel=str(chat.id),
            message_id=msg.id,
            content_type=f"Album ({len(media_items)} items)",
            text_or_caption=text,
            media_file_id=media_ids_json,
        )

        source_label = chat.username or chat.title or str(chat.id)
        logger.info(
            "New Album ({}) from {}: pending_id={}, sending preview...",
            len(media_items), source_label, pending_id,
        )

        if self.send_album_preview:
            try:
                await self.send_album_preview(
                    pending_id=pending_id,
                    source_label=source_label,
                    text=text,
                    album_msgs=album_msgs,
                )
                logger.info("Album preview sent for pending_id={}", pending_id)
            except Exception:
                logger.exception("Failed to send album preview for pending_id={}", pending_id)

    async def _process_message(self, msg: Message, chat):
        content_type = TYPE_LABELS.get(msg.media, "Unknown")
        text = clean_text(_extract_text(msg))
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
        self._send_preview: Callable[..., Awaitable] | None = None
        self._send_album_preview: Callable[..., Awaitable] | None = None
        self._reconnect_task: asyncio.Task | None = None

    async def start(
        self,
        send_preview: Callable[..., Awaitable] | None = None,
        send_album_preview: Callable[..., Awaitable] | None = None,
    ):
        logger.info("Starting Pyrogram client...")
        self._send_preview = send_preview
        self._send_album_preview = send_album_preview
        await self._connect_with_retry()
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
                await self._start_watcher()
                return
            except Exception:
                if attempt < max_retries:
                    logger.warning(
                        "Pyrogram connect failed (attempt {}/{}), retrying in {}s",
                        attempt, max_retries, RECONNECT_INTERVAL,
                    )
                    await asyncio.sleep(RECONNECT_INTERVAL)
                else:
                    logger.error(
                        "Pyrogram connect failed after {} attempts. "
                        "Run 'python login.py' to authenticate, then copy the .session file.",
                        max_retries,
                    )

    async def _start_watcher(self):
        if self.watcher is None and self._send_preview:
            self.watcher = SourceWatcher(
                self.client, self._send_preview, self._send_album_preview
            )
            await self.watcher.start()

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
