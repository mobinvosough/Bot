import asyncio
import os
import tempfile
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
from utils.cleaner import clean_and_tag

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

        tag = await get_setting("custom_tag")

        for item in items:
            await self._send_item(item, target, tag)

    async def _send_item(self, item: dict, target: str, tag: str | None):
        queue_id = item["queue_id"]
        pending_id = item["pending_id"]
        content_type = item.get("content_type", "Text")
        raw_text = item.get("text_or_caption") or ""
        text = clean_and_tag(raw_text, tag)
        source_chat = item.get("source_channel")
        msg_id = item.get("message_id")
        tmp_path = None

        try:
            from_chat = (
                int(source_chat)
                if source_chat and source_chat.lstrip("-").isdigit()
                else source_chat
            )

            if content_type == "Photo" and from_chat and msg_id:
                tmp_path = tempfile.NamedTemporaryFile(suffix=".jpg", delete=False).name
                orig_msg = await self._client.get_messages(from_chat, msg_id)
                if orig_msg and orig_msg.photo:
                    await self._client.download_media(orig_msg, file_name=tmp_path)
                    await self._client.send_photo(
                        chat_id=target, photo=tmp_path, caption=text
                    )
                else:
                    await self._client.send_message(chat_id=target, text=text)
            elif content_type == "Video" and from_chat and msg_id:
                tmp_path = tempfile.NamedTemporaryFile(suffix=".mp4", delete=False).name
                orig_msg = await self._client.get_messages(from_chat, msg_id)
                if orig_msg and orig_msg.video:
                    await self._client.download_media(orig_msg, file_name=tmp_path)
                    await self._client.send_video(
                        chat_id=target, video=tmp_path, caption=text
                    )
                else:
                    await self._client.send_message(chat_id=target, text=text)
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
        finally:
            if tmp_path and os.path.exists(tmp_path):
                try:
                    os.unlink(tmp_path)
                except OSError:
                    pass

    async def _notify_admins(self, pending_id: int, target: str):
        admins = await get_admins()
        for admin in admins:
            try:
                await self._client.send_message(
                    admin["user_id"],
                    f"Message #{pending_id} has been sent to {target} by the queue worker.",
                )
            except Exception:
                pass
