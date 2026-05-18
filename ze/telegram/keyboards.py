from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup


def confirmation_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="✅ Yes", callback_data="confirm:yes"),
        InlineKeyboardButton(text="❌ No", callback_data="confirm:no"),
        InlineKeyboardButton(text="✏️ Edit", callback_data="confirm:edit"),
    ]])
