import asyncio
import re

import aiohttp
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

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

    add_transaction(c.from_user.id, data["amount"], "expense", data["category"])
    await state.clear()

    await c.message.answer(
        f"✅ {data['amount']} ₽ → {data['category']}",
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


@dp.callback_query(F.data == "income")
async def income(c: CallbackQuery, state: FSMContext):
    await state.set_state(AddIncome.sum)
    await c.message.answer("Введите сумму дохода")


@dp.message(AddIncome.sum)
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


@dp.callback_query(F.data == "inc_custom")
async def inc_custom_start(c: CallbackQuery, state: FSMContext):
    await state.set_state(AddIncome.custom)
    await c.message.answer("Введи категорию")


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

    add_transaction(c.from_user.id, data["amount"], "income", data["category"])
    await state.clear()

    await c.message.answer(
        f"✅ {data['amount']} ₽ → {data['category']}",
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

    # 🔥 БЕРЕМ ТОЛЬКО ЛИЧНЫЕ ДАННЫЕ
    user_income_map = {}
    user_expense_map = {}

    for uid in users:
        income = get_income_stats(uid) if len(users) == 1 else get_income_stats(uid)
        expense = get_expense_stats(uid) if len(users) == 1 else get_expense_stats(uid)

        # ❗ ФИЛЬТР: берем только его вклад
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

    # ДОХОДЫ
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
                    contributors.append((name, val))

            if len(contributors) > 1:
                for name, val in contributors:
                    text += f"  👤{name} — {val} ₽\n"

    else:
        text += "нет данных\n"

    # РАСХОДЫ
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
                    contributors.append((name, val))

            if len(contributors) > 1:
                for name, val in contributors:
                    text += f"  👤{name} — {val} ₽\n"

    else:
        text += "нет данных\n"

    text += "\n────────────\n"

    await c.message.answer(text, reply_markup=keyboards.stats_menu())



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

    plt.title("💸 Расходы (вся семья)", fontsize=20, color="white")

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

    plt.title("💰 Доходы (вся семья)", fontsize=20, color="white")

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

        days_list = days.split(",")
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
        # 🔥 НОВАЯ ВЕРСТКА
        # =========================

        if h_type == "personal":
            # --- ЛИЧНЫЕ ---
            labels_line = ""
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

                labels_line += f"{d} "
                bar_line += f"{block} "

        else:
            # --- СЕМЕЙНЫЕ (СТОЛБЦЫ) ---
            labels_line = ""
            rows = [""] * len(active_users)

            for d in days_list:
                labels_line += f"{d} "

                for i, uid in enumerate(active_users):
                    key = today + "_" + d
                    log_map = user_logs.get(uid, {})

                    if key in log_map:
                        if log_map[key] == "done":
                            block = get_user_color(uid)
                        elif log_map[key] == "skip":
                            block = "🟥"
                    else:
                        block = "⬜"

                    rows[i] += f"{block} "

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
            f"<code>{labels_line.strip()}</code>\n"
            f"<code>{bar_line.strip()}</code>\n"
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
    from datetime import datetime, timedelta

    logs = get_habit_logs(habit_id, user_id)

    if not logs:
        return 0

    log_map = {l[0]: l[1] for l in logs}

    today = datetime.now()
    streak = 0

    while True:
        week_ok = True

        for i in range(7):
            day = today - timedelta(days=i + streak * 7)
            day_str = day.strftime("%Y-%m-%d")

            # проверяем есть ли хоть одна запись "не done"
            found = False

            for key in log_map:
                if key.startswith(day_str):
                    if log_map[key] != "done":
                        week_ok = False
                    found = True

            if not found:
                week_ok = False

        if week_ok:
            streak += 1
        else:
            break

    return streak    
    
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

        days_list = days.split(",")

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
        # НОВАЯ ВЕРСТКА
        # =========================

        if h_type == "personal":
            labels_line = ""
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

                labels_line += f"{d} "
                bar_line += f"{block} "

        else:
            labels_line = ""
            rows = [""] * len(active_users)

            for d in days_list:
                labels_line += f"{d} "

                for i, uid in enumerate(active_users):
                    key = today + "_" + d
                    log_map = user_logs.get(uid, {})

                    if key in log_map:
                        if log_map[key] == "done":
                            block = get_user_color(uid)
                        elif log_map[key] == "skip":
                            block = "🟥"
                    else:
                        block = "⬜"

                    rows[i] += f"{block} "

            bar_line = "\n".join(rows)

        title = name
        if time:
            title = f"{name} ({time})"

        text += (
            f"🔹 <b><i>{title}</i></b>\n"
            f"<code>{labels_line.strip()}</code>\n"
            f"<code>{bar_line.strip()}</code>\n"
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
    TIME_FIX = -180  # поправка сервера (в секундах)

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

    # 🔥 ЕСЛИ это старт
    if "name" in data:
        await state.update_data(timezone=tz)

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

    # 🔥 ЕСЛИ это настройки
    else:
        cur.execute(
            "UPDATE users SET timezone=? WHERE id=?",
            (tz, c.from_user.id)
        )
        conn.commit()

        await c.message.edit_text("✅ Часовой пояс обновлён")

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
   
@dp.message(F.text == "💎 Подписка")
async def sub_menu(m: Message):
    await m.answer(
        "💎 Подписка\n\n"
        "🚧 Скоро здесь будет PRO-функционал"
    )   
    
    
@dp.message(F.text == "💰 Финансы")
async def open_finance(m: Message):
    await m.answer(
        "💰 Финансы",
        reply_markup=keyboards.budget_menu()
    )

@dp.message(F.text == "🏋️ Привычки")
async def open_habits(m: Message):
    await m.answer(
        "🏋️ Привычки",
        reply_markup=keyboards.habits_menu()
    )    
    
@dp.message(F.text == "📊 Аналитика")
async def open_stats(m: Message):
    await stats_inline(m)

async def stats_inline(m: Message):
    users = get_family_members(m.from_user.id)

    text = "📊 Аналитика\n\n"

    for uid in users:
        profile = get_user_profile(uid)
        name = profile[0] if profile and profile[0] else f"id:{uid}"

        expenses = get_expense_stats(uid)
        income = get_income_stats(uid)

        text += f"👤 <b>{name}</b>\n"

        text += "💰 Доходы:\n"
        if income:
            for cat, amount in income:
                text += f"{cat} — {amount} ₽\n"
        else:
            text += "нет данных\n"

        text += "\n💸 Расходы:\n"
        if expenses:
            for cat, amount in expenses:
                text += f"{cat} — {amount} ₽\n"
        else:
            text += "нет данных\n"

        text += "\n────────────\n\n"

    await m.answer(text, reply_markup=keyboards.stats_menu())    

def get_stats_text(user_id):
    users = get_family_members(user_id)

    text = "📊 Аналитика\n\n"

    for uid in users:
        profile = get_user_profile(uid)
        name = profile[0] if profile and profile[0] else f"id:{uid}"

        expenses = get_expense_stats(uid)
        income = get_income_stats(uid)

        total_expense = sum(x[1] for x in expenses) if expenses else 0
        total_income = sum(x[1] for x in income) if income else 0
        balance = total_income - total_expense

        if len(users) > 1:
            text += f"👤 <b>{name}</b>\n"

        # ДОХОДЫ
        text += "💰 Доходы:\n"
        if income:
            for cat, amount in income:
                percent = int(amount / total_income * 100) if total_income else 0
                text += f"{cat} — {amount} ₽ ({percent}%)\n"
        else:
            text += "нет данных\n"

        # РАСХОДЫ
        text += "\n💸 Расходы:\n"
        if expenses:
            for cat, amount in expenses:
                percent = int(amount / total_expense * 100) if total_expense else 0
                text += f"{cat} — {amount} ₽ ({percent}%)\n"
        else:
            text += "нет данных\n"

        text += f"\n📈 Баланс: {balance} ₽"
        text += f"\nДоход: {total_income} ₽ | Расход: {total_expense} ₽"

        text += "\n────────────\n\n"

    return text

class StartStates(StatesGroup):
    name = State()
    timezone = State()
    color = State()



@dp.message(StartStates.name)
async def set_name(m: Message, state: FSMContext):
    await state.update_data(name=m.text)
    await state.set_state(StartStates.timezone)

    await m.answer(
        "Выбери время относительно МСК:",
        reply_markup=timezone_kb()
    )

    
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

    else:
        set_user_profile(c.from_user.id, "User", color)

        await c.message.edit_text("✅ Цвет сохранён")  
    
    
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

        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="📎 Мой код", callback_data="family_code")],
            [InlineKeyboardButton(text="🚪 Выйти", callback_data="leave_family")]
        ])

        await m.answer(f"Ты в семье: <b>{name}</b>", reply_markup=kb, parse_mode="HTML")

 

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
    add_user(m.from_user.id, m.from_user.first_name)  # 🔥 ВАЖНО

    await state.set_state(StartStates.name)
    await m.answer(
        "👋 Добро пожаловать!\n\n"
        "Этот бот поможет тебе:\n"
        "— контролировать финансы\n"
        "— внедрять привычки\n"
        "— работать вместе с семьёй\n\n"
        "Как тебя назвать?"
    )


async def main():
    asyncio.create_task(reminder_worker(bot))
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())    

