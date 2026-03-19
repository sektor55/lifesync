import asyncio
import re
from aiogram import Bot, Dispatcher, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext

from config import TOKEN
from database import *
from keyboards import *
from states import *

bot = Bot(token=TOKEN)
dp = Dispatcher()

# --- SMART CATEGORY ---
CATEGORIES = {
    "Еда": [
        "пятерочка", "pyaterochka",
        "магнит", "magnit",
        "ашан", "auchan",
        "еда", "food",
        "kfc", "mcdonalds", "burger", "бургер"
    ],
    "Транспорт": ["такси", "taxi", "метро", "автобус"],
    "Быт": ["ozon", "wb", "wildberries"],
    "Развлечения": ["кино", "cinema", "игра", "game"],
    "Кредиты": ["кредит", "loan"]
}

INCOME_CATEGORIES = ["ЗП", "Фриланс", "Инвестиции", "Подарок", "Другое"]

def parse_amount(text):
    text = text.replace(",", ".")
    
    matches = re.findall(r"(\d+[.\d]*)\s?(₽|RUB|rub)", text)
    if matches:
        return int(float(matches[0][0]))
    
    nums = re.findall(r"\d+[.\d]*", text)
    nums = [float(n) for n in nums if float(n) > 10]
    
    if not nums:
        return None
    
    return int(max(nums))

def detect_category(text, user_id):
    text_lower = text.lower()

    text_clean = text_lower.replace(".", " ").replace(",", " ")
    text_clean = text_clean.replace("mm", "").replace("mgn", "")

    rules = get_rules(user_id)
    for keyword, cat in rules:
        if keyword in text_clean:
            return cat

    for cat, words in CATEGORIES.items():
        for w in words:
            if w in text_clean:
                return cat

    return "Другое"

# --- СТАРТ ---
@dp.message(CommandStart())
async def start(m: Message):
    await m.answer("🚀 LifeSync", reply_markup=main_menu())

# --- НАВИГАЦИЯ ---
@dp.callback_query(F.data == "back_main")
async def back(c: CallbackQuery):
    await c.message.edit_text("Главное меню", reply_markup=main_menu())

# --- БЮДЖЕТ ---
@dp.callback_query(F.data == "budget")
async def budget(c: CallbackQuery):
    await c.message.edit_text("📊 Бюджет", reply_markup=budget_menu())

# =========================
# 💸 РАСХОД
# =========================
@dp.callback_query(F.data == "expense")
async def expense(c: CallbackQuery, state: FSMContext):
    await state.set_state(AddTransaction.waiting_sum)
    await c.message.answer("Введите сумму или пришлите сообщение из банка")

@dp.message(AddTransaction.waiting_sum)
async def get_sum(m: Message, state: FSMContext):
    amount = parse_amount(m.text)

    if not amount:
        await m.answer("❌ Не нашел сумму, попробуй еще раз")
        return

    category = detect_category(m.text, m.from_user.id)

    await state.update_data(amount=amount, category=category, original_text=m.text)

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Подтвердить", callback_data="confirm_expense")],
        [InlineKeyboardButton(text="🔄 Изменить категорию", callback_data="change_category")]
    ])

    await m.answer(
        f"Сумма: {amount} ₽\nКатегория: {category}",
        reply_markup=kb
    )

@dp.callback_query(F.data == "confirm_expense")
async def confirm_expense(c: CallbackQuery, state: FSMContext):
    data = await state.get_data()

    add_transaction(c.from_user.id, data["amount"], "expense", data["category"])

    await state.clear()
    await c.message.answer(
        f"✅ {data['amount']} ₽ → {data['category']}",
        reply_markup=budget_menu()
    )

# =========================
# 💰 ДОХОД (ЧИСТО ОТДЕЛЕН)
# =========================
class IncomeState:
    waiting_sum = "income_sum"

@dp.callback_query(F.data == "income")
async def income(c: CallbackQuery, state: FSMContext):
    await state.set_state(IncomeState.waiting_sum)
    await c.message.answer("Введите сумму дохода")

@dp.message(F.text, IncomeState.waiting_sum)
async def income_sum(m: Message, state: FSMContext):
    amount = parse_amount(m.text)

    if not amount:
        await m.answer("❌ Не нашел сумму")
        return

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=cat, callback_data=f"income_cat_{cat}")]
        for cat in INCOME_CATEGORIES
    ])

    await state.update_data(amount=amount)

    await m.answer(f"Доход: {amount} ₽\nВыбери категорию", reply_markup=kb)

@dp.callback_query(F.data.startswith("income_cat_"))
async def income_category(c: CallbackQuery, state: FSMContext):
    cat = c.data.replace("income_cat_", "")
    data = await state.get_data()

    add_transaction(c.from_user.id, data["amount"], "income", cat)

    await state.clear()
    await c.message.answer(
        f"💰 +{data['amount']} ₽ ({cat})",
        reply_markup=budget_menu()
    )

# =========================
# ИЗМЕНЕНИЕ КАТЕГОРИИ
# =========================
@dp.callback_query(F.data == "change_category")
async def change_category(c: CallbackQuery, state: FSMContext):
    await state.set_state(AddTransaction.waiting_category)
    await c.message.answer("Выбери категорию", reply_markup=categories_menu())

@dp.callback_query(AddTransaction.waiting_category, F.data.startswith("cat_"))
async def set_cat(c: CallbackQuery, state: FSMContext):
    if c.data == "cat_custom":
        await state.set_state(AddTransaction.waiting_custom_category)
        await c.message.answer("Введи свою категорию")
        return

    cat = c.data.replace("cat_", "")
    data = await state.get_data()

    await state.update_data(category=cat)

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Подтвердить", callback_data="confirm_expense")],
        [InlineKeyboardButton(text="🔄 Изменить категорию", callback_data="change_category")]
    ])

    await c.message.answer(
        f"Сумма: {data['amount']} ₽\nКатегория: {cat}",
        reply_markup=kb
    )

@dp.message(AddTransaction.waiting_custom_category)
async def custom_cat(m: Message, state: FSMContext):
    data = await state.get_data()

    await state.update_data(category=m.text)

    text = data.get("original_text", "").lower()
    if text:
        words = text.split()
        if len(words) > 1:
            keyword = words[-1]
            add_rule(m.from_user.id, keyword, m.text)

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Подтвердить", callback_data="confirm_expense")],
        [InlineKeyboardButton(text="🔄 Изменить категорию", callback_data="change_category")]
    ])

    await m.answer(
        f"Сумма: {data['amount']} ₽\nКатегория: {m.text}",
        reply_markup=kb
    )

# --- АНАЛИТИКА ---
@dp.callback_query(F.data == "stats")
async def stats(c: CallbackQuery):
    data = get_stats(c.from_user.id)

    text = ""
    total = sum(x[1] for x in data)

    for cat, val in data:
        perc = int(val / total * 100)
        text += f"{cat} — {val} ₽ ({perc}%)\n"

    await c.message.answer(text, reply_markup=budget_menu())

# --- ПРИВЫЧКИ ---
@dp.callback_query(F.data == "habits")
async def habits(c: CallbackQuery):
    await c.message.edit_text("🏋️ Привычки", reply_markup=habits_menu())

@dp.callback_query(F.data == "habit_add")
async def habit_add(c: CallbackQuery, state: FSMContext):
    await state.set_state(AddHabit.name)
    await c.message.answer("Название привычки")

@dp.message(AddHabit.name)
async def habit_name(m: Message, state: FSMContext):
    await state.update_data(name=m.text)
    await state.set_state(AddHabit.days)
    await m.answer("Дни (например: пн вт ср)")

@dp.message(AddHabit.days)
async def habit_days(m: Message, state: FSMContext):
    data = await state.get_data()

    cur.execute("INSERT INTO habits VALUES(?,?,?)",(m.from_user.id,data["name"],m.text))
    conn.commit()

    await state.clear()
    await m.answer("✅ Привычка добавлена", reply_markup=habits_menu())

# --- СЕМЬЯ ---
@dp.callback_query(F.data == "family")
async def family(c: CallbackQuery):
    await c.message.edit_text("👨‍👩‍👧 Семья", reply_markup=family_menu())

async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())