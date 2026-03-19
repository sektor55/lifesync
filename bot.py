import asyncio
import re
from aiogram import Bot, Dispatcher, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import CommandStart, StateFilter
from aiogram.fsm.context import FSMContext

from config import TOKEN
from database import *
from keyboards import *
from states import *

bot = Bot(token=TOKEN)
dp = Dispatcher()

# --- SMART CATEGORY (РАСХОД — НЕ ТРОГАЕМ) ---
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

# --- ДОХОД (СВОИ КАТЕГОРИИ) ---
INCOME_CATEGORIES = {
    "ЗП": ["зарплата", "salary", "работа", "job"],
    "Перевод": ["перевод", "transfer"],
    "Кэшбэк": ["cashback"],
    "Инвестиции": ["дивиденды", "invest"],
    "Другое": []
}


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


# =========================
# РАСХОД (ИДЕАЛ — НЕ ТРОГАЕМ)
# =========================
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


# =========================
# ДОХОД (ОТДЕЛЬНО)
# =========================
def detect_income_category(text):
    text = text.lower()

    for cat, words in INCOME_CATEGORIES.items():
        for w in words:
            if w in text:
                return cat

    return "Другое"


# --- СТАРТ ---
@dp.message(CommandStart())
async def start(m: Message):
    await m.answer("🚀 LifeSync", reply_markup=main_menu())


# --- БЮДЖЕТ ---
@dp.callback_query(F.data == "budget")
async def budget(c: CallbackQuery):
    await c.message.edit_text("📊 Бюджет", reply_markup=budget_menu())


# =========================
# РАСХОД (НЕ ТРОГАЕМ)
# =========================
@dp.callback_query(F.data == "expense")
async def expense(c: CallbackQuery, state: FSMContext):
    await state.set_state(AddTransaction.waiting_sum)
    await c.message.answer("Введите сумму или пришлите сообщение из банка")


@dp.message(AddTransaction.waiting_sum)
async def get_sum(m: Message, state: FSMContext):
    amount = parse_amount(m.text)

    if not amount:
        await m.answer("❌ Не нашел сумму")
        return

    category = detect_category(m.text, m.from_user.id)

    await state.update_data(amount=amount, category=category, original_text=m.text)

    if category == "Другое":
        await state.set_state(AddTransaction.waiting_category)
        await m.answer("Выбери категорию", reply_markup=categories_menu())
        return

    add_transaction(m.from_user.id, amount, "expense", category)

    await state.clear()
    await m.answer(f"✅ {amount} ₽ → {category}", reply_markup=budget_menu())


@dp.callback_query(AddTransaction.waiting_category, F.data.startswith("cat_"))
async def set_cat(c: CallbackQuery, state: FSMContext):
    if c.data == "cat_custom":
        await state.set_state(AddTransaction.waiting_custom_category)
        await c.message.answer("Введи свою категорию")
        return

    cat = c.data.replace("cat_", "")
    data = await state.get_data()

    add_transaction(c.from_user.id, data["amount"], "expense", cat)

    await state.clear()
    await c.message.answer(f"✅ {data['amount']} ₽ → {cat}", reply_markup=budget_menu())


@dp.message(AddTransaction.waiting_custom_category)
async def custom_cat(m: Message, state: FSMContext):
    data = await state.get_data()

    add_transaction(m.from_user.id, data["amount"], "expense", m.text)

    text = data.get("original_text", "").lower()

    words = text.split()
    stop_words = ["покупка", "карта", "баланс", "доступно", "счет", "rub", "₽"]

    clean_words = []
    for w in words:
        w = w.strip(".,:;()")
        if w.isdigit(): continue
        if any(c.isdigit() for c in w): continue
        if w in stop_words: continue
        if len(w) < 3: continue
        clean_words.append(w)

    if clean_words:
        keyword = max(clean_words, key=len)
        add_rule(m.from_user.id, keyword, m.text)

    await state.clear()
    await m.answer(f"✅ {data['amount']} ₽ → {m.text}", reply_markup=budget_menu())


# =========================
# ДОХОД (ПОЛНОСТЬЮ ОТДЕЛЬНО)
# =========================
@dp.callback_query(F.data == "income")
async def income(c: CallbackQuery, state: FSMContext):
    await state.set_state("income_wait_sum")
    await c.message.answer("Введите сумму дохода")


@dp.message(StateFilter("income_wait_sum"))
async def income_sum(m: Message, state: FSMContext):
    amount = parse_amount(m.text)

    if not amount:
        await m.answer("❌ Не нашел сумму")
        return

    category = detect_income_category(m.text)

    await state.update_data(amount=amount)

    if category == "Другое":
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="💼 ЗП", callback_data="inc_ЗП")],
            [InlineKeyboardButton(text="💸 Перевод", callback_data="inc_Перевод")],
            [InlineKeyboardButton(text="💰 Кэшбэк", callback_data="inc_Кэшбэк")],
            [InlineKeyboardButton(text="➕ Другое", callback_data="inc_custom")]
        ])

        await m.answer(f"Сумма: {amount} ₽\nКатегория: Другое", reply_markup=kb)
        return

    add_transaction(m.from_user.id, amount, "income", category)

    await state.clear()
    await m.answer(f"✅ {amount} ₽ → {category}", reply_markup=budget_menu())


@dp.callback_query(F.data.startswith("inc_"))
async def income_set_cat(c: CallbackQuery, state: FSMContext):
    data = await state.get_data()

    if c.data == "inc_custom":
        await state.set_state("income_wait_custom")
        await c.message.answer("Введи категорию дохода")
        return

    cat = c.data.replace("inc_", "")
    add_transaction(c.from_user.id, data["amount"], "income", cat)

    await state.clear()
    await c.message.answer(f"✅ {data['amount']} ₽ → {cat}", reply_markup=budget_menu())


@dp.message(StateFilter("income_wait_custom"))
async def income_custom(m: Message, state: FSMContext):
    data = await state.get_data()

    add_transaction(m.from_user.id, data["amount"], "income", m.text)

    await state.clear()
    await m.answer(f"✅ {data['amount']} ₽ → {m.text}", reply_markup=budget_menu())


# --- АНАЛИТИКА ---
@dp.callback_query(F.data == "stats")
async def stats(c: CallbackQuery):
    data = get_stats(c.from_user.id)

    text = ""
    total = sum(x[1] for x in data) if data else 1

    for cat, val in data:
        perc = int(val / total * 100)
        text += f"{cat} — {val} ₽ ({perc}%)\n"

    await c.message.answer(text, reply_markup=budget_menu())


async def main():
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())