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
import json
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
    is_setup_complete,
    get_clean_stats,
    clean_old_messages,
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
    setup_target_keyboard,
    clean_confirm_keyboard,
)

pyrogram_client = None

SET_TARGET, SET_SOURCE, SET_TAG, SET_ADMIN, SETUP_TARGET, SETUP_SOURCE, SETUP_ADMIN = range(7)


async def is_admin(user_id: int) -> bool:
    if user_id in settings.ADMIN_IDS:
        return True
    admins = await get_admins()
    return any(a["user_id"] == user_id for a in admins)


# ── /start ──────────────────────────────────────────────────────────


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user = update.effective_user
    if not await is_admin(user.id):
        return

    setup_done = await is_setup_complete()
    if not setup_done:
        return await _start_setup(update, context)

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
    return ConversationHandler.END


# ── Initial Setup Flow ──────────────────────────────────────────────


async def _start_setup(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.message.reply_text(
        "👋 Welcome! Let's set up your bot.\n\n"
        "Step 1/3: Send the <b>Target Channel</b> (username or ID)\n"
        "where approved messages will be posted.",
        reply_markup=setup_target_keyboard(),
    )
    return SETUP_TARGET


async def setup_target_save(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if not await is_admin(update.effective_user.id):
        return ConversationHandler.END
    text = update.message.text.strip()
    await set_setting("target_channel", text)
    await log_action(update.effective_user.id, f"setup_target:{text}")
    await update.message.reply_text(
        f"✅ Target set to: {text}\n\n"
        "Step 2/3: Send a <b>Source Channel</b> (username or ID)\n"
        "You can add more later from the menu.",
    )
    return SETUP_SOURCE


async def setup_source_save(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if not await is_admin(update.effective_user.id):
        return ConversationHandler.END
    text = update.message.text.strip()
    await add_source_channel(text)
    await log_action(update.effective_user.id, f"setup_source:{text}")
    await update.message.reply_text(
        f"✅ Source added: {text}\n\n"
        "Step 3/3: Send an <b>Admin User ID</b> to manage the bot.\n"
        "You can add more later from the menu.",
    )
    return SETUP_ADMIN


async def setup_admin_save(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if not await is_admin(update.effective_user.id):
        return ConversationHandler.END
    text = update.message.text.strip()
    try:
        uid = int(text)
    except ValueError:
        await update.message.reply_text("❌ Invalid ID. Send a numeric User ID or /cancel.")
        return SETUP_ADMIN
    await add_admin(uid)
    await set_setting("setup_complete", "true")
    await log_action(update.effective_user.id, f"setup_admin:{uid}")
    await update.message.reply_text(
        "✅ Setup complete!\n\n"
        "The bot is now monitoring your source channels.\n"
        "Use /start to open the main menu.",
        reply_markup=back_to_menu_keyboard(),
    )
    return ConversationHandler.END


# ── Target conversation ─────────────────────────────────────────────


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
    if not await is_admin(update.effective_user.id):
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
    if not await is_admin(update.effective_user.id):
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
    if not await is_admin(update.effective_user.id):
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
    if not await is_admin(update.effective_user.id):
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
    tag = await get_setting("custom_tag") or "Not set"
    await query.edit_message_text(
        "⚙️ Settings\n"
        "━━━━━━━━━━━━━━━━━━━━\n\n"
        f"📝 Custom Tag:\n{tag}\n\n"
        "Use the menu to change settings.",
        reply_markup=back_to_menu_keyboard(),
    )


async def menu_clean(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    stats = await get_clean_stats()

    if stats["total"] == 0:
        await query.edit_message_text(
            "🧹 Clean Database\n"
            "━━━━━━━━━━━━━━━━━━━━\n\n"
            "Nothing to clean. Database is already tidy.",
            reply_markup=back_to_menu_keyboard(),
        )
        return

    text = (
        "🧹 Clean Database\n"
        "━━━━━━━━━━━━━━━━━━━━\n\n"
        f"This will remove all old messages before the last accepted post.\n\n"
        f"🗑 Pending: {stats['pending']}\n"
        f"🗑 Rejected: {stats['rejected']}\n"
        f"🗑 Queue (old): {stats['queue']}\n"
        f"📊 Total: {stats['total']} items\n\n"
        "⚠️ This cannot be undone. Continue?"
    )
    await query.edit_message_text(text, reply_markup=clean_confirm_keyboard())


async def confirm_clean(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    user = update.effective_user
    await query.answer("Cleaning...")

    stats = await clean_old_messages()
    await log_action(user.id, f"clean_db:{stats.get('total', 0)}")

    await query.edit_message_text(
        "🧹 Clean Complete\n"
        "━━━━━━━━━━━━━━━━━━━━\n\n"
        f"Removed {stats.get('total', 0)} old items from database.\n\n"
        "✅ Database is now clean.",
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


async def preview_add_queue(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    user = update.effective_user
    pending_id = int(query.data.split(":")[1])

    pending = await get_pending_by_id(pending_id)
    if not pending:
        await query.answer(
            "⚠️ This message has been cleaned from the database and is no longer available.",
            show_alert=True,
        )
        try:
            await query.edit_message_reply_markup(reply_markup=None)
        except Exception:
            pass
        return

    previous_status = pending.get("status")
    if previous_status in ("queued", "sent", "rejected"):
        acted_by = pending.get("acted_by")
        if acted_by and acted_by != user.id:
            await query.answer(
                f"This message was already {ACTION_LABELS.get(previous_status, previous_status)} by another admin.",
                show_alert=True,
            )
            return

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

    queue_id = await add_to_queue(pending_id, scheduled_str, user.id)
    await update_pending_status(pending_id, "queued", acted_by=user.id)
    await log_action(user.id, f"queue_scheduled:{pending_id}:{scheduled_str}")

    await query.edit_message_reply_markup(reply_markup=None)
    await query.message.reply_text(
        f"Message #{pending_id}: Added to Queue by you.\n"
        f"⏰ Scheduled for: {scheduled.strftime('%Y-%m-%d %H:%M UTC')}"
    )


async def preview_send_now(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    user = update.effective_user
    pending_id = int(query.data.split(":")[1])

    pending = await get_pending_by_id(pending_id)
    if not pending:
        await query.answer(
            "⚠️ This message has been cleaned from the database and is no longer available.",
            show_alert=True,
        )
        try:
            await query.edit_message_reply_markup(reply_markup=None)
        except Exception:
            pass
        return

    previous_status = pending.get("status")
    if previous_status in ("queued", "sent", "rejected"):
        acted_by = pending.get("acted_by")
        if acted_by and acted_by != user.id:
            await query.answer(
                f"This message was already {ACTION_LABELS.get(previous_status, previous_status)} by another admin.",
                show_alert=True,
            )
            return

    target = await get_setting("target_channel")
    if not target:
        await query.answer("No target channel configured.", show_alert=True)
        return

    tag = await get_setting("custom_tag")
    raw_text = pending.get("text_or_caption") or ""
    text = clean_and_tag(raw_text, tag)

    content_type = pending.get("content_type", "Text")
    media_id = pending.get("media_file_id")

    try:
        await query.answer("Sending...")
    except Exception:
        pass

    try:
        if not (pyrogram_client and pyrogram_client.client):
            await query.answer("Pyrogram client not available.", show_alert=True)
            return

        client = pyrogram_client.client

        if content_type.startswith("Album") and media_id:
            from pyrogram.types import InputMediaPhoto, InputMediaVideo
            media_items = json.loads(media_id)
            group = []
            for i, item in enumerate(media_items):
                cap = text if i == 0 else ""
                if item["type"] == "photo":
                    group.append(InputMediaPhoto(media=item["file_id"], caption=cap))
                elif item["type"] == "video":
                    group.append(InputMediaVideo(media=item["file_id"], caption=cap))
            logger.info("Send Now #{}: sending Album ({}) to {}", pending_id, len(group), target)
            await client.send_media_group(chat_id=target, media=group)
        elif content_type == "Photo" and media_id:
            logger.info("Send Now #{}: sending Photo via file_id to {}", pending_id, target)
            await client.send_photo(chat_id=target, photo=media_id, caption=text)
        elif content_type == "Video" and media_id:
            logger.info("Send Now #{}: sending Video via file_id to {}", pending_id, target)
            await client.send_video(chat_id=target, video=media_id, caption=text)
        else:
            logger.info("Send Now #{}: sending Text to {}", pending_id, target)
            await client.send_message(chat_id=target, text=text)

        await update_pending_status(pending_id, "sent", acted_by=user.id)
        await log_action(user.id, f"send_now:{pending_id}")

        await query.edit_message_reply_markup(reply_markup=None)
        await query.message.reply_text(
            f"Message #{pending_id}: Sent Now by you.\n"
            f"Delivered to: {target}"
        )
    except Exception:
        logger.exception("Failed to forward message #{}", pending_id)
        try:
            await query.answer("Failed to forward message.", show_alert=True)
        except Exception:
            pass


async def preview_reject(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    user = update.effective_user
    pending_id = int(query.data.split(":")[1])

    pending = await get_pending_by_id(pending_id)
    if not pending:
        await query.answer(
            "⚠️ This message has been cleaned from the database and is no longer available.",
            show_alert=True,
        )
        try:
            await query.edit_message_reply_markup(reply_markup=None)
        except Exception:
            pass
        return

    previous_status = pending.get("status")
    if previous_status in ("queued", "sent", "rejected"):
        acted_by = pending.get("acted_by")
        if acted_by and acted_by != user.id:
            await query.answer(
                f"This message was already {ACTION_LABELS.get(previous_status, previous_status)} by another admin.",
                show_alert=True,
            )
            return

    await update_pending_status(pending_id, "rejected", acted_by=user.id)
    await log_action(user.id, f"reject:{pending_id}")

    await query.edit_message_reply_markup(reply_markup=None)
    await query.message.reply_text(
        f"Message #{pending_id}: Rejected by you."
    )


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
