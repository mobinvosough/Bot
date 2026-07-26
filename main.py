import asyncio
import signal
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from telegram import Bot
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    ConversationHandler,
    filters,
)
from loguru import logger

from config import settings
from utils.logger import setup_logger
from core.database import get_db, close_db, get_admins, get_setting, add_admin
from core.pyrogram_client import PyrogramClient
from core.queue_manager import QueueWorker
import bot.handlers as handlers
from bot.handlers import (
    SET_TARGET,
    SET_SOURCE,
    SET_TAG,
    SET_ADMIN,
    SETUP_TARGET,
    SETUP_SOURCE,
    SETUP_ADMIN,
    start_command,
    set_target_save,
    add_source_save,
    set_tag_save,
    add_admin_save,
    menu_status,
    menu_sources,
    menu_add_source_entry,
    menu_target,
    menu_admins,
    menu_add_admin_entry,
    menu_tag,
    menu_queue,
    menu_settings,
    back_main,
    remove_admin_cb,
    remove_source_cb,
    cancel,
    conv_cancel_callback,
    preview_add_queue,
    preview_send_now,
    preview_reject,
    cancel_queue_cb,
    setup_target_save,
    setup_source_save,
    setup_admin_save,
)
from bot.keyboards import preview_keyboard

pyrogram_client = PyrogramClient()


def make_send_preview(bot: Bot):
    async def send_preview(
        pending_id: int,
        source_label: str,
        content_type: str,
        text: str | None,
        pyrogram_msg=None,
    ):
        admins = await get_admins()
        tag = await get_setting("custom_tag")
        from utils.cleaner import clean_and_tag
        display_text = clean_and_tag(text, tag)
        header = f"**{content_type}** from `{source_label}`\n\n{display_text}\n\nID: #{pending_id}"

        kb = preview_keyboard(pending_id)

        for admin in admins:
            uid = admin["user_id"]
            try:
                if pyrogram_msg and content_type == "Photo" and pyrogram_msg.photo:
                    await bot.send_photo(
                        chat_id=uid,
                        photo=pyrogram_msg.photo.file_id,
                        caption=header,
                        reply_markup=kb,
                    )
                elif pyrogram_msg and content_type == "Video" and pyrogram_msg.video:
                    await bot.send_video(
                        chat_id=uid,
                        video=pyrogram_msg.video.file_id,
                        caption=header,
                        reply_markup=kb,
                    )
                else:
                    await bot.send_message(
                        chat_id=uid,
                        text=header,
                        reply_markup=kb,
                    )
            except Exception:
                logger.exception("Failed to send preview to admin {}", uid)

    return send_preview


def build_app() -> Application:
    app = Application.builder().token(settings.BOT_TOKEN).build()

    conv_fallbacks = [
        CommandHandler("cancel", cancel),
        CallbackQueryHandler(conv_cancel_callback, pattern=r"^conv_cancel$"),
    ]

    setup_handler = ConversationHandler(
        entry_points=[
            CommandHandler("start", start_command),
        ],
        states={
            SETUP_TARGET: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, setup_target_save),
            ],
            SETUP_SOURCE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, setup_source_save),
            ],
            SETUP_ADMIN: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, setup_admin_save),
            ],
        },
        fallbacks=conv_fallbacks,
        allow_reentry=True,
    )

    target_handler = ConversationHandler(
        entry_points=[
            CallbackQueryHandler(menu_target, pattern=r"^menu_target$"),
        ],
        states={
            SET_TARGET: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, set_target_save)
            ],
        },
        fallbacks=conv_fallbacks,
        allow_reentry=True,
    )

    source_handler = ConversationHandler(
        entry_points=[
            CallbackQueryHandler(menu_add_source_entry, pattern=r"^menu_add_source$"),
        ],
        states={
            SET_SOURCE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, add_source_save)
            ],
        },
        fallbacks=conv_fallbacks,
        allow_reentry=True,
    )

    tag_handler = ConversationHandler(
        entry_points=[
            CallbackQueryHandler(menu_tag, pattern=r"^menu_tag$"),
        ],
        states={
            SET_TAG: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, set_tag_save)
            ],
        },
        fallbacks=conv_fallbacks,
        allow_reentry=True,
    )

    admin_handler = ConversationHandler(
        entry_points=[
            CallbackQueryHandler(menu_add_admin_entry, pattern=r"^menu_add_admin$"),
        ],
        states={
            SET_ADMIN: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, add_admin_save)
            ],
        },
        fallbacks=conv_fallbacks,
        allow_reentry=True,
    )

    app.add_handler(setup_handler)

    app.add_handler(target_handler)
    app.add_handler(source_handler)
    app.add_handler(tag_handler)
    app.add_handler(admin_handler)

    app.add_handler(CallbackQueryHandler(menu_status, pattern=r"^menu_status$"))
    app.add_handler(CallbackQueryHandler(menu_sources, pattern=r"^menu_sources$"))
    app.add_handler(CallbackQueryHandler(menu_admins, pattern=r"^menu_admins$"))
    app.add_handler(CallbackQueryHandler(menu_queue, pattern=r"^menu_queue$"))
    app.add_handler(CallbackQueryHandler(menu_settings, pattern=r"^menu_settings$"))
    app.add_handler(CallbackQueryHandler(remove_admin_cb, pattern=r"^remove_admin:"))
    app.add_handler(CallbackQueryHandler(remove_source_cb, pattern=r"^remove_source:"))
    app.add_handler(CallbackQueryHandler(preview_add_queue, pattern=r"^preview_queue:"))
    app.add_handler(CallbackQueryHandler(preview_send_now, pattern=r"^preview_send:"))
    app.add_handler(CallbackQueryHandler(preview_reject, pattern=r"^preview_reject:"))
    app.add_handler(CallbackQueryHandler(cancel_queue_cb, pattern=r"^cancel_queue:"))
    app.add_handler(CallbackQueryHandler(back_main, pattern=r"^back_main$"))

    return app


async def main():
    setup_logger()
    logger.info("Starting ContentForwardBot...")

    await get_db()

    admins = await get_admins()
    if not admins:
        for uid in settings.ADMIN_IDS:
            await add_admin(uid)
        logger.info("Populated admins from .env: {}", settings.ADMIN_IDS)

    app = build_app()
    await app.initialize()
    await app.start()
    await app.updater.start_polling(drop_pending_updates=True)

    send_preview = make_send_preview(app.bot)
    handlers.pyrogram_client = pyrogram_client

    try:
        await pyrogram_client.start(send_preview=send_preview)
        logger.info("Pyrogram client connected")
    except Exception:
        logger.warning("Pyrogram failed to connect. SourceWatcher disabled.")

    queue_worker = QueueWorker(pyrogram_client.client)
    await queue_worker.start()

    logger.info("Bot is running. Press Ctrl+C to stop.")

    stop_event = asyncio.Event()

    def _signal_handler():
        stop_event.set()

    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, _signal_handler)

    await stop_event.wait()

    logger.info("Shutting down...")
    await queue_worker.stop()
    await pyrogram_client.stop()
    await app.updater.stop()
    await app.stop()
    await app.shutdown()
    await close_db()
    logger.info("Shutdown complete")


if __name__ == "__main__":
    asyncio.run(main())
