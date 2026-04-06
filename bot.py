import asyncio
import re

import aiohttp
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

SAVINGS_BUFFER = {}

from aiogram import Bot, Dispatcher, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton, FSInputFile
from aiogram.filters import CommandStart, StateFilter
from aiogram.fsm.context import FSMContext

from config import TOKEN
from database import *
import keyboards
from states import *
USER_MODE = {}

bot = Bot(token=TOKEN)
dp = Dispatcher()

def get_user_color(user_id):
    profile = get_user_profile(user_id)
    if profile:
        return profile[2] or "🟩"
    return "🟩"

# =========================
# РАСХОД 
# =========================
CATEGORIES = {
    "Еда": ["пятерочка","pyaterochka","магнит","magnit","ашан","auchan","еда","food","kfc","burger"],
    "Транспорт": ["такси","taxi","метро","автобус"],
    "Быт": ["ozon","wb","wildberries"],
    "Развлечения": ["кино","cinema","игра","game"],
    "Кредиты": ["кредит","loan"]
}

# =========================
# ДОХОД
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

    return int(nums[-1])  # БЕРЕМ ПОСЛЕДНЕЕ, а не max


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
# КНОПКИ
# =========================
def confirm_kb(prefix="exp"):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Подтвердить", callback_data=f"{prefix}_confirm")],
        [InlineKeyboardButton(text="🔄 Изменить категорию", callback_data=f"{prefix}_change")]
    ])

def timezone_kb():
    kb = []
    row = []

    for i in range(-12, 13):
        if i == 0:
            text = "🕒 МСК"
        else:
            text = f"МСК {i:+d}"

        row.append(InlineKeyboardButton(
            text=text,
            callback_data=f"tz_{i+3}"
        ))

        if len(row) == 4:  # компактная сетка
            kb.append(row)
            row = []

    if row:
        kb.append(row)

    return InlineKeyboardMarkup(inline_keyboard=kb)



# ✅ ДОБАВЛЕНО (новое меню статистики)



# =========================
# СТАРТ
# =========================



# =========================
# МЕНЮ
# =========================
@dp.callback_query(F.data == "budget")
async def budget(c: CallbackQuery):
    await c.message.edit_text("📊 Финансы", reply_markup=keyboards.budget_menu())


@dp.callback_query(F.data == "back_main")
async def back_main(c: CallbackQuery):
    await c.message.answer("Главное меню", reply_markup=keyboards.get_main_menu())
        


# =========================
# РАСХОД (НЕ ТРОГАЕМ)
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

    amount = data["amount"]
    category = data["category"]

    # 🔥 НАКОПЛЕНИЯ (расход → копилка)
    if category.lower() == "накопления":
        add_savings(c.from_user.id, amount)
        await state.clear()

        await c.message.answer(
            f"💰 {amount} ₽ → Накопления\n\n✔ Перемещено из баланса",
            reply_markup=keyboards.budget_menu()
        )
        return

    add_transaction(c.from_user.id, amount, "expense", category)

    await state.clear()

    await c.message.answer(
        f"✅ {amount} ₽ → {category}",
        reply_markup=keyboards.budget_menu()
    )


@dp.callback_query(F.data == "exp_change")
async def exp_change(c: CallbackQuery, state: FSMContext):
    await state.set_state(AddTransaction.waiting_category)
    await c.message.answer("Выбери категорию", reply_markup=keyboards.categories_menu())


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
# ДОХОД (НЕ ТРОГАЕМ)
# =========================
from aiogram.fsm.state import StatesGroup, State

class AddIncome(StatesGroup):
    sum = State()
    custom = State()

class SavingsState(StatesGroup):
    add = State()
    remove = State()

@dp.callback_query(F.data == "sav_add")
async def sav_add(c: CallbackQuery, state: FSMContext):
    await state.set_state(SavingsState.add)
    await c.message.answer("Введите сумму для добавления:")

@dp.message(SavingsState.add)
async def sav_add_process(m: Message, state: FSMContext):
    amount = parse_amount(m.text)

    if not amount:
        await m.answer("❌ Ошибка суммы")
        return

    add_savings(m.from_user.id, amount)

    await state.clear()

    await m.answer(f"✅ Добавлено в накопления: {amount:,} ₽")

@dp.callback_query(F.data == "sav_remove")
async def remove_savings_start(c: CallbackQuery, state: FSMContext):
    await state.set_state("remove_savings")

    await c.message.answer("Введите сумму для списания")
    
@dp.message(F.text, StateFilter("remove_savings"))
async def remove_savings_finish(m: Message, state: FSMContext):
    amount = parse_amount(m.text)
    user_id = m.from_user.id

    if not amount:
        await m.answer("❌ Неверная сумма")
        return

    success = withdraw_savings(user_id, amount)

    if not success:
        await m.answer("❌ Недостаточно накоплений")
        return

    # 🔥 ДОБАВЛЯЕМ В ДОХОД
    add_transaction(user_id, amount, "income", "Накопления")

    await state.clear()

    await m.answer(
        f"➖ Списано: {amount:,} ₽",
        reply_markup=keyboards.budget_menu(is_fin_enabled(user_id))
    )    
    
@dp.message(SavingsState.remove)
async def sav_remove_process(m: Message, state: FSMContext):
    amount = parse_amount(m.text)

    if not amount:
        await m.answer("❌ Ошибка суммы")
        return

    success = withdraw_savings(m.from_user.id, amount)

    await state.clear()

    if success:
        await m.answer(f"💸 Списано: {amount:,} ₽")
    else:
        await m.answer("❌ Недостаточно средств")    
    

@dp.callback_query(F.data == "income")
async def income(c: CallbackQuery, state: FSMContext):
    await state.clear()  # 🔥 убираем мусор
    await state.set_state(AddIncome.sum)

    await c.message.answer("💰 Введите сумму дохода:")


@dp.message(AddIncome.sum)
async def income_sum(m: Message, state: FSMContext):
    amount = parse_amount(m.text)

    if not amount:
        await m.answer("❌ Не нашел сумму")
        return

    await state.update_data(amount=amount)

    await m.answer(
        "💰 Выбери категорию дохода:",
        reply_markup=keyboards.income_categories()
    )

@dp.callback_query(F.data == "save_income_part")
async def save_income_part(c: CallbackQuery, state: FSMContext):
    user_id = c.from_user.id
    data = SAVINGS_BUFFER.get(user_id)

    if not data:
        await c.answer("Ошибка")
        return

    income_part = data["amount"] - data["savings"]

    # доход (уже без 10%)
    add_transaction(user_id, income_part, "income", data["category"])

    # накопления
    add_savings(user_id, data["savings"])

    SAVINGS_BUFFER.pop(user_id, None)
    await state.clear()

    await c.message.answer(
        f"💰 Отложено: {data['savings']:,} ₽\n"
        f"💵 В доход учтено: {income_part:,} ₽",
        reply_markup=keyboards.budget_menu(is_fin_enabled(user_id))
    )


@dp.callback_query(F.data == "subscription")
async def subscription(c: CallbackQuery):
    await c.message.answer(
        "📦 Подписка\n\nВыбери функцию:",
        reply_markup=keyboards.subscription_menu()
    )
    
@dp.callback_query(F.data == "fin_menu")
async def fin_menu(c: CallbackQuery):
    user_id = c.from_user.id
    enabled = is_fin_enabled(user_id)

    status = "✅ Включено" if enabled else "❌ Выключено"
    btn_text = "🔴 Выключить" if enabled else "🟢 Включить"

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=btn_text, callback_data="toggle_fin")],
        [InlineKeyboardButton(text="⬅️ Назад", callback_data="back_sub")]
    ])

    await c.message.answer(
        "💰 Финансовая система\n"
        "«Самый богатый человек в Вавилоне»\n\n"
        "1. Платите себе первым\n"
        "2. Контролируйте расходы\n"
        "3. Создавайте накопления\n"
        "4. Увеличивайте доход\n"
        "5. Инвестируйте\n"
        "6. Не влезайте в долги\n"
        "7. Защищайте капитал\n"
        "8. Думайте самостоятельно\n"
        "9. Учитесь на ошибках\n"
        "10. Используйте ресурсы разумно\n\n"
        f"Статус: {status}",
        reply_markup=kb
    )

@dp.callback_query(F.data == "toggle_fin")
async def toggle_fin_handler(c: CallbackQuery):
    toggle_fin(c.from_user.id)

    await c.answer("Обновлено")
    await fin_menu(c)

@dp.callback_query(F.data == "back_fin")
async def back_fin(c: CallbackQuery):
    await c.message.answer(
        "📊 Финансы",
        reply_markup=keyboards.budget_menu(is_fin_enabled(c.from_user.id))
    )  

@dp.callback_query(F.data == "savings_menu")
async def open_savings(c: CallbackQuery):
    if not is_fin_enabled(c.from_user.id):
        await c.answer("❌ Финансовая система выключена", show_alert=True)
        return

    await c.message.answer(
        "🏦 Накопления",
        reply_markup=keyboards.savings_menu()
    )

@dp.callback_query(F.data == "skip_income_part")
async def skip_income_part(c: CallbackQuery, state: FSMContext):
    user_id = c.from_user.id
    data = SAVINGS_BUFFER.get(user_id)

    if not data:
        await c.answer("Ошибка")
        return

    add_transaction(user_id, data["amount"], "income", data["category"])

    SAVINGS_BUFFER.pop(user_id, None)
    await state.clear()

    await c.message.answer(
        f"✅ Доход добавлен: {data['amount']:,} ₽",
        reply_markup=keyboards.budget_menu(is_fin_enabled(user_id))
    )
    
    
@dp.callback_query(F.data == "withdraw_no")
async def withdraw_no(c: CallbackQuery):
    await c.message.answer("❌ Отменено")    

@dp.callback_query(F.data == "inc_custom")
async def inc_custom_start(c: CallbackQuery, state: FSMContext):
    await state.set_state(AddIncome.custom)
    await c.message.answer("Введи категорию")

@dp.callback_query(F.data.startswith("withdraw_yes_"))
async def withdraw_yes(c: CallbackQuery):
    amount = int(c.data.split("_")[2])

    success = withdraw_savings(c.from_user.id, amount)

    if not success:
        await c.message.answer("❌ Недостаточно накоплений")
        return

    await c.message.answer(f"✅ Снято: {amount:,} ₽")


@dp.message(AddIncome.custom)
async def inc_custom(m: Message, state: FSMContext):
    data = await state.get_data()

    await state.update_data(category=m.text)

    await m.answer(
        f"Сумма: {data['amount']} ₽\nКатегория: {m.text}",
        reply_markup=confirm_kb("inc")
    )


@dp.callback_query(F.data == "inc_confirm")
async def inc_confirm(c: CallbackQuery, state: FSMContext):
    data = await state.get_data()

    amount = data["amount"]
    category = data["category"]

    # 🔥 СНЯТИЕ С КОПИЛКИ
    if category.lower() == "накопления":
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(text="✅ Да", callback_data=f"withdraw_yes_{amount}"),
                InlineKeyboardButton(text="❌ Нет", callback_data="withdraw_no")
            ]
        ])

        await c.message.answer(
            f"💰 Снять из накоплений: {amount:,} ₽?",
            reply_markup=kb
        )
        return

    add_transaction(c.from_user.id, amount, "income", category)

    await state.clear()

    await c.message.answer(
        f"✅ {amount} ₽ → {category}",
        reply_markup=keyboards.budget_menu()
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

# =========================
# 📊 СТАТИСТИКА (ИСПРАВЛЕНА)
# =========================
@dp.callback_query(F.data == "finance_stats")
async def stats(c: CallbackQuery):
    users = get_family_members(c.from_user.id)

    text = "📊 Аналитика\n\n"

    total_income_map = {}
    total_expense_map = {}

    user_income_map = {}
    user_expense_map = {}

    for uid in users:
        cur.execute("""
            SELECT category, SUM(amount)
            FROM transactions
            WHERE user_id=? AND type='income'
            GROUP BY category
        """, (uid,))
        income = cur.fetchall()

        cur.execute("""
            SELECT category, SUM(amount)
            FROM transactions
            WHERE user_id=? AND type='expense'
            GROUP BY category
        """, (uid,))
        expense = cur.fetchall()

        user_income_map[uid] = dict(income)
        user_expense_map[uid] = dict(expense)

        for cat, amount in income:
            total_income_map[cat] = total_income_map.get(cat, 0) + amount

        for cat, amount in expense:
            total_expense_map[cat] = total_expense_map.get(cat, 0) + amount

    total_income = sum(total_income_map.values())
    total_expense = sum(total_expense_map.values())

    text += "💰 Доходы:\n"

    if total_income_map:
        for cat, amount in total_income_map.items():
            percent = int(amount / total_income * 100) if total_income else 0
            text += f"{cat} — {amount} ₽ ({percent}%)\n"

            contributors = []
            for uid in users:
                val = user_income_map.get(uid, {}).get(cat, 0)
                if val > 0:
                    profile = get_user_profile(uid)
                    name = profile[0] if profile and profile[0] else f"id:{uid}"
                    contributors.append((uid, name, val))

            if len(contributors) > 1:
                for uid2, name, val in contributors:
                    profile = get_user_profile(uid2)
                    gender = (profile[3] if profile and len(profile) > 3 else "male") or "male"
                    emoji = "👩" if str(gender).lower() in ["female", "woman", "f", "ж", "жен"] else "👤"
                    text += f"  {emoji}{name} — {val} ₽\n"

    else:
        text += "нет данных\n"

    text += "\n💸 Расходы:\n"

    if total_expense_map:
        for cat, amount in total_expense_map.items():
            percent = int(amount / total_expense * 100) if total_expense else 0
            text += f"{cat} — {amount} ₽ ({percent}%)\n"

            contributors = []
            for uid in users:
                val = user_expense_map.get(uid, {}).get(cat, 0)
                if val > 0:
                    profile = get_user_profile(uid)
                    name = profile[0] if profile and profile[0] else f"id:{uid}"
                    contributors.append((uid, name, val))

            if len(contributors) > 1:
                for uid2, name, val in contributors:
                    profile = get_user_profile(uid2)
                    gender = (profile[3] if profile and len(profile) > 3 else "male") or "male"
                    emoji = "👩" if str(gender).lower() in ["female", "woman", "f", "ж", "жен"] else "👤"
                    text += f"  {emoji}{name} — {val} ₽\n"

    else:
        text += "нет данных\n"

    # ✅ ИТОГИ (НОВЫЙ ФОРМАТ)
    balance = total_income - total_expense

    text += (
        "\n────────────────────────\n"
        f"📈 Баланс: {balance} ₽\n"
        f"Доход: {total_income} ₽ | Расход: {total_expense} ₽\n"
        "────────────────────────\n\n"
    )

    savings = get_savings(c.from_user.id)
    percent = int((savings / total_income) * 100) if total_income else 0

    if percent == 0:
        status = "❌"
        text_status = "Ты пока не платишь себе первым"
    elif percent < 10:
        status = "⚠️"
        text_status = "Ниже нормы (10%)"
    elif percent < 20:
        status = "👍"
        text_status = "Хороший уровень"
    else:
        status = "🔥"
        text_status = "Отлично"

    text += (
        f"💰 Накопления — {savings} ₽\n"
        f"📊 Ты откладываешь: {percent}% / {status} {text_status}\n"
    )

    text += "\n\n" + get_motivation_text()
    
    await c.message.answer(text, reply_markup=keyboards.stats_menu())

@dp.callback_query(F.data.startswith("inc_cat_"))
async def income_category(c: CallbackQuery, state: FSMContext):
    category = c.data.split("_")[2]

    data = await state.get_data()
    amount = data.get("amount")

    if amount is None:
        await c.message.answer("❌ Сначала введи сумму")
        return

    user_id = c.from_user.id

    # ❗ ЕСЛИ ФИНАНСЫ ВЫКЛЮЧЕНЫ
    if not is_fin_enabled(user_id):
        add_transaction(user_id, amount, "income", category)

        await state.clear()

        await c.message.answer(
            f"✅ Доход добавлен: {amount:,} ₽ → {category}",
            reply_markup=keyboards.budget_menu(is_fin_enabled(user_id))
        )
        return

    # 💰 ЛОГИКА 10%
    savings_part = int(amount * 0.1)

    SAVINGS_BUFFER[user_id] = {
        "amount": amount,
        "category": category,
        "savings": savings_part
    }

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="💰 Отложить", callback_data="save_income_part"),
            InlineKeyboardButton(text="❌ Пропустить", callback_data="skip_income_part")
        ]
    ])

    await c.message.answer(
        f"💰 Доход: {amount:,} ₽ → {category}\n\n"
        f"📌 Отложить 10%?\n👉 {savings_part:,} ₽",
        reply_markup=kb
    )

# =========================
# 📉 ГРАФИК РАСХОДОВ
# =========================
@dp.callback_query(F.data == "graph_expense")
async def graph_expense(c: CallbackQuery):
    users = get_family_members(c.from_user.id)

    all_data = {}

    for uid in users:
        data = get_expense_stats(uid)
        for cat, amount in data:
            all_data[cat] = all_data.get(cat, 0) + amount

    if not all_data:
        await c.message.answer("Нет данных", reply_markup=keyboards.budget_menu())
        return

    cats = list(all_data.keys())
    vals = list(all_data.values())

    total = sum(vals)

    def autopct(pct):
        val = int(pct * total / 100)
        return f"{val} ₽\n({int(pct)}%)"

    plt.figure(figsize=(7, 7), facecolor="#1e1e2f")

    colors = ["#00c896", "#ff6b6b", "#4dabf7", "#ffd43b", "#845ef7"]

    plt.pie(
        vals,
        labels=cats,
        autopct=autopct,
        startangle=140,
        colors=colors,
        textprops={"color": "white", "fontsize": 14},
        wedgeprops={"edgecolor": "#1e1e2f", "linewidth": 2}
    )

    plt.title("Расходы (вся семья)", fontsize=20, color="white")

    file_name = "expense.png"
    plt.savefig(file_name, facecolor="#1e1e2f")
    plt.close()

    await c.message.answer_photo(FSInputFile(file_name))
    await c.message.answer("📊 Готово", reply_markup=keyboards.budget_menu())


# =========================
# 💰 ГРАФИК ДОХОДОВ
# =========================
@dp.callback_query(F.data == "graph_income")
async def graph_income(c: CallbackQuery):
    users = get_family_members(c.from_user.id)

    all_data = {}

    for uid in users:
        data = get_income_stats(uid)
        for cat, amount in data:
            all_data[cat] = all_data.get(cat, 0) + amount

    if not all_data:
        await c.message.answer("Нет данных", reply_markup=keyboards.budget_menu())
        return

    cats = list(all_data.keys())
    vals = list(all_data.values())

    total = sum(vals)

    def autopct(pct):
        val = int(pct * total / 100)
        return f"{val} ₽\n({int(pct)}%)"

    plt.figure(figsize=(7, 7), facecolor="#1e1e2f")

    colors = ["#51cf66", "#339af0", "#fcc419", "#ff922b", "#f06595"]

    plt.pie(
        vals,
        labels=cats,
        autopct=autopct,
        startangle=140,
        colors=colors,
        textprops={"color": "white", "fontsize": 14},
        wedgeprops={"edgecolor": "#1e1e2f", "linewidth": 2}
    )

    plt.title("Доходы (вся семья)", fontsize=20, color="white")

    file_name = "income.png"
    plt.savefig(file_name, facecolor="#1e1e2f")
    plt.close()

    await c.message.answer_photo(FSInputFile(file_name))
    await c.message.answer("📊 Готово", reply_markup=keyboards.budget_menu())
    
    # =========================
# 🏋️ ПРИВЫЧКИ
# =========================

from datetime import datetime

DAYS = ["Пн","Вт","Ср","Чт","Пт","Сб","Вс"]


@dp.callback_query(F.data == "habits")
async def habits_menu_handler(c: CallbackQuery):
    await c.message.edit_text("🏋️ Привычки", reply_markup=keyboards.habits_menu())


@dp.callback_query(F.data == "habit_add")
async def habit_add_start(c: CallbackQuery, state: FSMContext):
    await c.answer()

    await state.set_state(AddHabit.name)
    await c.message.answer("Введите название привычки")


@dp.message(AddHabit.name)
async def habit_name(m: Message, state: FSMContext):
    name = m.text.strip()

    # если первый символ не буква/цифра (эмодзи)
    if len(name) > 1 and not name[0].isalnum():
        name = name[0] + name[1:].upper()
    else:
        name = name.upper()

    await state.update_data(name=name)
    await state.set_state(AddHabit.type)

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="👤 Личная", callback_data="habit_type_personal")],
        [InlineKeyboardButton(text="👥 Общая", callback_data="habit_type_family")]
    ])

    await m.answer("Выбери тип", reply_markup=kb)


def get_days_kb(selected):
    kb = []
    row = []

    for d in DAYS:
        if d in selected:
            text = f"•{d}"
        else:
            text = f" {d}"

        row.append(InlineKeyboardButton(
            text=text,
            callback_data=f"day_{d}"
        ))

    kb.append(row)
    kb.append([InlineKeyboardButton(text="✅ Готово", callback_data="days_done")])

    return InlineKeyboardMarkup(inline_keyboard=kb)


@dp.callback_query(AddHabit.type, F.data.startswith("habit_type"))
async def habit_type(c: CallbackQuery, state: FSMContext):
    await c.answer()

    h_type = "personal" if "personal" in c.data else "family"
    await state.update_data(type=h_type, days=[])

    await state.set_state(AddHabit.task_type)

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔁 Цикличная", callback_data="task_cycle")],
        [InlineKeyboardButton(text="🎯 Разовая", callback_data="task_once")]
    ])

    await c.message.edit_text("Тип задачи", reply_markup=kb)


@dp.callback_query(F.data.startswith("day_"))
async def toggle_days(c: CallbackQuery, state: FSMContext):
    await c.answer()

    data = await state.get_data()
    days = data.get("days", [])

    d = c.data.replace("day_", "")

    if data.get("task_type") == "once":
        days = [d]
    else:
        if d in days:
            days.remove(d)
        else:
            days.append(d)

    # 🔥 ВАЖНО — СОРТИРОВКА
    order = {day: i for i, day in enumerate(DAYS)}
    days = sorted(days, key=lambda x: order[x])

    await state.update_data(days=days)

    await c.message.edit_reply_markup(
        reply_markup=get_days_kb(days)
    )


def get_hours_kb():
    kb = []
    row = []

    for h in range(0, 24):
        row.append(InlineKeyboardButton(
            text=f"{h:02d}",
            callback_data=f"hour_{h:02d}"
        ))
        if len(row) == 6:
            kb.append(row)
            row = []

    if row:
        kb.append(row)

    kb.append([
        InlineKeyboardButton(text="❌ Без времени", callback_data="skip_time")
    ])

    return InlineKeyboardMarkup(inline_keyboard=kb)


def get_minutes_kb(hour):
    kb = []
    row = []

    for m in range(0, 60, 5):
        label = f"{m:02d}"

        if m % 15 == 0:
            label = f"🔥{label}"

        row.append(InlineKeyboardButton(
            text=label,
            callback_data=f"min_{hour}_{m:02d}"
        ))

        if len(row) == 6:
            kb.append(row)
            row = []

    if row:
        kb.append(row)

    return InlineKeyboardMarkup(inline_keyboard=kb)


@dp.callback_query(F.data == "days_done")
async def days_done(c: CallbackQuery, state: FSMContext):
    await c.answer()

    data = await state.get_data()

    if not data.get("days"):
        await c.answer("Выбери хотя бы 1 день", show_alert=True)
        return

    await state.set_state(AddHabit.time)

    await c.message.edit_text(
        "Выбери час",
        reply_markup=get_hours_kb()
    )


@dp.callback_query(AddHabit.time, F.data.startswith("hour_"))
async def select_hour(c: CallbackQuery, state: FSMContext):
    await c.answer()

    hour = c.data.split("_")[1]

    await c.message.edit_text(
        "Выбери минуты",
        reply_markup=get_minutes_kb(hour)
    )


@dp.callback_query(AddHabit.time, F.data == "skip_time")
async def skip_time(c: CallbackQuery, state: FSMContext):
    await c.answer()

    await state.update_data(time=None, reminder=None)

    await finish_habit_creation(c, state)
    
    


@dp.callback_query(AddHabit.time, F.data.startswith("min_"))
async def select_minute(c: CallbackQuery, state: FSMContext):
    await c.answer()

    _, hour, minute = c.data.split("_")
    time = f"{hour}:{minute}"

    await state.update_data(time=time)

    # 🔥 ВАЖНО — меняем состояние
    await state.set_state(AddHabit.reminder)

    await c.message.edit_text(
        "Включить напоминание?",
        reply_markup=reminder_kb()
    )

@dp.callback_query(AddHabit.reminder, F.data.startswith("rem_"))
async def set_reminder(c: CallbackQuery, state: FSMContext):
    await c.answer()

    if c.data == "rem_skip":
        reminder = None
    else:
        reminder = int(c.data.split("_")[1])

    await state.update_data(reminder=reminder)

    await finish_habit_creation(c, state)

@dp.message(AddHabit.time)
async def set_time(m: Message, state: FSMContext):

    if not re.match(r"^\d{2}:\d{2}$", m.text):
        await m.answer("Формат времени: 12:30")
        return

    await state.update_data(time=m.text)

    # 🔥 ВАЖНО
    await state.set_state(AddHabit.reminder)

    await m.answer(
        "Включить напоминание?",
        reply_markup=reminder_kb()
    )

    
async def finish_habit_creation(c: CallbackQuery, state: FSMContext):
    data = await state.get_data()

    user_id = c.from_user.id

    name = data.get("name")
    days = data.get("days")
    h_type = data.get("type")
    time = data.get("time")
    task_type = data.get("task_type")
    reminder = data.get("reminder")

    # дни → строка
    if isinstance(days, list):
        days = ",".join(days)

    tz = get_user_timezone(user_id)

    add_habit(
        user_id,
        name,
        days,
        h_type,
        time,
        task_type,
        family_id=None,
        reminder=reminder,
        tz=tz
    )

    await state.clear()

    # ✅ сообщение + возврат в меню привычек
    await c.message.answer(
        "✅ Привычка создана",
        reply_markup=keyboards.habits_menu()
    )

    await c.answer()


@dp.callback_query(AddHabit.task_type)
async def set_task_type(c: CallbackQuery, state: FSMContext):
    await c.answer()

    task_type = "cycle" if "cycle" in c.data else "once"

    await state.update_data(task_type=task_type, days=[])

    await state.set_state(AddHabit.days)

    await c.message.edit_text(
        "Выбери дни",
        reply_markup=get_days_kb([])
    )

# -------------------------
# МОИ ПРИВЫЧКИ
# -------------------------

async def render_habits(user_id):
    habits = get_habits(user_id)

    if not habits:
        return "Нет привычек", keyboards.habits_menu()

    text = "📋 <b>Мои привычки</b>\n\n"
    kb = []

    from datetime import datetime
    today = datetime.now().strftime("%Y-%m-%d")

    for h in habits:
        hid, name, days, h_type, time, task_type, reminder = h

        order = {day: i for i, day in enumerate(DAYS)}
        days_list = sorted(days.split(","), key=lambda x: order[x])
        logs = get_habit_logs(hid, user_id)

        log_map = {}
        for l in logs:
            log_map[l[0]] = l[1]

        bar = ""

        for d in days_list:
            key = today + "_" + d

            if key in log_map:
                if log_map[key] == "done":
                    bar += get_user_color(user_id)
                elif log_map[key] == "skip":
                    bar += "🟥"
            else:
                bar += "⬜"

        labels = " ".join(days_list)

        title = name
        if time:
            title = f"{name} ({time})"

        text += (
            f"🔹 <b><i>{title}</i></b>\n"
            f"<code>{labels}</code>\n"
            f"<code>{bar}</code>\n"
            f"────────────\n"
        )

        if "⬜" in bar:
            kb.append([
                InlineKeyboardButton(text=name, callback_data=f"open_{hid}")
            ])

    kb.append([InlineKeyboardButton(text="⬅️ Назад", callback_data="habits")])

    return text, InlineKeyboardMarkup(inline_keyboard=kb)


async def show_my_habits(c: CallbackQuery, mode="personal"):
    USER_MODE[c.from_user.id] = mode

    habits = get_habits(c.from_user.id)
    users = get_family_members(c.from_user.id)

    from datetime import datetime, timedelta
    today = datetime.now().strftime("%Y-%m-%d")
    yesterday = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")

    text = "📋 <b>Мои привычки</b>\n\n"
    kb = []

    for h in habits:
        hid, name, days, h_type, time, task_type, reminder = h

        if mode == "personal" and h_type != "personal":
            continue
        if mode == "family" and h_type != "family":
            continue

        days_list = days.split(",")

        active_users = [c.from_user.id] if h_type == "personal" else users

        user_logs = {}
        for uid in active_users:
            logs = get_habit_logs(hid, uid)
            user_logs[uid] = {l[0]: l[1] for l in logs}

        # =========================
        # 🔥 РОВНАЯ ВЕРСТКА
        # =========================

        # подпись (1 пробел между днями)
        labels_line = " ".join(days_list)

        if h_type == "personal":
            bar_line = ""

            for d in days_list:
                key = today + "_" + d
                log_map = user_logs.get(c.from_user.id, {})

                if key in log_map:
                    if log_map[key] == "done":
                        block = get_user_color(c.from_user.id)
                    elif log_map[key] == "skip":
                        block = "🟥"
                else:
                    block = "⬜"

                bar_line += block  # ❗ БЕЗ ПРОБЕЛОВ

        else:
            rows = []

            for uid in active_users:
                row = ""
                log_map = user_logs.get(uid, {})

                for d in days_list:
                    key = today + "_" + d

                    if key in log_map:
                        if log_map[key] == "done":
                            block = get_user_color(uid)
                        elif log_map[key] == "skip":
                            block = "🟥"
                    else:
                        block = "⬜"

                    row += block  # ❗ БЕЗ ПРОБЕЛОВ

                rows.append(row)

            bar_line = "\n".join(rows)

        # =========================
        # вчера скрытие
        # =========================
        yesterday_done = True
        for d in days_list:
            key = yesterday + "_" + d
            for uid in active_users:
                log_map = user_logs.get(uid, {})
                if key not in log_map or log_map[key] != "done":
                    yesterday_done = False

        if yesterday_done:
            continue

        title = name
        if time:
            title = f"{name} ({time})"

        streak = get_streak(hid, c.from_user.id)
        if streak > 0:
            title += f" {streak}🔥"

        if "⬜" not in bar_line:
            title = f"<s>{title}</s>"

        text += (
            f"🔹 <b><i>{title}</i></b>\n"
            f"<code>{labels_line}</code>\n"
            f"<code>{bar_line}</code>\n"
            f"────────────\n"
        )

        if "⬜" in bar_line:
            kb.append([
                InlineKeyboardButton(text=name, callback_data=f"open_{hid}")
            ])

    if mode == "personal":
        kb.append([InlineKeyboardButton(text="👥 Общие", callback_data="my_family")])
    else:
        kb.append([InlineKeyboardButton(text="👤 Личные", callback_data="my_personal")])

    kb.append([InlineKeyboardButton(text="⬅️ Назад", callback_data="habits")])

    try:
        await c.message.edit_text(
            text,
            reply_markup=InlineKeyboardMarkup(inline_keyboard=kb),
            parse_mode="HTML"
        )
    except:
        await c.message.answer(
            text,
            reply_markup=InlineKeyboardMarkup(inline_keyboard=kb),
            parse_mode="HTML"
        )

@dp.callback_query(F.data == "habit_list")
async def habit_list(c: CallbackQuery):
    await show_my_habits(c)
 
@dp.callback_query(F.data == "my_family")
async def my_family(c: CallbackQuery):
    await show_my_habits(c, mode="family")

@dp.callback_query(F.data == "my_personal")
async def my_personal(c: CallbackQuery):
    await show_my_habits(c, mode="personal") 
 
@dp.callback_query(F.data.startswith("open_"))
async def open_habit(c: CallbackQuery):
    hid = int(c.data.split("_")[1])

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Выполнить", callback_data=f"choose_done_{hid}")],
        [InlineKeyboardButton(text="❌ Пропустить", callback_data=f"choose_skip_{hid}")],
        [InlineKeyboardButton(text="🗑 Удалить", callback_data=f"del_{hid}")],
        [InlineKeyboardButton(text="⬅️ Назад", callback_data="habit_list")]
    ])

    await c.message.edit_text("Выбери действие:", reply_markup=kb)
    
def get_streak(habit_id, user_id):
    habits = get_habits(user_id)

    habit = None
    for h in habits:
        if h[0] == habit_id:
            habit = h
            break

    if not habit:
        return 0

    hid, name, days, h_type, time, task_type, reminder = habit

    if task_type == "once":
        return 0

    users = [user_id]

    if h_type == "family":
        users = get_family_members(user_id)

    total_done = 0

    for uid in users:
        logs = get_habit_logs(habit_id, uid)

        for log_date, status in logs:
            if status == "done":
                total_done += 1

    # 🔥 для семейной — делим на участников
    if h_type == "family" and users:
        total_done = total_done // len(users)

    return total_done    
    
@dp.callback_query(F.data.startswith("choose_"))
async def choose_action(c: CallbackQuery):
    _, action, hid = c.data.split("_")
    hid = int(hid)

    users = get_family_members(c.from_user.id)

    habit = None

    # 🔥 ищем привычку у всех
    for uid in users:
        habits = get_habits(uid)
        for h in habits:
            if h[0] == hid:
                habit = h
                break
        if habit:
            break

    if not habit:
        return

    days = habit[2].split(",")

    # ✅ если 1 день
    if len(days) == 1:
        day = days[0]

        from datetime import datetime
        today = datetime.now().strftime("%Y-%m-%d")
        key = today + "_" + day

        logs = get_habit_logs(hid, c.from_user.id)

        for l in logs:
            if l[0] == key:
                await c.answer("Уже отмечено", show_alert=True)
                return

        if action == "done":
            add_habit_log(hid, c.from_user.id, key, "done")
            await c.answer("✅ Выполнено")
        else:
            add_habit_log(hid, c.from_user.id, key, "skip")
            await c.answer("❌ Пропущено")

        mode = USER_MODE.get(c.from_user.id, "personal")
        await show_my_habits(c, mode=mode)
        return

    # --- стандарт ---
    logs = get_habit_logs(hid, c.from_user.id)

    from datetime import datetime
    today = datetime.now().strftime("%Y-%m-%d")

    used_days = set()

    for log_date, status in logs:
        if log_date.startswith(today):
            day = log_date.split("_")[1]
            used_days.add(day)

    kb = []

    for d in days:
        if d not in used_days:
            kb.append([
                InlineKeyboardButton(
                    text=d,
                    callback_data=f"{action}_{hid}_{d}"
                )
            ])

    kb.append([InlineKeyboardButton(text="⬅️ Назад", callback_data="habit_list")])

    await c.message.edit_text("Выбери день:", reply_markup=InlineKeyboardMarkup(inline_keyboard=kb))


# -------------------------
# ПРОГРЕСС
# -------------------------
@dp.callback_query(F.data == "habit_progress")
async def habit_progress(c: CallbackQuery):
    try:
        await show_progress(c, mode="personal")
    except:
        await c.message.answer("Ошибка открытия прогресса")


# -------------------------
# ACTIONS (done / skip / delete)
# -------------------------

@dp.callback_query(F.data.startswith("done_"))
async def habit_done(c: CallbackQuery):
    _, hid, day = c.data.split("_")
    hid = int(hid)

    from datetime import datetime
    today = datetime.now().strftime("%Y-%m-%d")
    key = today + "_" + day

    logs = get_habit_logs(hid, c.from_user.id)

    # ❌ ЕСЛИ УЖЕ ЕСТЬ — НЕ ДАЕМ НАЖАТЬ
    for l in logs:
        if l[0] == key:
            await c.answer("Уже отмечено", show_alert=True)
            return

    add_habit_log(hid, c.from_user.id, key, "done")

    await c.answer("✅ Выполнено")

    mode = USER_MODE.get(c.from_user.id, "personal")
    await show_my_habits(c, mode=mode)

async def show_progress(c: CallbackQuery, mode="personal", period="week"):
    USER_MODE[c.from_user.id] = mode

    habits = get_habits(c.from_user.id)
    users = get_family_members(c.from_user.id)

    from datetime import datetime, timedelta
    now = datetime.now()

    if period == "week":
        start_date = now - timedelta(days=7)
    elif period == "month":
        start_date = now - timedelta(days=30)
    else:
        start_date = datetime(2000, 1, 1)

    text = f"📊 <b>Прогресс</b>\n\n"
    kb = []

    today = now.strftime("%Y-%m-%d")

    for h in habits:
        hid, name, days, h_type, time, task_type, reminder = h

        if mode == "personal" and h_type != "personal":
            continue
        if mode == "family" and h_type != "family":
            continue

        order = {day: i for i, day in enumerate(DAYS)}
        days_list = sorted(days.split(","), key=lambda x: order[x])

        active_users = [c.from_user.id] if h_type == "personal" else users

        user_logs = {}
        for uid in active_users:
            logs = get_habit_logs(hid, uid)

            log_map = {}
            for l in logs:
                date_str = l[0].split("_")[0]
                date = datetime.strptime(date_str, "%Y-%m-%d")

                if date >= start_date:
                    log_map[l[0]] = l[1]

            user_logs[uid] = log_map

        # =========================
        # 🔥 РОВНАЯ ВЕРСТКА
        # =========================

        labels_line = " ".join(days_list)

        if h_type == "personal":
            bar_line = ""

            for d in days_list:
                key = today + "_" + d
                log_map = user_logs.get(c.from_user.id, {})

                if key in log_map:
                    if log_map[key] == "done":
                        block = get_user_color(c.from_user.id)
                    elif log_map[key] == "skip":
                        block = "🟥"
                else:
                    block = "⬜"

                bar_line += block  # ❗ БЕЗ ПРОБЕЛОВ

        else:
            rows = []

            for uid in active_users:
                row = ""
                log_map = user_logs.get(uid, {})

                for d in days_list:
                    key = today + "_" + d

                    if key in log_map:
                        if log_map[key] == "done":
                            block = get_user_color(uid)
                        elif log_map[key] == "skip":
                            block = "🟥"
                    else:
                        block = "⬜"

                    row += block  # ❗ БЕЗ ПРОБЕЛОВ

                rows.append(row)

            bar_line = "\n".join(rows)

        title = name
        if time:
            title = f"{name} ({time})"

        text += (
            f"🔹 <b><i>{title}</i></b>\n"
            f"<code>{labels_line}</code>\n"
            f"<code>{bar_line}</code>\n"
            f"────────────\n"
        )

    if mode == "personal":
        kb.append([InlineKeyboardButton(text="👥 Общие", callback_data="progress_family")])
    else:
        kb.append([InlineKeyboardButton(text="👤 Личные", callback_data="progress_personal")])

    kb.append([
        InlineKeyboardButton(text="📅 Неделя", callback_data="prog_week"),
        InlineKeyboardButton(text="🗓 Месяц", callback_data="prog_month"),
        InlineKeyboardButton(text="📊 Всё", callback_data="prog_all")
    ])

    kb.append([InlineKeyboardButton(text="⬅️ Назад", callback_data="habits")])

    try:
        await c.message.edit_text(
            text,
            reply_markup=InlineKeyboardMarkup(inline_keyboard=kb),
            parse_mode="HTML"
        )
    except:
        await c.message.answer(
            text,
            reply_markup=InlineKeyboardMarkup(inline_keyboard=kb),
            parse_mode="HTML"
        )
    
@dp.callback_query(F.data == "prog_week")
async def prog_week(c: CallbackQuery):
    mode = USER_MODE.get(c.from_user.id, "personal")
    await show_progress(c, mode=mode, period="week")


@dp.callback_query(F.data == "prog_month")
async def prog_month(c: CallbackQuery):
    mode = USER_MODE.get(c.from_user.id, "personal")
    await show_progress(c, mode=mode, period="month")


@dp.callback_query(F.data == "prog_all")
async def prog_all(c: CallbackQuery):
    mode = USER_MODE.get(c.from_user.id, "personal")
    await show_progress(c, mode=mode, period="all")   

@dp.callback_query(F.data == "progress_family")
async def progress_family(c: CallbackQuery):
    await show_progress(c, mode="family")


@dp.callback_query(F.data == "progress_personal")
async def progress_personal(c: CallbackQuery):
    await show_progress(c, mode="personal")

@dp.callback_query(F.data.startswith("skip_"))
async def habit_skip(c: CallbackQuery):
    _, hid, day = c.data.split("_")
    hid = int(hid)

    from datetime import datetime
    today = datetime.now().strftime("%Y-%m-%d")
    key = today + "_" + day

    logs = get_habit_logs(hid, c.from_user.id)

    for l in logs:
        if l[0] == key:
            await c.answer("Уже отмечено", show_alert=True)
            return

    add_habit_log(hid, c.from_user.id, key, "skip")

    await c.answer("❌ Пропущено")

    mode = USER_MODE.get(c.from_user.id, "personal")
    await show_my_habits(c, mode=mode)


@dp.callback_query(F.data.startswith("del_"))
async def habit_delete(c: CallbackQuery):
    hid = int(c.data.split("_")[1])

    delete_habit(hid)

    await c.answer("🗑 Удалено")

    mode = USER_MODE.get(c.from_user.id, "personal")
    await show_my_habits(c, mode=mode)
    

        
def reminder_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⏰ За 10 мин", callback_data="rem_10")],
        [InlineKeyboardButton(text="⏰ За 15 мин", callback_data="rem_15")],
        [InlineKeyboardButton(text="⏰ За 30 мин", callback_data="rem_30")],
        [InlineKeyboardButton(text="⏰ За 1 час", callback_data="rem_60")],
        [InlineKeyboardButton(text="⏰ За 3 часа", callback_data="rem_180")],
        [InlineKeyboardButton(text="❌ Без напоминаний", callback_data="rem_skip")]
    ])
    
from datetime import datetime, timedelta

from database import cur

async def reminder_worker(bot: Bot):
    TIME_FIX = -60  # поправка сервера (в секундах)

    while True:
        try:
            cur.execute("""
                SELECT rowid, user_id, name, days, time, reminder, tz
                FROM habits
                WHERE time IS NOT NULL
            """)
            habits = cur.fetchall()

            for habit in habits:
                try:
                    rowid, user_id, name, days, time_str, reminder, tz = habit

                    if not time_str:
                        continue

                    # текущее время пользователя
                    user_now = datetime.utcnow() + timedelta(hours=tz)

                    # день недели
                    weekday_map = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"]
                    today = weekday_map[user_now.weekday()]

                    if today not in days.split(","):
                        continue

                    # время привычки
                    hour, minute = map(int, time_str.split(":"))

                    habit_time = user_now.replace(
                        hour=hour,
                        minute=minute,
                        second=0,
                        microsecond=0
                    )

                    # время напоминания
                    if reminder is not None:
                        remind_time = habit_time - timedelta(minutes=reminder)
                    else:
                        remind_time = habit_time

                    diff = (user_now - remind_time).total_seconds() + TIME_FIX

                    day_key = remind_time.strftime("%Y-%m-%d_%H:%M")

                    if 0 <= diff <= 30 and not was_reminded_today(rowid, user_id, day_key):
                        await bot.send_message(
                            user_id,
                            f"⏰ Напоминание: {name}"
                        )

                        mark_reminded(rowid, user_id, day_key)

                except Exception as e:
                    print("REMINDER ERROR:", e)

        except Exception as e:
            print("WORKER ERROR:", e)

        await asyncio.sleep(1)  # ✅ ЭТО ПРАВИЛЬНО


@dp.callback_query(F.data.startswith("tz_"))
async def set_timezone(c: CallbackQuery, state: FSMContext):
    await c.answer()

    tz = int(c.data.split("_")[1])
    data = await state.get_data()

    # =========================
    # 🔥 СТАРТ
    # =========================
    if "name" in data:
        await state.update_data(timezone=tz)

        # 👉 теперь НЕ color, а gender
        await state.set_state(StartStates.gender)

        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="👤", callback_data="gender_male")],
            [InlineKeyboardButton(text="👩", callback_data="gender_female")]
        ])

        await c.message.edit_text(
            "Выбери пол:",
            reply_markup=kb
        )

    # =========================
    # 🔥 НАСТРОЙКИ
    # =========================
    else:
        cur.execute(
            "UPDATE users SET timezone=? WHERE id=?",
            (tz, c.from_user.id)
        )
        conn.commit()

        await c.message.edit_text("✅ Часовой пояс обновлён")
        
@dp.callback_query(F.data.startswith("gender_"))
async def set_gender(c: CallbackQuery, state: FSMContext):
    await c.answer()

    gender = c.data.split("_")[1]

    await state.update_data(gender=gender)

    # 👉 теперь уже color
    await state.set_state(StartStates.color)

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="🟩", callback_data="color_🟩"),
            InlineKeyboardButton(text="🟦", callback_data="color_🟦"),
            InlineKeyboardButton(text="🟪", callback_data="color_🟪"),
            InlineKeyboardButton(text="🟧", callback_data="color_🟧"),
        ]
    ])

    await c.message.edit_text(
        "🎨 Выбери цвет привычек:",
        reply_markup=kb
    )        

@dp.message(F.text == "⚙️ Настройки")
async def settings_menu(m: Message):
    await m.answer(
        "⚙️ Настройки",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(text="🌍 Часовой пояс", callback_data="settings_tz"),
            ],
            [
                InlineKeyboardButton(text="🎨 Цвет", callback_data="set_color"),
                InlineKeyboardButton(text="✏️ Имя", callback_data="set_name"),
            ]
        ])
    )

@dp.callback_query(F.data == "set_color")
async def change_color(c: CallbackQuery, state: FSMContext):
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="🟩", callback_data="color_🟩"),
            InlineKeyboardButton(text="🟦", callback_data="color_🟦"),
            InlineKeyboardButton(text="🟪", callback_data="color_🟪"),
            InlineKeyboardButton(text="🟧", callback_data="color_🟧"),
        ]
    ])

    await c.message.answer("🎨 Выбери цвет:", reply_markup=kb)

@dp.callback_query(F.data == "settings_tz")
async def settings_timezone(c: CallbackQuery):
    await c.answer()

    await c.message.edit_text(
        "Выбери новый часовой пояс:",
        reply_markup=timezone_kb()
    )
   
def is_fin_enabled(user_id):
    cur.execute("SELECT fin_enabled FROM users WHERE id=?", (user_id,))
    res = cur.fetchone()
    return res[0] if res else 1
    
def toggle_fin(user_id):
    cur.execute("""
        UPDATE users
        SET fin_enabled = CASE WHEN fin_enabled=1 THEN 0 ELSE 1 END
        WHERE id=?
    """, (user_id,))
    conn.commit()

def set_fin_enabled(user_id, val: int):
    cur.execute("UPDATE users SET fin_enabled=? WHERE id=?", (val, user_id))
    conn.commit()


@dp.message(F.text == "💎 Подписка")
async def subscription_handler(m: Message):
    await m.answer(
        "Выбери функцию:",
        reply_markup=keyboards.subscription_menu()
    )

    await m.answer(
        "💰 Финансовая система\n"
        "«Самый богатый человек в Вавилоне»\n\n"
        "────────────\n\n"
        "Постулаты:\n\n"
        "1. Платите себе первым\n"
        "2. Контролируйте расходы\n"
        "3. Создавайте накопления\n"
        "4. Увеличивайте доход\n"
        "5. Инвестируйте\n"
        "6. Не влезайте в долги\n"
        "7. Защищайте капитал\n"
        "8. Думайте самостоятельно\n"
        "9. Учитесь на ошибках\n"
        "10. Используйте ресурсы разумно\n\n"
        "────────────\n\n"
        f"Статус: {status}",
        reply_markup=kb
    )

@dp.callback_query(F.data == "back_sub")
async def back_subscription(c: CallbackQuery):
    await c.message.answer(
        "Выбери функцию:",
        reply_markup=keyboards.subscription_menu()
    )

@dp.callback_query(F.data == "fin_toggle")
async def fin_toggle(c: CallbackQuery):
    enabled = is_fin_enabled(c.from_user.id)

    set_fin_enabled(c.from_user.id, 0 if enabled else 1)

    await sub_menu(c.message)
    
    
@dp.message(F.text == "💰 Финансы")
async def open_finance(m: Message):
    user_id = m.from_user.id

    await m.answer(
        "💰 Финансы",
        reply_markup=keyboards.budget_menu(is_fin_enabled(user_id))
    )

@dp.message(F.text == "🏋️ Привычки")
async def open_habits(m: Message):
    await m.answer(
        "🏋️ Привычки",
        reply_markup=keyboards.habits_menu()
    )    
    
@dp.message(F.text == "📊 Аналитика")
async def open_stats(m: Message):
    text = get_stats_text(m.from_user.id)

    await m.answer(
        text,
        reply_markup=keyboards.stats_menu(),
        parse_mode="HTML"
    )
    


def get_stats_text(user_id):
    users = get_family_members(user_id)

    text = "📊 Аналитика\n\n"

    total_savings = 0
    total_percent = 0
    percent_count = 0

    for uid in users:
        profile = get_user_profile(uid)
        name = profile[0] if profile and profile[0] else f"id:{uid}"

        expenses = get_expense_stats(uid)
        income = get_income_stats(uid)

        total_expense = sum(x[1] for x in expenses) if expenses else 0
        total_income = sum(x[1] for x in income) if income else 0
        balance = total_income - total_expense

        total_savings += get_savings_balance(uid)

        p = get_savings_percent(uid)
        if p > 0:
            total_percent += p
            percent_count += 1

        if len(users) > 1:
            text += f"👤 <b>{name}</b>\n"

        text += "💰 Доходы:\n"
        if income:
            for cat, amount in income:
                percent = int(amount / total_income * 100) if total_income else 0
                text += f"{cat} — {amount} ₽ ({percent}%)\n"
        else:
            text += "нет данных\n"

        text += "\n💸 Расходы:\n"
        if expenses:
            for cat, amount in expenses:
                percent = int(amount / total_expense * 100) if total_expense else 0
                text += f"{cat} — {amount} ₽ ({percent}%)\n"
        else:
            text += "нет данных\n"

        text += f"\n📈 Баланс: {balance} ₽"
        text += f"\nДоход: {total_income} ₽ | Расход: {total_expense} ₽"
        text += "\n"

    avg_percent = int(total_percent / percent_count) if percent_count else 0

    text += f"💰 Накопления — {total_savings:,} ₽\n\n"
    text += f"📊 Ты откладываешь: {avg_percent}%\n"

    if avg_percent == 0:
        text += "❌ Начни копить\n"
    elif avg_percent < 10:
        text += "⚠️ Ниже нормы\n"
    elif avg_percent < 15:
        text += "👍 Хорошо\n"
    else:
        text += "🔥 Отлично\n"

    text += "\n\n" + get_motivation_text()

    return text

@dp.callback_query(F.data == "open_savings")
async def open_savings(c: CallbackQuery):
    if not is_fin_enabled(c.from_user.id):
        await c.answer("Функция отключена", show_alert=True)
        return

    balance = get_savings_balance(c.from_user.id)

    await c.message.answer(
        f"💰 Накопления: {balance:,} ₽",
        reply_markup=keyboards.savings_menu()
    )

@dp.message(StartStates.name)
async def set_name(m: Message, state: FSMContext):
    await state.update_data(name=m.text)
    await state.set_state(StartStates.timezone)

    await m.answer(
        "Выбери время относительно МСК:",
        reply_markup=timezone_kb()
    )


async def finance_notifications_worker(bot: Bot):
    import asyncio
    from datetime import datetime, timedelta

    last_sent = {}

    while True:
        try:
            cur.execute("SELECT id, tz FROM users")
            users = cur.fetchall()

            for user_id, tz in users:
                now = datetime.utcnow() + timedelta(hours=tz)

                if now.weekday() == 0 and now.hour == 0:
                    key = f"{user_id}_{now.date()}"

                    if last_sent.get(user_id) == key:
                        continue

                    savings, percent = get_total_savings(user_id)

                    if percent == 0:
                        text = (
                            "💰 Финансовая система\n\n"
                            "«Часть того, что ты зарабатываешь,\nпринадлежит тебе»\n\n"
                            "Но сейчас ты не откладываешь ничего\n\n"
                            "Начни хотя бы с малого — 5–10%"
                        )
                    elif percent < 10:
                        text = "Ты начал платить себе,\nно пока меньше нормы\n\n10% — это база"
                    elif percent < 15:
                        text = "Ты платишь себе первым\n\nЭто фундамент роста"
                    else:
                        text = "Ты создаёшь капитал быстрее большинства\n\nДеньги начинают работать на тебя"

                    await bot.send_message(user_id, text)

                    last_sent[user_id] = key

        except Exception as e:
            print("FIN WORKER ERROR:", e)

        await asyncio.sleep(60)
    
@dp.callback_query(F.data.startswith("color_"))
async def set_color_callback(c: CallbackQuery, state: FSMContext):
    color = c.data.split("_")[1]
    data = await state.get_data()

    if "name" in data:
        cur.execute("""
            UPDATE users
            SET name=?, timezone=?, color=?
            WHERE id=?
        """, (data["name"], data["timezone"], color, c.from_user.id))
        conn.commit()

        await state.clear()

        await c.message.answer("✅ Готово!")
        await c.message.answer("🏠 Главное меню", reply_markup=keyboards.get_main_menu())  
    
  
async def weekly_reset_worker():
    from datetime import datetime, timedelta
    import asyncio

    last_reset = {}

    while True:
        try:
            cur.execute("""
                SELECT DISTINCT user_id, tz
                FROM habits
            """)
            users = cur.fetchall()

            for user_id, tz in users:
                try:
                    user_now = datetime.utcnow() + timedelta(hours=tz)

                    week_key = f"{user_id}_{user_now.strftime('%Y-%W')}"

                    if (
                        user_now.weekday() == 0
                        and user_now.hour == 0
                        and user_now.minute == 0
                    ):
                        if last_reset.get(user_id) != week_key:

                            print(f"✅ RESET for user {user_id}")

                            # 🔥 ВОТ ЧТО НУЖНО
                            cur.execute("""
                                DELETE FROM habit_logs
                                WHERE user_id=?
                            """, (user_id,))
                            conn.commit()

                            last_reset[user_id] = week_key

                except Exception as e:
                    print("USER RESET ERROR:", e)

        except Exception as e:
            print("WEEKLY WORKER ERROR:", e)

        await asyncio.sleep(30)   
    
# =========================
# СЕМЬЯ
# =========================

from aiogram.fsm.state import State, StatesGroup

class FamilyStates(StatesGroup):
    create_name = State()
    create_password = State()
    join_code = State()
    join_password = State()


@dp.message(F.text == "👥 Семья")
async def family_menu(m: Message):
    family_id = get_family_id(m.from_user.id)

    if not family_id:
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="➕ Создать семью", callback_data="create_family")],
            [InlineKeyboardButton(text="🔗 Вступить", callback_data="join_family")]
        ])
        await m.answer("Ты не в семье", reply_markup=kb)
    else:
        name = get_family_name(family_id)
        members = get_family_members(m.from_user.id)

        members_text = ""
        for uid in members:
            profile = get_user_profile(uid)
            uname = profile[0] if profile else f"id:{uid}"
            members_text += f"• <b>{uname}</b>\n"

        kb = [
            [InlineKeyboardButton(text="📎 Мой код", callback_data="family_code")],
            [InlineKeyboardButton(text="🚪 Выйти", callback_data="leave_family")]
        ]

        if is_family_owner(m.from_user.id, family_id):
            kb.insert(0, [InlineKeyboardButton(text="✏️ Переименовать", callback_data="rename_family")])

        await m.answer(
            f"Ты в семье: <b>{name}</b>\n\n"
            f"Участники:\n{members_text}",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=kb),
            parse_mode="HTML"
        )

InlineKeyboardButton(text="✏️ Имя", callback_data="set_name")


class SettingsStates(StatesGroup):
    change_name = State()
    
@dp.callback_query(F.data == "set_name")
async def change_name(c: CallbackQuery, state: FSMContext):
    await state.set_state(SettingsStates.change_name)
    await c.message.answer("Введи новое имя")


@dp.message(SettingsStates.change_name)
async def set_name_settings(m: Message, state: FSMContext):
    set_user_profile(m.from_user.id, m.text, get_user_color(m.from_user.id))
    await state.clear()
    await m.answer("✅ Имя обновлено")

# -------- СОЗДАНИЕ --------

@dp.callback_query(F.data == "create_family")
async def create_family_start(c: CallbackQuery, state: FSMContext):
    await state.set_state(FamilyStates.create_name)
    await c.message.answer("Введи название семьи")


@dp.message(FamilyStates.create_name)
async def create_family_name(m: Message, state: FSMContext):
    await state.update_data(name=m.text)
    await state.set_state(FamilyStates.create_password)
    await m.answer("Придумай пароль для семьи")


@dp.message(FamilyStates.create_password)
async def create_family_password(m: Message, state: FSMContext):
    data = await state.get_data()

    fid = create_family(
        m.from_user.id,
        data["name"],
        m.text.strip()
    )

    await state.clear()

    await m.answer(
        f"Семья создана: <b>{data['name']}</b>\nКод: <code>{fid}</code>",
        parse_mode="HTML"
    )

    await m.answer("👥 Меню семьи", reply_markup=InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📎 Мой код", callback_data="family_code")],
        [InlineKeyboardButton(text="🚪 Выйти", callback_data="leave_family")]
    ]))
    
@dp.callback_query(F.data == "rename_family")
async def rename_family_start(c: CallbackQuery, state: FSMContext):
    await state.set_state(FamilyStates.create_name)
    await c.message.answer("Введи новое название семьи")


@dp.message(FamilyStates.create_name)
async def rename_family_name(m: Message, state: FSMContext):
    family_id = get_family_id(m.from_user.id)

    if not is_family_owner(m.from_user.id, family_id):
        await m.answer("❌ Только создатель может менять название")
        return

    cur.execute(
        "UPDATE families SET name=? WHERE id=?",
        (m.text, family_id)
    )
    conn.commit()

    await state.clear()
    await m.answer("✅ Название обновлено")    


# -------- ВСТУПЛЕНИЕ --------

@dp.callback_query(F.data == "join_family")
async def join_family_start(c: CallbackQuery, state: FSMContext):
    await state.set_state(FamilyStates.join_code)
    await c.message.answer("Введи код семьи")


@dp.message(FamilyStates.join_code)
async def join_family_code(m: Message, state: FSMContext):
    await state.update_data(code=m.text.strip())
    await state.set_state(FamilyStates.join_password)
    await m.answer("Введи пароль")


@dp.message(FamilyStates.join_password)
async def join_family_password(m: Message, state: FSMContext):
    data = await state.get_data()

    success, name = join_family(
        m.from_user.id,
        data["code"],
        m.text.strip()
    )

    await state.clear()

    if success:
        await m.answer(f"Добро пожаловать в семью: <b>{name}</b>", parse_mode="HTML")
    else:
        await m.answer("Неверный код или пароль")


# -------- ПРОЧЕЕ --------

@dp.callback_query(F.data == "family_code")
async def show_code(c: CallbackQuery):
    fid = get_family_id(c.from_user.id)
    await c.message.answer(f"Код семьи: <code>{fid}</code>", parse_mode="HTML")


@dp.callback_query(F.data == "leave_family")
async def leave_family_handler(c: CallbackQuery):
    leave_family(c.from_user.id)

    await c.message.answer(
        "Ты вышел из семьи",
        reply_markup=keyboards.get_main_menu()
    )
    
# =========================
# НАСТРОЙКИ
# =========================    
    

# =========================
# СТАРТ
# =========================

@dp.message(CommandStart())
async def start(m: Message, state: FSMContext):
    user = get_user_profile(m.from_user.id)

    # 🔥 ЕСЛИ УЖЕ ЕСТЬ — ПРОСТО В МЕНЮ
    if user and user[0]:
        await state.clear()
        await m.answer(
            "🏠 Главное меню",
            reply_markup=keyboards.get_main_menu()
        )
        return

    # 🔥 ЕСЛИ НОВЫЙ — ВСЁ КАК БЫЛО
    add_user(m.from_user.id, m.from_user.first_name)  # НЕ ТРОГАЕМ

    await state.set_state(StartStates.name)

    await m.answer(
        "👋 Добро пожаловать!\n\n"
        "Этот бот поможет тебе:\n"
        "— контролировать финансы\n"
        "— внедрять привычки\n"
        "— работать вместе с семьёй\n\n"
        "Как тебя назвать?"
    )


@dp.message(F.text.startswith("-"))
async def remove_money(m: Message):
    try:
        amount = int(m.text.replace("-", "").strip())
        remove_savings(m.from_user.id, amount)
        await m.answer(f"❌ Снято {amount} ₽ с накоплений")
    except:
        await m.answer("Ошибка")


async def main():
    asyncio.create_task(reminder_worker(bot))
    asyncio.create_task(weekly_reset_worker())
    asyncio.create_task(finance_notifications_worker(bot))

    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())    

