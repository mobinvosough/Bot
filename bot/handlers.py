from telegram import Update, Bot
from telegram.ext import (
    ContextTypes,
    ConversationHandler,
    MessageHandler,
    CallbackQueryHandler,
    CommandHandler,
    filters,
)
from datetime import datetime, timedelta
from loguru import logger

from config import settings
from core.database import (
    get_setting,
    set_setting,
    add_source_channel,
    remove_source_channel,
    get_source_channels,
    add_admin,
    remove_admin,
    get_admins,
    is_setup_complete,
    log_action,
    get_pending_by_id,
    update_pending_status,
    get_last_queue_time,
    add_to_queue,
    get_admin_username,
    get_active_queue_items,
    cancel_queue_item,
    count_pending,
    get_recent_actions,
)
from utils.cleaner import clean_and_tag
from bot.keyboards import (
    main_menu_keyboard,
    setup_source_confirm_keyboard,
    admin_list_keyboard,
    source_list_keyboard,
    settings_keyboard,
    back_to_menu_keyboard,
    preview_keyboard,
    queue_list_keyboard,
)

pyrogram_client = None

(
    SETUP_TARGET,
    SETUP_SOURCE,
    SETUP_SOURCE_CONFIRM,
    SETUP_ADMINS,
    SETUP_PHONE,
    ADD_SOURCE,
    CHANGE_TARGET,
    ADD_ADMIN,
    CHANGE_TAG,
) = range(9)


def is_admin(user_id: int) -> bool:
    return user_id in settings.ADMIN_IDS


# ── Setup conversation ──────────────────────────────────────────────

async def setup_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user = update.effective_user
    if not is_admin(user.id):
        await update.message.reply_text("Access denied.")
        return ConversationHandler.END

    if await is_setup_complete():
        await update.message.reply_text(
            "Setup already done. Use /menu to open the panel.",
            reply_markup=main_menu_keyboard(),
        )
        return ConversationHandler.END

    await log_action(user.id, "setup_started")
    await update.message.reply_text(
        "Welcome to ContentForwardBot setup.\n\n"
        "Step 1/4: Send me the Target Channel\n"
        "(username like @channel or numeric ID)"
    )
    return SETUP_TARGET


async def setup_target(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    text = update.message.text.strip()
    await set_setting("target_channel", text)
    await log_action(update.effective_user.id, f"target_set:{text}")
    await update.message.reply_text(
        f"Target channel set to: {text}\n\n"
        "Step 2/4: Send me a Source Channel\n"
        "(username or ID). You can add multiple."
    )
    return SETUP_SOURCE


async def setup_source(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    text = update.message.text.strip()
    await add_source_channel(text)
    await update.message.reply_text(
        f"Source channel added: {text}\n\n"
        "Add another source or press Done.",
        reply_markup=setup_source_confirm_keyboard(),
    )
    return SETUP_SOURCE_CONFIRM


async def setup_source_confirm_cb(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> int:
    query = update.callback_query
    await query.answer()

    if query.data == "setup_source_more":
        await query.edit_message_text("Send me the next Source Channel (username or ID).")
        return SETUP_SOURCE

    sources = await get_source_channels()
    await query.edit_message_text(
        f"Sources saved: {', '.join(sources)}\n\n"
        "Step 3/4: Send me Admin User IDs\n"
        "(one per message, or comma-separated).\n"
        "Send /done when finished."
    )
    return SETUP_ADMINS


async def setup_admins(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if update.message.text and update.message.text.strip() == "/done":
        admins = await get_admins()
        if not admins:
            for aid in settings.ADMIN_IDS:
                await add_admin(aid)
            admins = await get_admins()

        phone = settings.PHONE_NUMBER
        masked = phone[:3] + "****" + phone[-2:] if len(phone) > 5 else "****"
        await update.message.reply_text(
            f"Admins confirmed: {len(admins)} total\n\n"
            "Step 4/4: Confirm Pyrogram account\n"
            f"Phone number from .env: {masked}\n\n"
            "Press Confirm to finish setup.",
            reply_markup=setup_source_confirm_keyboard(),
        )
        return SETUP_PHONE

    text = update.message.text.strip()
    parts = [p.strip() for p in text.split(",") if p.strip().isdigit()]
    for uid in parts:
        await add_admin(int(uid))

    count = len(parts)
    await update.message.reply_text(f"Added {count} admin(s). Send more or /done.")
    return SETUP_ADMINS


async def setup_phone_cb(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()

    if query.data == "setup_source_done":
        existing = await get_setting("custom_tag")
        if not existing:
            await set_setting("custom_tag", settings.DEFAULT_CUSTOM_TAG)
        await set_setting("setup_complete", "true")
        await log_action(update.effective_user.id, "setup_completed")
        await query.edit_message_text(
            "Setup complete! Bot is ready.\nUse the menu below.",
        )
        await query.message.reply_text(
            "Main Menu", reply_markup=main_menu_keyboard()
        )
        return ConversationHandler.END

    return SETUP_PHONE


async def setup_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.message.reply_text("Setup cancelled. Run /start to begin again.")
    return ConversationHandler.END


# ── Menu entry ──────────────────────────────────────────────────────

async def menu_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user = update.effective_user
    if not is_admin(user.id):
        await update.message.reply_text("Access denied.")
        return ConversationHandler.END

    if not await is_setup_complete():
        await update.message.reply_text(
            "Bot not set up yet. Run /start to begin setup."
        )
        return ConversationHandler.END

    await update.message.reply_text("Main Menu", reply_markup=main_menu_keyboard())
    return ConversationHandler.END


# ── Main menu callbacks ─────────────────────────────────────────────

async def menu_status(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()

    target = await get_setting("target_channel") or "Not set"
    sources = await get_source_channels()
    admins = await get_admins()
    tag = await get_setting("custom_tag") or "Not set"
    queue_items = await get_active_queue_items()
    pending_count = await count_pending()
    actions = await get_recent_actions(5)

    next_post = "N/A"
    if queue_items:
        try:
            dt = datetime.fromisoformat(queue_items[0]["scheduled_time"])
            next_post = dt.strftime("%Y-%m-%d %H:%M UTC")
        except (ValueError, TypeError):
            next_post = queue_items[0]["scheduled_time"]

    text = (
        "📊 Bot Status\n\n"
        f"Target: {target}\n"
        f"Sources: {len(sources)} ({', '.join(sources) if sources else 'none'})\n"
        f"Admins: {len(admins)}\n"
        f"Queue: {len(queue_items)} items | Next: {next_post}\n"
        f"Pending messages: {pending_count}\n"
        f"Custom Tag:\n{tag}\n"
    )

    if actions:
        text += "\nLast actions:\n"
        for a in actions:
            text += f"  - {a['action']} (admin {a['admin_id']})\n"

    await query.edit_message_text(text, reply_markup=back_to_menu_keyboard())


async def menu_add_source_entry(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> int:
    query = update.callback_query
    await query.answer()
    await query.edit_message_text("Send me the Source Channel (username or ID).")
    return ADD_SOURCE


async def add_source_save(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    text = update.message.text.strip()
    await add_source_channel(text)
    await log_action(update.effective_user.id, f"source_added:{text}")
    sources = await get_source_channels()
    await update.message.reply_text(
        f"Source added: {text}\n\nCurrent sources:",
        reply_markup=source_list_keyboard(sources),
    )
    return ConversationHandler.END


async def menu_change_target_entry(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> int:
    query = update.callback_query
    await query.answer()
    current = await get_setting("target_channel") or "Not set"
    await query.edit_message_text(
        f"Current target: {current}\n\nSend me the new Target Channel (username or ID)."
    )
    return CHANGE_TARGET


async def change_target_save(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    text = update.message.text.strip()
    await set_setting("target_channel", text)
    await log_action(update.effective_user.id, f"target_changed:{text}")
    await update.message.reply_text(
        f"Target updated to: {text}", reply_markup=main_menu_keyboard()
    )
    return ConversationHandler.END


async def menu_manage_admins_entry(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> int:
    query = update.callback_query
    await query.answer()
    admins = await get_admins()
    await query.edit_message_text(
        "👥 Manage Admins", reply_markup=admin_list_keyboard(admins)
    )
    return ConversationHandler.END


async def remove_admin_cb(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    uid = int(query.data.split(":")[1])
    await remove_admin(uid)
    await log_action(update.effective_user.id, f"admin_removed:{uid}")
    admins = await get_admins()
    await query.edit_message_text(
        "👥 Manage Admins", reply_markup=admin_list_keyboard(admins)
    )


async def add_admin_entry(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    await query.edit_message_text("Send me the Admin User ID.")
    return ADD_ADMIN


async def add_admin_save(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    text = update.message.text.strip()
    if not text.isdigit():
        await update.message.reply_text("Invalid ID. Send a numeric user ID.")
        return ADD_ADMIN

    uid = int(text)
    await add_admin(uid)
    await log_action(update.effective_user.id, f"admin_added:{uid}")
    admins = await get_admins()
    await update.message.reply_text(
        "👥 Manage Admins", reply_markup=admin_list_keyboard(admins)
    )
    return ConversationHandler.END


async def menu_change_tag_entry(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> int:
    query = update.callback_query
    await query.answer()
    current = await get_setting("custom_tag") or "Not set"
    await query.edit_message_text(
        f"Current tag:\n{current}\n\nSend me the new custom tag (multi-line supported)."
    )
    return CHANGE_TAG


async def change_tag_save(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    text = update.message.text
    if text:
        text = text.strip()
    if not text:
        await update.message.reply_text("Tag cannot be empty. Send a tag or /cancel.")
        return CHANGE_TAG
    await set_setting("custom_tag", text)
    await log_action(update.effective_user.id, f"tag_changed")
    await update.message.reply_text(
        f"Tag updated to:\n{text}", reply_markup=main_menu_keyboard()
    )
    return ConversationHandler.END


async def menu_view_queue(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    items = await get_active_queue_items()
    if not items:
        await query.edit_message_text(
            "📋 Queue is empty.", reply_markup=back_to_menu_keyboard()
        )
        return
    text = f"📋 Queue ({len(items)} items)\n\n"
    for i, item in enumerate(items, 1):
        ctype = item.get("content_type", "?")
        sched = item.get("scheduled_time", "?")
        try:
            dt = datetime.fromisoformat(sched)
            sched_fmt = dt.strftime("%Y-%m-%d %H:%M UTC")
        except (ValueError, TypeError):
            sched_fmt = sched
        text += f"{i}. {ctype} — scheduled {sched_fmt}\n"
    await query.edit_message_text(text, reply_markup=queue_list_keyboard(items))


async def menu_settings(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    await query.edit_message_text("⚙️ Settings", reply_markup=settings_keyboard())


async def back_main(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    await query.edit_message_text("Main Menu", reply_markup=main_menu_keyboard())


async def remove_source_cb(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    src = query.data.split(":", 1)[1]
    await remove_source_channel(src)
    await log_action(update.effective_user.id, f"source_removed:{src}")
    sources = await get_source_channels()
    await query.edit_message_text(
        "Sources", reply_markup=source_list_keyboard(sources)
    )


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    return ConversationHandler.END


# ── Preview action callbacks ────────────────────────────────────────

ACTION_LABELS = {
    "queued": "Added to Queue",
    "sent": "Sent Now",
    "rejected": "Rejected",
}


async def _notify_other_admins(
    bot: Bot,
    acting_user_id: int,
    pending_id: int,
    action: str,
):
    admins = await get_admins()
    acting_name = await get_admin_username(acting_user_id)
    label = ACTION_LABELS.get(action, action)
    for admin in admins:
        uid = admin["user_id"]
        if uid == acting_user_id:
            continue
        try:
            await bot.send_message(
                chat_id=uid,
                text=f"Message #{pending_id} was {label} by {acting_name}.",
            )
        except Exception:
            logger.exception("Failed to notify admin {}", uid)


async def _handle_preview_action(
    update: Update,
    pending_id: int,
    action: str,
):
    query = update.callback_query
    user = update.effective_user
    acting_label = ACTION_LABELS.get(action, action)

    pending = await get_pending_by_id(pending_id)
    if not pending:
        await query.answer("Message not found.", show_alert=True)
        return

    previous_acted_by = pending.get("acted_by")

    if previous_acted_by and previous_acted_by != user.id:
        prev_name = await get_admin_username(previous_acted_by)
        prev_action = pending.get("status", "unknown")
        prev_label = ACTION_LABELS.get(prev_action, prev_action)
        await query.answer(
            f"This message was already {prev_label} by {prev_name}. "
            f"Your action ({acting_label}) will override.",
            show_alert=True,
        )

    await update_pending_status(pending_id, action, acted_by=user.id)
    await log_action(user.id, f"{action}:{pending_id}")

    await query.edit_message_reply_markup(reply_markup=None)
    await query.message.reply_text(
        f"Message #{pending_id}: {acting_label} by you."
    )

    await _notify_other_admins(query.bot, user.id, pending_id, action)


async def preview_add_queue(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    user = update.effective_user
    pending_id = int(query.data.split(":")[1])

    await _handle_preview_action(update, pending_id, "queued")

    last_time = await get_last_queue_time()

    if last_time:
        try:
            base = datetime.fromisoformat(last_time)
        except ValueError:
            base = datetime.utcnow()
    else:
        base = datetime.utcnow()

    scheduled = base + timedelta(hours=2, minutes=30)
    scheduled_str = scheduled.isoformat()

    await add_to_queue(pending_id, scheduled_str, user.id)
    await log_action(user.id, f"queue_scheduled:{pending_id}:{scheduled_str}")

    try:
        await query.message.reply_text(
            f"Scheduled for: {scheduled.strftime('%Y-%m-%d %H:%M UTC')}"
        )
    except Exception:
        pass


async def preview_send_now(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    user = update.effective_user
    pending_id = int(query.data.split(":")[1])

    pending = await get_pending_by_id(pending_id)
    if not pending:
        await query.answer("Message not found.", show_alert=True)
        return

    await _handle_preview_action(update, pending_id, "sent")

    target = await get_setting("target_channel")
    if not target:
        await query.message.reply_text("Error: No target channel configured.")
        return

    tag = await get_setting("custom_tag")
    raw_text = pending.get("text_or_caption") or ""
    text = clean_and_tag(raw_text, tag)

    content_type = pending.get("content_type", "Text")
    media_id = pending.get("media_file_id")
    source_chat = pending.get("source_channel")
    msg_id = pending.get("message_id")

    try:
        if pyrogram_client and pyrogram_client.client:
            if content_type == "Photo" and media_id:
                await pyrogram_client.client.send_photo(
                    chat_id=target, photo=media_id, caption=text
                )
            elif content_type == "Video" and media_id:
                await pyrogram_client.client.send_video(
                    chat_id=target, video=media_id, caption=text
                )
            elif source_chat and msg_id:
                from_chat = (
                    int(source_chat)
                    if source_chat.lstrip("-").isdigit()
                    else source_chat
                )
                await pyrogram_client.client.copy_message(
                    chat_id=target, from_chat_id=from_chat, message_id=msg_id
                )
            else:
                await pyrogram_client.client.send_message(
                    chat_id=target, text=text
                )
            await query.message.reply_text(f"Sent to {target}.")
        else:
            await query.message.reply_text("Error: Pyrogram client not available.")
    except Exception:
        logger.exception("Failed to forward message #{}", pending_id)
        await query.message.reply_text("Error: Failed to forward message.")


async def preview_reject(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    pending_id = int(query.data.split(":")[1])
    await _handle_preview_action(update, pending_id, "rejected")


async def cancel_queue_cb(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    qid = int(query.data.split(":")[1])
    removed = await cancel_queue_item(qid)
    await log_action(update.effective_user.id, f"queue_cancelled:{qid}")
    if removed:
        await query.edit_message_text(f"Queue item #{qid} cancelled.")
    else:
        await query.edit_message_text(f"Queue item #{qid} not found or already processed.")
    items = await get_active_queue_items()
    if items:
        await query.message.reply_text(
            "Updated queue:", reply_markup=queue_list_keyboard(items)
        )
