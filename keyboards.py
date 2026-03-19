from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

def main_menu():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📊 Бюджет", callback_data="budget")],
        [InlineKeyboardButton(text="🏋️ Привычки", callback_data="habits")],
        [InlineKeyboardButton(text="👨‍👩‍👧 Семья", callback_data="family")]
    ])

def budget_menu():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💸 Расход", callback_data="expense")],
        [InlineKeyboardButton(text="💰 Доход", callback_data="income")],
        [InlineKeyboardButton(text="📈 Аналитика", callback_data="stats")],
        [InlineKeyboardButton(text="📚 Категории", callback_data="cats")]
    ])