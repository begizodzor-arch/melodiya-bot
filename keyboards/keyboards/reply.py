from aiogram.types import ReplyKeyboardMarkup, KeyboardButton


def get_main_menu_keyboard(is_admin: bool = False) -> ReplyKeyboardMarkup:
    """Asosiy pastki menyu tugmalari."""
    keyboard = [
        [KeyboardButton(text="🔍 Qo'shiq qidirish")],
        [KeyboardButton(text="🔥 Trend musiqalar"), KeyboardButton(text="⭐️ Sevimlilar")],
        [KeyboardButton(text="👥 Do'stlarni taklif qilish"), KeyboardButton(text="ℹ️ Bot haqida / Yordam")]
    ]
    if is_admin:
        keyboard.append([KeyboardButton(text="⚙️ Admin panel")])

    return ReplyKeyboardMarkup(
        keyboard=keyboard,
        resize_keyboard=True,
        is_persistent=True
    )
