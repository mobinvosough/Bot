from telegram import InlineKeyboardButton, InlineKeyboardMarkup


def main_menu_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("📊 Status", callback_data="menu_status"),
                InlineKeyboardButton("➕ Add Source", callback_data="menu_add_source"),
            ],
            [
                InlineKeyboardButton("🎯 Change Target", callback_data="menu_change_target"),
                InlineKeyboardButton("👥 Manage Admins", callback_data="menu_manage_admins"),
            ],
            [
                InlineKeyboardButton("📝 Change Tag", callback_data="menu_change_tag"),
                InlineKeyboardButton("📋 View Queue", callback_data="menu_view_queue"),
            ],
            [
                InlineKeyboardButton("⚙️ Settings", callback_data="menu_settings"),
            ],
        ]
    )


def setup_source_confirm_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("Done", callback_data="setup_source_done"),
                InlineKeyboardButton("Add More", callback_data="setup_source_more"),
            ]
        ]
    )


def admin_list_keyboard(admins: list[dict]) -> InlineKeyboardMarkup:
    rows = []
    for admin in admins:
        label = f"@{admin['username']}" if admin["username"] else str(admin["user_id"])
        rows.append(
            [InlineKeyboardButton(f"❌ {label}", callback_data=f"remove_admin:{admin['user_id']}")]
        )
    rows.append([InlineKeyboardButton("➕ Add Admin", callback_data="add_admin")])
    rows.append([InlineKeyboardButton("◀️ Back", callback_data="back_main")])
    return InlineKeyboardMarkup(rows)


def source_list_keyboard(sources: list[str]) -> InlineKeyboardMarkup:
    rows = []
    for src in sources:
        rows.append(
            [InlineKeyboardButton(f"❌ {src}", callback_data=f"remove_source:{src}")]
        )
    rows.append([InlineKeyboardButton("➕ Add Source", callback_data="add_source")])
    rows.append([InlineKeyboardButton("◀️ Back", callback_data="back_main")])
    return InlineKeyboardMarkup(rows)


def settings_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("◀️ Back", callback_data="back_main")],
        ]
    )


def confirm_keyboard(callback_prefix: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("✅ Yes", callback_data=f"{callback_prefix}:yes"),
                InlineKeyboardButton("❌ No", callback_data=f"{callback_prefix}:no"),
            ]
        ]
    )


def back_to_menu_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [[InlineKeyboardButton("◀️ Back to Menu", callback_data="back_main")]]
    )
