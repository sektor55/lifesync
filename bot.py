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

# =========================
# РАСХОД (НЕ ТРОГАЕМ ЛОГИКУ)
# =========================
CATEGORIES = {
    "Еда": ["пятерочка","pyaterochka","магнит","magnit","ашан","auchan","еда","food","kfc","burger"],
    "Транспорт": ["такси","taxi","метро","автобус"],
    "Быт": ["ozon","wb","wildberries"],
    "Развлечения": ["кино","cinema","игра","game"],
    "Кредиты": ["кредит","loan"]
}

# =========================
# ДОХОД (ОТДЕЛЬНО)
# =========================
INCOME_CATEGORIES = {
    "ЗП": ["зарплата","salary","работа","job","др банк"],
    "Перевод": ["перевод","transfer"],
    "Кэшбэк": ["cashback"],
    "Инвестиции": ["дивиденды","инвестиции"],
}

# =========================
# ОБЩЕЕ
# =========================
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
# РАСХОД
# =========================
def detect_category(text, user_id):
    text = text.lower().replace(".", " ").replace(",", " ")
    text = text.replace("mm","").replace("mgn","")

    rules = get_rules(user_id)
    for keyword, cat in rules:
        if keyword in text:
            return cat

    for cat, words in CATEGORIES.items():
        for w in words:
            if w in text:
                return cat

    return "Другое"


# =========================
# ДОХОД
# =========================
def detect_income_category(text):
    text = text.lower()
    for cat, words in INCOME_CATEGORIES.items():
        for w in words:
            if w in text:
                return cat
    return "Другое"


# =========================
# КНОПКИ ПОДТВЕРЖДЕНИЯ
# =========================
def confirm_kb(prefix="exp"):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Подтвердить", callback_data=f"{prefix}_confirm")],
        [InlineKeyboardButton(text="🔄 Изменить категорию", callback_data=f"{prefix}_change")]
    ])


# =========================
# СТАРТ
# =========================
@dp.message(CommandStart())
async def start(m: Message):
    await m.answer("🚀 LifeSync", reply_markup=main_menu())


# =========================
# МЕНЮ (ФИКС КНОПОК)
# =========================
@dp.callback_query(F.data == "budget")
async def budget(c: CallbackQuery):
    await c.message.edit_text("📊 Бюджет", reply_markup=budget_menu())


@dp.callback_query(F.data == "back_main")
async def back_main(c: CallbackQuery):
    await c.message.edit_text("Главное меню", reply_markup=main_menu())


# =========================
# РАСХОД (ИДЕАЛ)
# =========================
@dp.callback_query(F.data == "expense")
async def expense(c: CallbackQuery, state: FSMContext):
    await state.set_state(AddTransaction.waiting_sum)
    await c.message.answer("Введите сумму или пришлите сообщение из банка")


@dp.message(AddTransaction.waiting_sum)
async def expense_sum(m: Message, state: FSMContext):
    amount = parse_amount(m.text)
    if not amount:
        await m.answer("❌ Не нашел сумму")
        return

    category = detect_category(m.text, m.from_user.id)

    await state.update_data(
        amount=amount,
        category=category,
        original_text=m.text
    )

    await m.answer(
        f"Сумма: {amount} ₽\nКатегория: {category}",
        reply_markup=confirm_kb("exp")
    )


@dp.callback_query(F.data == "exp_confirm")
async def exp_confirm(c: CallbackQuery, state: FSMContext):
    data = await state.get_data()

    add_transaction(c.from_user.id, data["amount"], "expense", data["category"])
    await state.clear()

    await c.message.answer(
        f"✅ {data['amount']} ₽ → {data['category']}",
        reply_markup=budget_menu()
    )


@dp.callback_query(F.data == "exp_change")
async def exp_change(c: CallbackQuery, state: FSMContext):
    await state.set_state(AddTransaction.waiting_category)
    await c.message.answer("Выбери категорию", reply_markup=categories_menu())


@dp.callback_query(AddTransaction.waiting_category, F.data.startswith("cat_"))
async def exp_set_cat(c: CallbackQuery, state: FSMContext):
    if c.data == "cat_custom":
        await state.set_state(AddTransaction.waiting_custom_category)
        await c.message.answer("Введи свою категорию")
        return

    cat = c.data.replace("cat_", "")
    await state.update_data(category=cat)

    data = await state.get_data()

    await c.message.answer(
        f"Сумма: {data['amount']} ₽\nКатегория: {cat}",
        reply_markup=confirm_kb("exp")
    )


@dp.message(AddTransaction.waiting_custom_category)
async def exp_custom(m: Message, state: FSMContext):
    data = await state.get_data()
    await state.update_data(category=m.text)

    # обучение
    text = data.get("original_text","").lower()
    words = text.split()

    stop_words = ["покупка","карта","баланс","доступно","счет","rub","₽"]

    clean = []
    for w in words:
        w = w.strip(".,:;()")
        if w.isdigit(): continue
        if any(c.isdigit() for c in w): continue
        if w in stop_words: continue
        if len(w) < 3: continue
        clean.append(w)

    if clean:
        keyword = max(clean, key=len)
        add_rule(m.from_user.id, keyword, m.text)

    await m.answer(
        f"Сумма: {data['amount']} ₽\nКатегория: {m.text}",
        reply_markup=confirm_kb("exp")
    )


# =========================
# ДОХОД (ОТДЕЛЬНО И БЕЗ КОНФЛИКТОВ)
# =========================
@dp.callback_query(F.data == "income")
async def income(c: CallbackQuery, state: FSMContext):
    await state.set_state("income_sum")
    await c.message.answer("Введите сумму дохода")


@dp.message(StateFilter("income_sum"))
async def income_sum(m: Message, state: FSMContext):
    amount = parse_amount(m.text)

    if not amount:
        await m.answer("❌ Не нашел сумму")
        return

    category = detect_income_category(m.text)

    await state.update_data(amount=amount, category=category)

    await m.answer(
        f"Сумма: {amount} ₽\nКатегория: {category}",
        reply_markup=confirm_kb("inc")
    )


@dp.callback_query(F.data == "inc_confirm")
async def inc_confirm(c: CallbackQuery, state: FSMContext):
    data = await state.get_data()

    add_transaction(c.from_user.id, data["amount"], "income", data["category"])
    await state.clear()

    await c.message.answer(
        f"✅ {data['amount']} ₽ → {data['category']}",
        reply_markup=budget_menu()
    )


@dp.callback_query(F.data == "inc_change")
async def inc_change(c: CallbackQuery):
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💼 ЗП", callback_data="inc_set_ЗП")],
        [InlineKeyboardButton(text="💸 Перевод", callback_data="inc_set_Перевод")],
        [InlineKeyboardButton(text="💰 Кэшбэк", callback_data="inc_set_Кэшбэк")],
        [InlineKeyboardButton(text="📈 Инвестиции", callback_data="inc_set_Инвестиции")],
        [InlineKeyboardButton(text="➕ Другое", callback_data="inc_custom")]
    ])

    await c.message.answer("Выбери категорию дохода", reply_markup=kb)


@dp.callback_query(F.data.startswith("inc_set_"))
async def inc_set(c: CallbackQuery, state: FSMContext):
    cat = c.data.replace("inc_set_", "")
    await state.update_data(category=cat)

    data = await state.get_data()

    await c.message.answer(
        f"Сумма: {data['amount']} ₽\nКатегория: {cat}",
        reply_markup=confirm_kb("inc")
    )


@dp.callback_query(F.data == "inc_custom")
async def inc_custom_start(c: CallbackQuery, state: FSMContext):
    await state.set_state("income_custom")
    await c.message.answer("Введи категорию")


@dp.message(StateFilter("income_custom"))
async def inc_custom(m: Message, state: FSMContext):
    data = await state.get_data()
    await state.update_data(category=m.text)

    await m.answer(
        f"Сумма: {data['amount']} ₽\nКатегория: {m.text}",
        reply_markup=confirm_kb("inc")
    )


# =========================
# СТАТИСТИКА
# =========================
@dp.callback_query(F.data == "stats")
async def stats(c: CallbackQuery):
    data = get_stats(c.from_user.id)

    total = sum(x[1] for x in data) if data else 1
    text = ""

    for cat, val in data:
        perc = int(val / total * 100)
        text += f"{cat} — {val} ₽ ({perc}%)\n"

    await c.message.answer(text, reply_markup=budget_menu())


# =========================
# СТАРТ БОТА
# =========================
async def main():
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())