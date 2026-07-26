import asyncio
from datetime import datetime
from loguru import logger
from pyrogram import Client

from core.database import (
    get_due_queue_items,
    update_queue_status,
    update_pending_status,
    get_setting,
    get_admins,
    log_action,
)

QUEUE_INTERVAL = 9000


class QueueWorker:
    def __init__(self, pyrogram_client: Client):
        self._client = pyrogram_client
        self._task: asyncio.Task | None = None
        self._running = False

    async def start(self):
        self._running = True
        self._task = asyncio.create_task(self._loop())
        logger.info("QueueWorker started (interval={}s)", QUEUE_INTERVAL)

    async def stop(self):
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        logger.info("QueueWorker stopped")

    async def _loop(self):
        while self._running:
            try:
                await self._process_due_items()
            except asyncio.CancelledError:
                break
            except Exception:
                logger.exception("QueueWorker error")
            await asyncio.sleep(QUEUE_INTERVAL)

    async def _process_due_items(self):
        items = await get_due_queue_items()
        if not items:
            return

        logger.info("QueueWorker: {} due item(s) found", len(items))

        target = await get_setting("target_channel")
        if not target:
            logger.warning("QueueWorker: no target channel configured, skipping")
            return

        tag = await get_setting("custom_tag") or ""

        for item in items:
            await self._send_item(item, target, tag)

    async def _send_item(self, item: dict, target: str, tag: str):
        queue_id = item["queue_id"]
        pending_id = item["pending_id"]
        content_type = item.get("content_type", "Text")
        text = item.get("text_or_caption") or ""
        media_id = item.get("media_file_id")
        source_chat = item.get("source_channel")
        msg_id = item.get("message_id")

        if tag:
            text = f"{text}\n\n{tag}" if text else tag

        try:
            if content_type == "Photo" and media_id:
                await self._client.send_photo(
                    chat_id=target, photo=media_id, caption=text
                )
            elif content_type == "Video" and media_id:
                await self._client.send_video(
                    chat_id=target, video=media_id, caption=text
                )
            elif source_chat and msg_id:
                from_chat = (
                    int(source_chat)
                    if source_chat.lstrip("-").isdigit()
                    else source_chat
                )
                await self._client.copy_message(
                    chat_id=target, from_chat_id=from_chat, message_id=msg_id
                )
            else:
                await self._client.send_message(chat_id=target, text=text)

            await update_queue_status(queue_id, "sent")
            await update_pending_status(pending_id, "sent")
            await log_action(0, f"queue_sent:{pending_id}")

            logger.info(
                "QueueWorker: sent pending_id={} to {}", pending_id, target
            )

            await self._notify_admins(pending_id, target)

        except Exception:
            logger.exception("QueueWorker: failed to send pending_id={}", pending_id)
            await update_queue_status(queue_id, "failed")

    async def _notify_admins(self, pending_id: int, target: str):
        admins = await get_admins()
        for admin in admins:
            try:
                await self._client.send_messages(
                    admin["user_id"],
                    [
                        f"Message #{pending_id} has been sent to {target} by the queue worker."
                    ],
                )
            except Exception:
                pass
