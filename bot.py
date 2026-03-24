import asyncio
import re

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from aiogram import Bot, Dispatcher, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton, FSInputFile
from aiogram.filters import CommandStart, StateFilter
from aiogram.fsm.context import FSMContext

from config import TOKEN
from database import *
from keyboards import *
from states import *
USER_MODE = {}

bot = Bot(token=TOKEN)
dp = Dispatcher()

# =========================
# РАСХОД (НЕ ТРОГАЕМ)
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
# КНОПКИ
# =========================
def confirm_kb(prefix="exp"):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Подтвердить", callback_data=f"{prefix}_confirm")],
        [InlineKeyboardButton(text="🔄 Изменить категорию", callback_data=f"{prefix}_change")]
    ])

# ✅ ДОБАВЛЕНО (новое меню статистики)
def stats_menu():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📊 График расходов", callback_data="graph_expense")],
        [InlineKeyboardButton(text="💰 График доходов", callback_data="graph_income")],
        [InlineKeyboardButton(text="⬅️ Назад", callback_data="budget")]
    ])


# =========================
# СТАРТ
# =========================
@dp.message(CommandStart())
async def start(m: Message):
    await m.answer("🚀 LifeSync", reply_markup=main_menu())


# =========================
# МЕНЮ
# =========================
@dp.callback_query(F.data == "budget")
async def budget(c: CallbackQuery):
    await c.message.edit_text("📊 Бюджет", reply_markup=budget_menu())


@dp.callback_query(F.data == "back_main")
async def back_main(c: CallbackQuery):
    await c.message.edit_text("Главное меню", reply_markup=main_menu())


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


@dp.callback_query(F.data == "inc_custom_handler")
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
# 📊 СТАТИСТИКА (ИСПРАВЛЕНА)
# =========================
@dp.callback_query(F.data == "stats")
async def stats(c: CallbackQuery):
    expense_data = get_expense_stats(c.from_user.id)
    income_data = get_income_stats(c.from_user.id)

    total_expense = sum(x[1] for x in expense_data) if expense_data else 0
    total_income = sum(x[1] for x in income_data) if income_data else 0
    balance = total_income - total_expense

    text = "📊 Аналитика\n\n"

    text += "💰 Доходы:\n"
    if income_data:
        for cat, val in income_data:
            perc = int(val / total_income * 100) if total_income else 0
            text += f"{cat} — {val} ₽ ({perc}%)\n"
    else:
        text += "нет данных\n"

    text += "\n💸 Расходы:\n"
    if expense_data:
        for cat, val in expense_data:
            perc = int(val / total_expense * 100) if total_expense else 0
            text += f"{cat} — {val} ₽ ({perc}%)\n"
    else:
        text += "нет данных\n"

    text += "\n"
    text += f"📈 Баланс: {balance} ₽\n"
    text += f"Доход: {total_income} ₽ | Расход: {total_expense} ₽"

    await c.message.answer(text, reply_markup=stats_menu())


# =========================
# 📉 ГРАФИК РАСХОДОВ
# =========================
@dp.callback_query(F.data == "graph_expense")
async def graph_expense(c: CallbackQuery):
    data = get_expense_stats(c.from_user.id)

    if not data:
        await c.message.answer("Нет данных", reply_markup=budget_menu())
        return

    cats = [x[0] for x in data]
    vals = [x[1] for x in data]

    total = sum(vals)

    def autopct(pct):
        val = int(pct * total / 100)
        return f"{val} ₽\n({int(pct)}%)"

    plt.figure(figsize=(7, 7), facecolor="#1e1e2f")

    colors = ["#00c896", "#ff6b6b", "#4dabf7", "#ffd43b", "#845ef7"]

    wedges, texts, autotexts = plt.pie(
        vals,
        labels=cats,
        autopct=autopct,
        startangle=140,
        colors=colors,
        textprops={"color": "white", "fontsize": 14},
        wedgeprops={"edgecolor": "#1e1e2f", "linewidth": 2}
    )

    plt.setp(autotexts, size=14, weight="bold", color="white")
    plt.setp(texts, size=16, weight="bold")

    plt.title("💸 Расходы", fontsize=20, color="white", pad=20)

    file_name = "expense.png"
    plt.savefig(file_name, facecolor="#1e1e2f")
    plt.close()

    photo = FSInputFile(file_name)
    await c.message.answer_photo(photo)
    await c.message.answer("📊 Готово", reply_markup=budget_menu())


# =========================
# 💰 ГРАФИК ДОХОДОВ
# =========================
@dp.callback_query(F.data == "graph_income")
async def graph_income(c: CallbackQuery):
    data = get_income_stats(c.from_user.id)

    if not data:
        await c.message.answer("Нет данных", reply_markup=budget_menu())
        return

    cats = [x[0] for x in data]
    vals = [x[1] for x in data]

    total = sum(vals)

    def autopct(pct):
        val = int(pct * total / 100)
        return f"{val} ₽\n({int(pct)}%)"

    plt.figure(figsize=(7, 7), facecolor="#1e1e2f")

    colors = ["#51cf66", "#339af0", "#fcc419", "#ff922b", "#f06595"]

    wedges, texts, autotexts = plt.pie(
        vals,
        labels=cats,
        autopct=autopct,
        startangle=140,
        colors=colors,
        textprops={"color": "white", "fontsize": 14},
        wedgeprops={"edgecolor": "#1e1e2f", "linewidth": 2}
    )

    plt.setp(autotexts, size=14, weight="bold", color="white")
    plt.setp(texts, size=16, weight="bold")

    plt.title("💰 Доходы", fontsize=20, color="white", pad=20)

    file_name = "income.png"
    plt.savefig(file_name, facecolor="#1e1e2f")
    plt.close()

    photo = FSInputFile(file_name)
    await c.message.answer_photo(photo)
    await c.message.answer("📊 Готово", reply_markup=budget_menu())
    
    # =========================
# 🏋️ ПРИВЫЧКИ
# =========================

from datetime import datetime

DAYS = ["Пн","Вт","Ср","Чт","Пт","Сб","Вс"]


@dp.callback_query(F.data == "habits")
async def habits_menu_handler(c: CallbackQuery):
    await c.message.edit_text("🏋️ Привычки", reply_markup=habits_menu())


@dp.callback_query(F.data == "habit_add")
async def habit_add_start(c: CallbackQuery, state: FSMContext):
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
    h_type = "personal" if "personal" in c.data else "family"
    await state.update_data(type=h_type, days=[])

    await state.set_state(AddHabit.task_type)

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔁 Цикличная", callback_data="task_cycle")],
        [InlineKeyboardButton(text="🎯 Разовая", callback_data="task_once")]
    ])

    await c.message.edit_text("Тип задачи", reply_markup=kb)


@dp.callback_query(AddHabit.days, F.data.startswith("day_"))
async def toggle_days(c: CallbackQuery, state: FSMContext):
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

    for h in range(1, 24):
        row.append(InlineKeyboardButton(text=f"{h:02d}", callback_data=f"hour_{h:02d}"))
        if len(row) == 6:
            kb.append(row)
            row = []

    row.append(InlineKeyboardButton(text="00", callback_data="hour_00"))
    kb.append(row)

    kb.append([InlineKeyboardButton(text="Пропустить", callback_data="skip_time")])
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


@dp.callback_query(AddHabit.days, F.data == "days_done")
async def days_done(c: CallbackQuery, state: FSMContext):
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
    hour = c.data.split("_")[1]

    await c.message.edit_text(
        "Выбери минуты",
        reply_markup=get_minutes_kb(hour)
    )


@dp.callback_query(AddHabit.time, F.data == "skip_time")
async def skip_time(c: CallbackQuery, state: FSMContext):
    await state.update_data(time=None)
    await finish_habit_creation(c, state)
    
    


@dp.callback_query(AddHabit.time, F.data.startswith("min_"))
async def select_minute(c: CallbackQuery, state: FSMContext):
    _, hour, minute = c.data.split("_")
    time = f"{hour}:{minute}"

    await state.update_data(time=time)

    await c.message.edit_text(
        "Включить напоминание?",
        reply_markup=reminder_kb()
    )

@dp.callback_query(F.data.startswith("rem_"))
async def set_reminder(c: CallbackQuery, state: FSMContext):
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

    await finish_habit_creation(m, state)  # ← ВСТАВИТЬ

    
async def finish_habit_creation(c: CallbackQuery | Message, state: FSMContext):
    data = await state.get_data()

    sorted_days = [d for d in DAYS if d in data["days"]]

    tz = 0  # временно

    add_habit(
        user_id=c.from_user.id,
        name=data["name"],
        days=",".join(sorted_days),
        h_type=data["type"],
        time=data.get("time"),
        task_type=data.get("task_type"),
        family_id=None,
        reminder=data.get("reminder"),
        tz=tz
    )

    await state.clear()

    if isinstance(c, CallbackQuery):
        await c.message.edit_text("🏋️ Привычки", reply_markup=habits_menu())
    else:
        await c.answer("🏋️ Привычки", reply_markup=habits_menu())    


@dp.callback_query(AddHabit.task_type)
async def set_task_type(c: CallbackQuery, state: FSMContext):
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
        return "Нет привычек", habits_menu()

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
                    bar += "🟩"
                elif log_map[key] == "skip":
                    bar += "🟥"
            else:
                bar += "⬜"

        labels = " ".join(days_list)

        # 👉 время
        title = name
        if time:
            title = f"{name} ({time})"

        text += (
            f"🔹 <b><i>{title}</i></b>\n"
            f"<code>{labels}</code>\n"
            f"<code>{bar}</code>\n"
            f"────────────\n"
        )

        # 👉 скрываем если полностью выполнена
        if "⬜" in bar:
            kb.append([
                InlineKeyboardButton(text=name, callback_data=f"open_{hid}")
            ])

    kb.append([InlineKeyboardButton(text="⬅️ Назад", callback_data="habits")])

    return text, InlineKeyboardMarkup(inline_keyboard=kb)

@dp.callback_query(F.data == "habit_list")
async def habit_list(c: CallbackQuery):
    mode = USER_MODE.get(c.from_user.id, "personal")

    try:
        await show_my_habits(c, mode=mode)
    except:
        await c.message.answer("Ошибка открытия привычек")


async def show_my_habits(c: CallbackQuery, mode="personal"):
    USER_MODE[c.from_user.id] = mode

    habits = get_habits(c.from_user.id)

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
        logs = get_habit_logs(hid, c.from_user.id)

        log_map = {l[0]: l[1] for l in logs}

        bar = ""
        all_done_today = True

        for d in days_list:
            key = today + "_" + d

            if key in log_map:
                if log_map[key] == "done":
                    bar += "🟩"
                elif log_map[key] == "skip":
                    bar += "🟥"
                    all_done_today = False
            else:
                bar += "⬜"
                all_done_today = False

        # 🔥 ЕСЛИ ВЧЕРА БЫЛО ПОЛНОСТЬЮ СДЕЛАНО → СКРЫВАЕМ
        yesterday_done = True
        for d in days_list:
            key = yesterday + "_" + d
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

        # 🔥 если всё выполнено сегодня → зачеркиваем
        if "⬜" not in bar:
            title = f"<s>{title}</s>"

        text += (
            f"🔹 <b><i>{title}</i></b>\n"
            f"<code>{' '.join(days_list)}</code>\n"
            f"<code>{bar}</code>\n"
            f"────────────\n"
        )

        # показываем только если есть пустые
        if "⬜" in bar:
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

    habits = get_habits(c.from_user.id)
    habit = next((h for h in habits if h[0] == hid), None)

    if not habit:
        return

    days = habit[2].split(",")

    # ✅ ЕСЛИ ТОЛЬКО 1 ДЕНЬ — НЕ СПРАШИВАЕМ
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
        return)

    # --- стандартная логика ---
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
        logs = get_habit_logs(hid, c.from_user.id)

        log_map = {}

        for l in logs:
            date_str = l[0].split("_")[0]
            date = datetime.strptime(date_str, "%Y-%m-%d")

            if date >= start_date:
                log_map[l[0]] = l[1]

        bar = ""

        for d in days_list:
            key = today + "_" + d

            if key in log_map:
                if log_map[key] == "done":
                    bar += "🟩"
                elif log_map[key] == "skip":
                    bar += "🟥"
            else:
                bar += "⬜"

        title = name
        if time:
            title = f"{name} ({time})"

        text += (
            f"🔹 <b><i>{title}</i></b>\n"
            f"<code>{' '.join(days_list)}</code>\n"
            f"<code>{bar}</code>\n"
            f"────────────\n"
        )

    # 🔁 переключатели режимов
    if mode == "personal":
        kb.append([InlineKeyboardButton(text="👥 Общие", callback_data="progress_family")])
    else:
        kb.append([InlineKeyboardButton(text="👤 Личные", callback_data="progress_personal")])

    # 📅 периоды
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
    
async def reminder_worker():
    while True:
        from datetime import datetime, timedelta

        now_utc = datetime.utcnow()

        cur.execute("""
            SELECT rowid, user_id, name, days, time, reminder, tz
            FROM habits
            WHERE time IS NOT NULL AND reminder IS NOT NULL
        """)

        habits = cur.fetchall()

        for hid, uid, name, days, time, reminder, tz in habits:
            try:
                # ✅ локальное время пользователя
                now = now_utc + timedelta(hours=tz)
                today_str = now.strftime("%Y-%m-%d")

                days_list = days.split(",")
                current_day = ["Пн","Вт","Ср","Чт","Пт","Сб","Вс"][now.weekday()]

                if current_day not in days_list:
                    continue

                # ❌ уже сделано
                logs = get_habit_logs(hid, uid)

                if any(log_date.startswith(today_str) for log_date, _ in logs):
                    continue

                # --- время привычки ---
                h, m = map(int, time.split(":"))
                habit_time = now.replace(hour=h, minute=m, second=0, microsecond=0)

                remind_time = habit_time - timedelta(minutes=reminder)

                # ✅ если время ещё не наступило
                if now < remind_time:
                    continue

                # ❌ если сильно опоздали
                if now < remind_time:
                    continue

                if now > habit_time:
                    continue

                day_key = f"{today_str}_{current_day}"

                if was_reminded_today(hid, uid, day_key):
                    continue

                await bot.send_message(uid, f"⏰ Напоминание: {name}")

                mark_reminded(hid, uid, day_key)

            except Exception as e:
                print("Reminder error:", e)

        await asyncio.sleep(20)     
        
from datetime import datetime

def get_user_tz():
    now = datetime.now()
    utc = datetime.utcnow()
    import time
    return int(time.localtime().tm_gmtoff // 3600)        
# =========================
# СТАРТ
# =========================
async def main():
    asyncio.create_task(reminder_worker())
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())