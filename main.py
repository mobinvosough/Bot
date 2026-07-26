import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

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
from core.database import get_db, close_db
from bot.handlers import (
    SETUP_TARGET,
    SETUP_SOURCE,
    SETUP_SOURCE_CONFIRM,
    SETUP_ADMINS,
    SETUP_PHONE,
    ADD_SOURCE,
    CHANGE_TARGET,
    ADD_ADMIN,
    CHANGE_TAG,
    setup_start,
    setup_target,
    setup_source,
    setup_source_confirm_cb,
    setup_admins,
    setup_phone_cb,
    setup_cancel,
    menu_command,
    menu_status,
    menu_add_source_entry,
    add_source_save,
    menu_change_target_entry,
    change_target_save,
    menu_manage_admins_entry,
    remove_admin_cb,
    add_admin_entry,
    add_admin_save,
    menu_change_tag_entry,
    change_tag_save,
    menu_view_queue,
    menu_settings,
    back_main,
    remove_source_cb,
    cancel,
)


def build_app() -> Application:
    app = Application.builder().token(settings.BOT_TOKEN).build()

    setup_handler = ConversationHandler(
        entry_points=[CommandHandler("start", setup_start)],
        states={
            SETUP_TARGET: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, setup_target)
            ],
            SETUP_SOURCE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, setup_source)
            ],
            SETUP_SOURCE_CONFIRM: [
                CallbackQueryHandler(setup_source_confirm_cb, pattern=r"^setup_source_")
            ],
            SETUP_ADMINS: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, setup_admins),
            ],
            SETUP_PHONE: [
                CallbackQueryHandler(setup_phone_cb, pattern=r"^setup_source_")
            ],
        },
        fallbacks=[
            CommandHandler("cancel", setup_cancel),
            CommandHandler("start", setup_start),
        ],
        allow_reentry=True,
    )

    menu_handler = ConversationHandler(
        entry_points=[
            CommandHandler("menu", menu_command),
            CallbackQueryHandler(back_main, pattern=r"^back_main$"),
        ],
        states={
            CHANGE_TARGET: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, change_target_save)
            ],
            ADD_SOURCE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, add_source_save)
            ],
            ADD_ADMIN: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, add_admin_save)
            ],
            CHANGE_TAG: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, change_tag_save)
            ],
        },
        fallbacks=[
            CommandHandler("cancel", cancel),
            CommandHandler("start", setup_start),
        ],
        allow_reentry=True,
    )

    app.add_handler(setup_handler)
    app.add_handler(menu_handler)

    app.add_handler(CallbackQueryHandler(menu_status, pattern=r"^menu_status$"))
    app.add_handler(
        CallbackQueryHandler(menu_add_source_entry, pattern=r"^menu_add_source$")
    )
    app.add_handler(
        CallbackQueryHandler(menu_change_target_entry, pattern=r"^menu_change_target$")
    )
    app.add_handler(
        CallbackQueryHandler(menu_manage_admins_entry, pattern=r"^menu_manage_admins$")
    )
    app.add_handler(
        CallbackQueryHandler(menu_change_tag_entry, pattern=r"^menu_change_tag$")
    )
    app.add_handler(
        CallbackQueryHandler(menu_view_queue, pattern=r"^menu_view_queue$")
    )
    app.add_handler(
        CallbackQueryHandler(menu_settings, pattern=r"^menu_settings$")
    )
    app.add_handler(
        CallbackQueryHandler(remove_admin_cb, pattern=r"^remove_admin:")
    )
    app.add_handler(
        CallbackQueryHandler(add_admin_entry, pattern=r"^add_admin$")
    )
    app.add_handler(
        CallbackQueryHandler(remove_source_cb, pattern=r"^remove_source:")
    )

    return app


async def main():
    setup_logger()
    logger.info("Starting ContentForwardBot...")

    await get_db()

    app = build_app()
    logger.info("Bot polling starting...")
    await app.initialize()
    await app.start()
    await app.updater.start_polling(drop_pending_updates=True)

    logger.info("Bot is running. Press Ctrl+C to stop.")

    stop_event = asyncio.Event()

    def _signal_handler():
        stop_event.set()

    try:
        import signal
        loop = asyncio.get_running_loop()
        for sig in (signal.SIGINT, signal.SIGTERM):
            loop.add_signal_handler(sig, _signal_handler)
    except NotImplementedError:
        pass

    await stop_event.wait()

    logger.info("Shutting down...")
    await app.updater.stop()
    await app.stop()
    await app.shutdown()
    await close_db()
    logger.info("Shutdown complete")


if __name__ == "__main__":
    asyncio.run(main())
