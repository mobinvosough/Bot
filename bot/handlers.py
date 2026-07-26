from telegram import Update, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import ContextTypes
from loguru import logger


def main_menu_keyboard():
    keyboard = [
        [KeyboardButton("Settings"), KeyboardButton("Queue")],
        [KeyboardButton("Sources"), KeyboardButton("Logs")],
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    logger.info("User {} started bot", user.id)
    await update.message.reply_text(
        "Welcome to ContentForwardBot.\nUse the menu below to manage settings.",
        reply_markup=main_menu_keyboard(),
    )
