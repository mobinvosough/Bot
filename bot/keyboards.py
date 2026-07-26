from telegram import InlineKeyboardButton, InlineKeyboardMarkup


def confirm_keyboard(action: str, item_id: int):
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("Approve", callback_data=f"approve:{item_id}"),
                InlineKeyboardButton("Reject", callback_data=f"reject:{item_id}"),
            ]
        ]
    )


def settings_keyboard():
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("Add Source", callback_data="add_source")],
            [InlineKeyboardButton("Remove Source", callback_data="remove_source")],
            [InlineKeyboardButton("Back", callback_data="back_main")],
        ]
    )
