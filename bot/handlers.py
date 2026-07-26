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
    cancel_keyboard,
)

pyrogram_client = None

SET_TARGET, SET_SOURCE, SET_TAG, SET_ADMIN = range(4)


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
    admins = await get_admins()
    queue_items = await get_active_queue_items()

    text = (
        "📋 ContentForwardBot\n"
        "━━━━━━━━━━━━━━━━━━━━\n\n"
        f"🎯 Target: {target}\n"
        f"📢 Sources: {len(sources)}\n"
        f"👥 Admins: {len(admins)}\n"
        f"📝 Tag: {tag}\n"
        f"📋 Queue: {len(queue_items)} items\n\n"
        "Use the menu below to manage the bot."
    )
    await update.message.reply_text(text, reply_markup=main_menu_keyboard())


# ── Target conversation ─────────────────────────────────────────────


async def set_target_entry(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if not is_admin(update.effective_user.id):
        return ConversationHandler.END
    current = await get_setting("target_channel") or "Not set"
    await update.message.reply_text(
        f"Current target: {current}\n\nSend the new Target Channel (username or ID)."
    )
    return SET_TARGET


async def menu_target(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    current = await get_setting("target_channel") or "Not set"
    await query.edit_message_text(
        "🎯 Target Channel\n"
        "━━━━━━━━━━━━━━━━━━━━\n\n"
        f"Current: {current}\n\n"
        "Send the new Target Channel (username or ID).",
        reply_markup=cancel_keyboard(),
    )
    return SET_TARGET


async def set_target_save(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if not is_admin(update.effective_user.id):
        return ConversationHandler.END
    text = update.message.text.strip()
    await set_setting("target_channel", text)
    await log_action(update.effective_user.id, f"target_set:{text}")
    await update.message.reply_text(
        f"✅ Target channel updated to: {text}",
        reply_markup=back_to_menu_keyboard(),
    )
    return ConversationHandler.END


# ── Source conversation ─────────────────────────────────────────────


async def add_source_entry(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if not is_admin(update.effective_user.id):
        return ConversationHandler.END
    await update.message.reply_text("Send the Source Channel (username or ID).")
    return SET_SOURCE


async def menu_add_source_entry(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    await query.edit_message_text(
        "➕ Add Source\n"
        "━━━━━━━━━━━━━━━━━━━━\n\n"
        "Send the Source Channel (username or ID).",
        reply_markup=cancel_keyboard(),
    )
    return SET_SOURCE


async def add_source_save(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if not is_admin(update.effective_user.id):
        return ConversationHandler.END
    text = update.message.text.strip()
    await add_source_channel(text)
    await log_action(update.effective_user.id, f"source_added:{text}")
    sources = await get_source_channels()
    await update.message.reply_text(
        f"✅ Source added: {text}",
        reply_markup=source_list_keyboard(sources),
    )
    return ConversationHandler.END


# ── Tag conversation ────────────────────────────────────────────────


async def set_tag_entry(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if not is_admin(update.effective_user.id):
        return ConversationHandler.END
    current = await get_setting("custom_tag") or "Not set"
    await update.message.reply_text(
        f"Current tag:\n{current}\n\nSend the new custom tag."
    )
    return SET_TAG


async def menu_tag(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    current = await get_setting("custom_tag") or "Not set"
    await query.edit_message_text(
        "📝 Custom Tag\n"
        "━━━━━━━━━━━━━━━━━━━━\n\n"
        f"Current tag:\n{current}\n\n"
        "Send the new custom tag (multi-line supported).",
        reply_markup=cancel_keyboard(),
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
    await update.message.reply_text(
        f"✅ Tag updated to:\n{text}",
        reply_markup=back_to_menu_keyboard(),
    )
    return ConversationHandler.END


# ── Admin conversation ──────────────────────────────────────────────


async def menu_add_admin_entry(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    await query.edit_message_text(
        "➕ Add Admin\n"
        "━━━━━━━━━━━━━━━━━━━━\n\n"
        "Send the Admin User ID.",
        reply_markup=cancel_keyboard(),
    )
    return SET_ADMIN


async def add_admin_save(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if not is_admin(update.effective_user.id):
        return ConversationHandler.END
    text = update.message.text.strip()
    try:
        uid = int(text)
    except ValueError:
        await update.message.reply_text(
            "❌ Invalid User ID. Send a numeric ID or /cancel."
        )
        return SET_ADMIN
    await add_admin(uid)
    await log_action(update.effective_user.id, f"admin_added:{uid}")
    admins = await get_admins()
    await update.message.reply_text(
        f"✅ Admin added: {uid}",
        reply_markup=admin_list_keyboard(admins),
    )
    return ConversationHandler.END


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
        "📊 Bot Status\n"
        "━━━━━━━━━━━━━━━━━━━━\n\n"
        f"🎯 Target: {target}\n"
        f"📢 Sources: {len(sources)}\n"
        f"👥 Admins: {len(admins)}\n"
        f"📝 Tag: {tag}\n\n"
        f"📋 Queue: {len(queue_items)} items\n"
        f"⏰ Next post: {next_post}\n"
        f"📨 Pending: {pending_count}\n"
    )

    if actions:
        text += "\n📜 Recent actions:\n"
        for a in actions:
            text += f"  • {a['action']} (admin {a['admin_id']})\n"

    await query.edit_message_text(text, reply_markup=back_to_menu_keyboard())


async def menu_sources(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    sources = await get_source_channels()

    if sources:
        text = f"📢 Source Channels ({len(sources)})\n━━━━━━━━━━━━━━━━━━━━\n"
        for i, src in enumerate(sources, 1):
            text += f"\n{i}. {src}"
        text += "\n\nRemove a source with the buttons below."
    else:
        text = (
            "📢 Source Channels\n"
            "━━━━━━━━━━━━━━━━━━━━\n\n"
            "No sources configured.\nTap 'Add Source' to add one."
        )

    await query.edit_message_text(text, reply_markup=source_list_keyboard(sources))


async def menu_admins(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    admins = await get_admins()

    if admins:
        text = f"👥 Admins ({len(admins)})\n━━━━━━━━━━━━━━━━━━━━\n"
        for i, admin in enumerate(admins, 1):
            label = f"@{admin['username']}" if admin["username"] else str(admin["user_id"])
            text += f"\n{i}. {label}"
        text += "\n\nRemove an admin with the buttons below."
    else:
        text = (
            "👥 Admins\n"
            "━━━━━━━━━━━━━━━━━━━━\n\n"
            "No admins configured.\nTap 'Add Admin' to add one."
        )

    await query.edit_message_text(text, reply_markup=admin_list_keyboard(admins))


async def menu_queue(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    items = await get_active_queue_items()
    if not items:
        await query.edit_message_text(
            "📋 Queue\n"
            "━━━━━━━━━━━━━━━━━━━━\n\n"
            "Queue is empty.",
            reply_markup=back_to_menu_keyboard(),
        )
        return

    text = f"📋 Queue ({len(items)} items)\n━━━━━━━━━━━━━━━━━━━━\n"
    for i, item in enumerate(items, 1):
        ctype = item.get("content_type", "?")
        sched = item.get("scheduled_time", "?")
        try:
            dt = datetime.fromisoformat(sched)
            sched_fmt = dt.strftime("%Y-%m-%d %H:%M UTC")
        except (ValueError, TypeError):
            sched_fmt = sched
        text += f"\n{i}. {ctype} — {sched_fmt}"
    text += "\n\nRemove an item with the buttons below."
    await query.edit_message_text(text, reply_markup=queue_list_keyboard(items))


async def menu_settings(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    await query.edit_message_text(
        "⚙️ Settings\n"
        "━━━━━━━━━━━━━━━━━━━━\n\n"
        "No settings available yet.",
        reply_markup=back_to_menu_keyboard(),
    )


# ── Navigation callbacks ────────────────────────────────────────────


async def back_main(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    await query.edit_message_text(
        "📋 ContentForwardBot\n━━━━━━━━━━━━━━━━━━━━",
        reply_markup=main_menu_keyboard(),
    )


async def remove_admin_cb(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    uid = int(query.data.split(":")[1])
    await remove_admin(uid)
    await log_action(update.effective_user.id, f"admin_removed:{uid}")
    admins = await get_admins()
    if admins:
        text = f"👥 Admins ({len(admins)})\n━━━━━━━━━━━━━━━━━━━━\n"
        for i, admin in enumerate(admins, 1):
            label = f"@{admin['username']}" if admin["username"] else str(admin["user_id"])
            text += f"\n{i}. {label}"
        text += "\n\nRemove an admin with the buttons below."
    else:
        text = (
            "👥 Admins\n"
            "━━━━━━━━━━━━━━━━━━━━\n\n"
            "No admins configured.\nTap 'Add Admin' to add one."
        )
    await query.edit_message_text(text, reply_markup=admin_list_keyboard(admins))


async def remove_source_cb(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    src = query.data.split(":", 1)[1]
    await remove_source_channel(src)
    await log_action(update.effective_user.id, f"source_removed:{src}")
    sources = await get_source_channels()
    if sources:
        text = f"📢 Source Channels ({len(sources)})\n━━━━━━━━━━━━━━━━━━━━\n"
        for i, s in enumerate(sources, 1):
            text += f"\n{i}. {s}"
        text += "\n\nRemove a source with the buttons below."
    else:
        text = (
            "📢 Source Channels\n"
            "━━━━━━━━━━━━━━━━━━━━\n\n"
            "No sources configured.\nTap 'Add Source' to add one."
        )
    await query.edit_message_text(text, reply_markup=source_list_keyboard(sources))


# ── Cancel / fallback ───────────────────────────────────────────────


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.message.reply_text(
        "🚫 Cancelled.", reply_markup=back_to_menu_keyboard()
    )
    return ConversationHandler.END


async def conv_cancel_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    await query.edit_message_text(
        "🚫 Cancelled.", reply_markup=back_to_menu_keyboard()
    )
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
    items = await get_active_queue_items()
    if items:
        text = f"📋 Queue ({len(items)} items)\n━━━━━━━━━━━━━━━━━━━━\n"
        for i, item in enumerate(items, 1):
            ctype = item.get("content_type", "?")
            sched = item.get("scheduled_time", "?")
            try:
                dt = datetime.fromisoformat(sched)
                sched_fmt = dt.strftime("%Y-%m-%d %H:%M UTC")
            except (ValueError, TypeError):
                sched_fmt = sched
            text += f"\n{i}. {ctype} — {sched_fmt}"
        text += "\n\nRemove an item with the buttons below."
        await query.edit_message_text(text, reply_markup=queue_list_keyboard(items))
    else:
        await query.edit_message_text(
            "📋 Queue\n"
            "━━━━━━━━━━━━━━━━━━━━\n\n"
            "Queue is empty.",
            reply_markup=back_to_menu_keyboard(),
        )
