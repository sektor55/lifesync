from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

def main_menu():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📊 Бюджет", callback_data="budget")],
        [InlineKeyboardButton(text="🏋️ Привычки", callback_data="habits")],
        [InlineKeyboardButton(text="👨‍👩‍👧 Семья", callback_data="family")],
    ])

def budget_menu():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💸 Расход", callback_data="expense")],
        [InlineKeyboardButton(text="💰 Доход", callback_data="income")],
        [InlineKeyboardButton(text="📈 Аналитика", callback_data="stats")],
        [InlineKeyboardButton(text="⬅️ Назад", callback_data="back_main")]
    ])

def categories_menu():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🍔 Еда", callback_data="cat_Еда")],
        [InlineKeyboardButton(text="🚗 Транспорт", callback_data="cat_Транспорт")],
        [InlineKeyboardButton(text="🏠 Быт", callback_data="cat_Быт")],
        [InlineKeyboardButton(text="🎮 Развлечения", callback_data="cat_Развлечения")],
        [InlineKeyboardButton(text="🏦 Кредиты", callback_data="cat_Кредиты")],
        [InlineKeyboardButton(text="➕ Другое", callback_data="cat_custom")]
    ])

def habits_menu():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➕ Добавить", callback_data="habit_add")],
        [InlineKeyboardButton(text="📋 Мои", callback_data="habit_list")],
        [InlineKeyboardButton(text="⬅️ Назад", callback_data="back_main")]
    ])

def family_menu():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➕ Создать", callback_data="family_create")],
        [InlineKeyboardButton(text="🔗 Вступить", callback_data="family_join")],
        [InlineKeyboardButton(text="👥 Участники", callback_data="family_members")],
        [InlineKeyboardButton(text="⬅️ Назад", callback_data="back_main")]
    ])