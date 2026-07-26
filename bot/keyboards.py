from datetime import datetime
from telegram import InlineKeyboardButton, InlineKeyboardMarkup


def main_menu_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("📊 Status", callback_data="menu_status"),
            InlineKeyboardButton("📢 Sources", callback_data="menu_sources"),
        ],
        [
            InlineKeyboardButton("🎯 Target Channel", callback_data="menu_target"),
            InlineKeyboardButton("👥 Admins", callback_data="menu_admins"),
        ],
        [
            InlineKeyboardButton("📝 Custom Tag", callback_data="menu_tag"),
            InlineKeyboardButton("📋 Queue", callback_data="menu_queue"),
        ],
        [
            InlineKeyboardButton("🧹 Clean DB", callback_data="menu_clean"),
            InlineKeyboardButton("⚙️ Settings", callback_data="menu_settings"),
        ],
    ])


def source_list_keyboard(sources: list[str]) -> InlineKeyboardMarkup:
    rows = []
    for src in sources:
        rows.append([InlineKeyboardButton(f"🗑 {src}", callback_data=f"remove_source:{src}")])
    rows.append([InlineKeyboardButton("➕ Add Source", callback_data="menu_add_source")])
    rows.append([InlineKeyboardButton("🔙 Back", callback_data="back_main")])
    return InlineKeyboardMarkup(rows)


def admin_list_keyboard(admins: list[dict]) -> InlineKeyboardMarkup:
    rows = []
    for admin in admins:
        label = f"@{admin['username']}" if admin["username"] else str(admin["user_id"])
        rows.append([InlineKeyboardButton(f"🗑 {label}", callback_data=f"remove_admin:{admin['user_id']}")])
    rows.append([InlineKeyboardButton("➕ Add Admin", callback_data="menu_add_admin")])
    rows.append([InlineKeyboardButton("🔙 Back", callback_data="back_main")])
    return InlineKeyboardMarkup(rows)


def back_to_menu_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🔙 Back to Menu", callback_data="back_main")],
    ])


def cancel_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🚫 Cancel", callback_data="conv_cancel")],
    ])


def preview_keyboard(pending_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("➕ Add to Queue", callback_data=f"preview_queue:{pending_id}")],
        [
            InlineKeyboardButton("🚀 Send Now", callback_data=f"preview_send:{pending_id}"),
            InlineKeyboardButton("❌ Reject", callback_data=f"preview_reject:{pending_id}"),
        ],
    ])


def queue_list_keyboard(items: list[dict]) -> InlineKeyboardMarkup:
    rows = []
    for item in items:
        qid = item["queue_id"]
        ctype = item.get("content_type", "?")
        sched = item.get("scheduled_time", "?")
        try:
            dt = datetime.fromisoformat(sched)
            label = f"{ctype} | {dt.strftime('%m-%d %H:%M')}"
        except (ValueError, TypeError):
            label = f"{ctype} | {sched}"
        rows.append([InlineKeyboardButton(f"🗑 {label}", callback_data=f"cancel_queue:{qid}")])
    rows.append([InlineKeyboardButton("🔙 Back", callback_data="back_main")])
    return InlineKeyboardMarkup(rows)


def setup_target_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🚫 Cancel Setup", callback_data="conv_cancel")],
    ])


def clean_confirm_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("✅ Yes, Clean", callback_data="confirm_clean"),
            InlineKeyboardButton("❌ No", callback_data="back_main"),
        ],
    ])
