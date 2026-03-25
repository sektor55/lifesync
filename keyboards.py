from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

def main_menu():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="💰 Финансы")],
            [KeyboardButton(text="🏋️ Привычки")],
            [KeyboardButton(text="📊 Аналитика")],
            [KeyboardButton(text="⚙️ Настройки"), KeyboardButton(text="💎 Подписка")]
        ],
        resize_keyboard=True
    )

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
        [InlineKeyboardButton(text="📊 Прогресс", callback_data="habit_progress")],
        [InlineKeyboardButton(text="⬅️ Назад", callback_data="back_main")]
    ])

def family_menu():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➕ Создать", callback_data="family_create")],
        [InlineKeyboardButton(text="🔗 Вступить", callback_data="family_join")],
        [InlineKeyboardButton(text="👥 Участники", callback_data="family_members")],
        [InlineKeyboardButton(text="⬅️ Назад", callback_data="back_main")]
    ])

# ✅ НОВОЕ (ТОЛЬКО ДОБАВИЛИ)
def stats_menu():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📊 График расходов", callback_data="graph_expense")],
        [InlineKeyboardButton(text="📈 График доходов", callback_data="graph_income")],
        [InlineKeyboardButton(text="⬅️ Назад", callback_data="budget")]
    ])
    
def timezone_kb():
    buttons = []

    for i in range(-12, 13):
        sign = "+" if i >= 0 else ""
        text = f"UTC {sign}{i}"

        msk_diff = i - 3
        msk_sign = "+" if msk_diff >= 0 else ""
        text += f"\nМСК {msk_sign}{msk_diff}"

        buttons.append(
            InlineKeyboardButton(
                text=text,
                callback_data=f"tz_{i}"
            )
        )

    # 🔥 делаем по 4 кнопки в строке
    kb_rows = [buttons[i:i+4] for i in range(0, len(buttons), 4)]

    return InlineKeyboardMarkup(inline_keyboard=kb_rows)