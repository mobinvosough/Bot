from telegram import Update
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
    get_active_queue_items,
    cancel_queue_item,
    count_pending,
    get_recent_actions,
)
from utils.cleaner import clean_and_tag
from bot.keyboards import (
    main_menu_keyboard,
    admin_list_keyboard,
    source_list_keyboard,
    back_to_menu_keyboard,
    preview_keyboard,
    queue_list_keyboard,
)

pyrogram_client = None

SET_TARGET, SET_SOURCE, SET_TAG = range(3)


def is_admin(user_id: int) -> bool:
    return user_id in settings.ADMIN_IDS


# ── /start ──────────────────────────────────────────────────────────

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    if not is_admin(user.id):
        return

    target = await get_setting("target_channel") or "Not set"
    sources = await get_source_channels()
    tag = await get_setting("custom_tag") or "Not set"

    text = (
        "ContentForwardBot\n\n"
        f"Target: {target}\n"
        f"Sources: {', '.join(sources) if sources else 'none'}\n"
        f"Tag:\n{tag}\n\n"
        "Commands:\n"
        "/set_target - Set target channel\n"
        "/add_source - Add source channel\n"
        "/list_sources - List source channels\n"
        "/set_tag - Change tag\n"
        "/status - Bot status\n"
        "/menu - Open panel"
    )
    await update.message.reply_text(text)


# ── /set_target ─────────────────────────────────────────────────────

async def set_target_entry(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if not is_admin(update.effective_user.id):
        return ConversationHandler.END
    current = await get_setting("target_channel") or "Not set"
    await update.message.reply_text(
        f"Current target: {current}\n\nSend the new Target Channel (username or ID)."
    )
    return SET_TARGET


async def set_target_save(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if not is_admin(update.effective_user.id):
        return ConversationHandler.END
    text = update.message.text.strip()
    await set_setting("target_channel", text)
    await log_action(update.effective_user.id, f"target_set:{text}")
    await update.message.reply_text(f"Target set to: {text}")
    return ConversationHandler.END


# ── /add_source ─────────────────────────────────────────────────────

async def add_source_entry(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if not is_admin(update.effective_user.id):
        return ConversationHandler.END
    await update.message.reply_text("Send the Source Channel (username or ID).")
    return SET_SOURCE


async def add_source_save(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if not is_admin(update.effective_user.id):
        return ConversationHandler.END
    text = update.message.text.strip()
    await add_source_channel(text)
    await log_action(update.effective_user.id, f"source_added:{text}")
    sources = await get_source_channels()
    await update.message.reply_text(
        f"Source added: {text}\n\nCurrent sources:",
        reply_markup=source_list_keyboard(sources),
    )
    return ConversationHandler.END


# ── /list_sources ───────────────────────────────────────────────────

async def list_sources_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not is_admin(update.effective_user.id):
        return
    sources = await get_source_channels()
    if not sources:
        await update.message.reply_text("No source channels configured.")
        return
    text = "Source channels:\n\n"
    for i, src in enumerate(sources, 1):
        text += f"{i}. {src}\n"
    await update.message.reply_text(text, reply_markup=source_list_keyboard(sources))


# ── /set_tag ────────────────────────────────────────────────────────

async def set_tag_entry(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if not is_admin(update.effective_user.id):
        return ConversationHandler.END
    current = await get_setting("custom_tag") or "Not set"
    await update.message.reply_text(
        f"Current tag:\n{current}\n\nSend the new custom tag."
    )
    return SET_TAG


async def set_tag_save(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if not is_admin(update.effective_user.id):
        return ConversationHandler.END
    text = update.message.text
    if text:
        text = text.strip()
    if not text:
        await update.message.reply_text("Tag cannot be empty. Send a tag or /cancel.")
        return SET_TAG
    await set_setting("custom_tag", text)
    await log_action(update.effective_user.id, "tag_changed")
    await update.message.reply_text(f"Tag updated to:\n{text}")
    return ConversationHandler.END


# ── /menu ───────────────────────────────────────────────────────────

async def menu_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not is_admin(update.effective_user.id):
        return
    await update.message.reply_text("Main Menu", reply_markup=main_menu_keyboard())


# ── Menu callbacks ──────────────────────────────────────────────────

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
        "Bot Status\n\n"
        f"Target: {target}\n"
        f"Sources: {len(sources)} ({', '.join(sources) if sources else 'none'})\n"
        f"Admins: {len(admins)}\n"
        f"Queue: {len(queue_items)} items | Next: {next_post}\n"
        f"Pending messages: {pending_count}\n"
        f"Tag:\n{tag}\n"
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
    return SET_SOURCE


async def menu_change_target_entry(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> int:
    query = update.callback_query
    await query.answer()
    current = await get_setting("target_channel") or "Not set"
    await query.edit_message_text(
        f"Current target: {current}\n\nSend me the new Target Channel (username or ID)."
    )
    return SET_TARGET


async def menu_manage_admins_entry(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    query = update.callback_query
    await query.answer()
    admins = await get_admins()
    await query.edit_message_text(
        "Manage Admins", reply_markup=admin_list_keyboard(admins)
    )


async def remove_admin_cb(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    uid = int(query.data.split(":")[1])
    await remove_admin(uid)
    await log_action(update.effective_user.id, f"admin_removed:{uid}")
    admins = await get_admins()
    await query.edit_message_text(
        "Manage Admins", reply_markup=admin_list_keyboard(admins)
    )


async def add_admin_entry(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    await query.edit_message_text("Send me the Admin User ID.")


async def menu_change_tag_entry(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> int:
    query = update.callback_query
    await query.answer()
    current = await get_setting("custom_tag") or "Not set"
    await query.edit_message_text(
        f"Current tag:\n{current}\n\nSend me the new custom tag (multi-line supported)."
    )
    return SET_TAG


async def menu_view_queue(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    items = await get_active_queue_items()
    if not items:
        await query.edit_message_text(
            "Queue is empty.", reply_markup=back_to_menu_keyboard()
        )
        return
    text = f"Queue ({len(items)} items)\n\n"
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
    await query.edit_message_text("Settings", reply_markup=back_to_menu_keyboard())


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
        await query.answer(
            f"This message was already {ACTION_LABELS.get(pending.get('status', ''), pending.get('status', 'acted on'))} by another admin.",
            show_alert=True,
        )
        return

    await update_pending_status(pending_id, action, acted_by=user.id)
    await log_action(user.id, f"{action}:{pending_id}")

    await query.edit_message_reply_markup(reply_markup=None)
    await query.message.reply_text(
        f"Message #{pending_id}: {acting_label} by you."
    )


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
