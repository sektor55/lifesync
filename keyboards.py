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
        [InlineKeyboardButton(text="⬅️ Назад", callback_data="back")]
    ])


def confirm_menu():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Подтвердить", callback_data="ok")],
        [InlineKeyboardButton(text="🔄 Изменить", callback_data="change_cat")]
    ])


def categories_menu():
    cats = ["Еда","Транспорт","Быт","Развлечения","Кредиты","Другое"]
    return InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text=c, callback_data=f"cat_{c}")] for c in cats]
    )


def habits_menu():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➕ Добавить", callback_data="add_habit")],
        [InlineKeyboardButton(text="📋 Мои", callback_data="my_habits")],
        [InlineKeyboardButton(text="📊 Прогресс", callback_data="progress")],
        [InlineKeyboardButton(text="📅 История", callback_data="history")],
        [InlineKeyboardButton(text="⬅️ Назад", callback_data="back")]
    ])


def days_menu(selected=[]):
    days = ["Пн","Вт","Ср","Чт","Пт","Сб","Вс"]
    kb = []
    for d in days:
        text = f"✅ {d}" if d in selected else d
        kb.append([InlineKeyboardButton(text=text, callback_data=f"day_{d}")])
    kb.append([InlineKeyboardButton(text="Готово", callback_data="days_done")])
    return InlineKeyboardMarkup(inline_keyboard=kb)


def family_menu():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➕ Создать", callback_data="create_family")],
        [InlineKeyboardButton(text="🔗 Вступить", callback_data="join_family")],
        [InlineKeyboardButton(text="⬅️ Назад", callback_data="back")]
    ])