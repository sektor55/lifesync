from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton

def get_main_menu():
    return ReplyKeyboardMarkup(
        keyboard=[
            [
                KeyboardButton(text="💰 Финансы"),
                KeyboardButton(text="🏋️ Привычки")
            ],
            [
                KeyboardButton(text="👥 Семья"),
                KeyboardButton(text="⚙️ Настройки"),
                KeyboardButton(text="💎 Подписка"),
                KeyboardButton(text="❓ FAQ")
            ]
        ],
        resize_keyboard=True
    )

def budget_menu():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💸 Расход", callback_data="expense")],
        [InlineKeyboardButton(text="💰 Доход", callback_data="income")],
        [InlineKeyboardButton(text="📊 Аналитика", callback_data="finance_stats")],
        [InlineKeyboardButton(text="🏦 Накопления", callback_data="savings_menu")]  # 🔥 ВОТ ЭТО ДОБАВЬ
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

def income_categories():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💼 ЗП", callback_data="inc_cat_ЗП")],
        [InlineKeyboardButton(text="💳 Кешбек", callback_data="inc_cat_Кешбек")],
        [InlineKeyboardButton(text="🎁 Подарок", callback_data="inc_cat_Подарок")],
        [InlineKeyboardButton(text="💰 Накопления", callback_data="inc_cat_Накопления")],
        [InlineKeyboardButton(text="✏️ Другое", callback_data="inc_cat_custom")]
    ])

def savings_menu():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➕ Добавить", callback_data="sav_add")],
        [InlineKeyboardButton(text="➖ Списать", callback_data="sav_remove")],
        [InlineKeyboardButton(text="⬅️ Назад", callback_data="back_fin")]
    ])

def habits_menu():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➕ Добавить", callback_data="habit_add")],
        [InlineKeyboardButton(text="📋 Мои", callback_data="habit_list")],
        [InlineKeyboardButton(text="📊 Прогресс", callback_data="habit_progress")],
    ])

def family_menu():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➕ Создать", callback_data="family_create")],
        [InlineKeyboardButton(text="🔗 Вступить", callback_data="family_join")],
        [InlineKeyboardButton(text="👥 Участники", callback_data="family_members")],
        [InlineKeyboardButton(text="⬅️ Назад", callback_data="back_main")]
    ])

def subscription_menu():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💰 Финансовая система", callback_data="fin_menu")],
        [InlineKeyboardButton(text="🌅 Магия утра", callback_data="morning_menu")],
        [InlineKeyboardButton(text="⬅️ Назад", callback_data="back_main")]
    ])

# ✅ НОВОЕ (ТОЛЬКО ДОБАВИЛИ)
def stats_menu():
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="📊 График расходов", callback_data="graph_expense"),
            InlineKeyboardButton(text="📈 График доходов", callback_data="graph_income"),
        ],
        [
            InlineKeyboardButton(text="⬅️ Назад", callback_data="budget")
        ]
    ])
    
def timezone_kb():
    buttons = []

    for i in range(-12, 13):
        if i == 3:
            continue  # МСК отдельно

        diff = i - 3
        sign = "+" if diff >= 0 else ""

        text = f"{sign}{diff} к МСК"

        buttons.append(
            InlineKeyboardButton(
                text=text,
                callback_data=f"tz_{i}"
            )
        )

    # по 5 кнопок в ряд
    rows = [buttons[i:i+5] for i in range(0, len(buttons), 5)]

    # кнопка МСК
    rows.append([
        InlineKeyboardButton(
            text="🕒 Время по МСК",
            callback_data="tz_3"
        )
    ])

    return InlineKeyboardMarkup(inline_keyboard=rows)