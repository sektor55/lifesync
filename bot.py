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
    await state.update_data(name=m.text)
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
            text = f"{d} 🟢"
        else:
            text = d

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

    await finish_habit_creation(c, state)  # ← ВОТ ЭТА СТРОКА

    await c.message.edit_text(
        "🏋️ Привычки",
        reply_markup=habits_menu()
    )
    
    


@dp.callback_query(AddHabit.time, F.data.startswith("min_"))
async def select_minute(c: CallbackQuery, state: FSMContext):
    _, hour, minute = c.data.split("_")
    time = f"{hour}:{minute}"

    await state.update_data(time=time)

    await finish_habit_creation(c, state)  # ← ВСТАВИТЬ

    await c.message.edit_text(
        "🏋️ Привычки",
        reply_markup=habits_menu()
    )
    
    


@dp.message(AddHabit.time)
async def set_time(m: Message, state: FSMContext):

    if not re.match(r"^\d{2}:\d{2}$", m.text):
        await m.answer("Формат времени: 12:30")
        return

    await state.update_data(time=m.text)

    await finish_habit_creation(m, state)  # ← ВСТАВИТЬ

    await m.answer("🏋️ Привычки", reply_markup=habits_menu())
    
async def finish_habit_creation(c: CallbackQuery | Message, state: FSMContext):
    data = await state.get_data()

    sorted_days = [d for d in DAYS if d in data["days"]]

    add_habit(
        user_id=c.from_user.id,
        name=data["name"],
        days=",".join(sorted_days),
        h_type=data["type"],
        time=data.get("time"),
        task_type=data.get("task_type")
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
@dp.callback_query(F.data == "habit_list")
async def habit_list(c: CallbackQuery):
    habits = get_habits(c.from_user.id)

    if not habits:
        await c.message.edit_text("Нет привычек", reply_markup=habits_menu())
        return

    text = "📋 <b>Мои привычки</b>\n\n"
    kb = []

    for h in habits:
        hid, name, days, *_ = h

        days_list = days.split(",")
        logs = get_habit_logs(hid, c.from_user.id)

        done = sum(1 for l in logs if l[1] == "done")
        skip = sum(1 for l in logs if l[1] == "skip")

        total = len(days_list)

        bar = (
            "🟩" * done +
            "🟥" * skip +
            "⬜" * (total - done - skip)
        )

        labels = " ".join(days_list)

        text += (
            f"🔹 <b>{name}</b>\n"
            f"📅 {labels}\n"
            f"{bar}\n"
            f"────────────\n"
        )

        kb.append([
            InlineKeyboardButton(text=name, callback_data=f"open_{hid}")
        ])

    kb.append([InlineKeyboardButton(text="⬅️ Назад", callback_data="habits")])

    await c.message.edit_text(
        text,
        reply_markup=InlineKeyboardMarkup(inline_keyboard=kb),
        parse_mode="HTML"
    )
    
@dp.callback_query(F.data.startswith("open_"))
async def open_habit(c: CallbackQuery):
    hid = int(c.data.split("_")[1])

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Выполнено", callback_data=f"done_{hid}")],
        [InlineKeyboardButton(text="❌ Пропустить", callback_data=f"skip_{hid}")],
        [InlineKeyboardButton(text="🗑 Удалить", callback_data=f"del_{hid}")],
        [InlineKeyboardButton(text="⬅️ Назад", callback_data="habit_list")]
    ])

    await c.message.edit_text("Действие:", reply_markup=kb)


# -------------------------
# ПРОГРЕСС
# -------------------------
@dp.callback_query(F.data == "habit_progress")
async def habit_progress(c: CallbackQuery):
    habits = get_habits(c.from_user.id)

    if not habits:
        await c.message.edit_text("Нет данных", reply_markup=habits_menu())
        return

    personal = []
    family = []

    for h in habits:
        if h[3] == "personal":
            personal.append(h)
        else:
            family.append(h)

    def build_block(title, items):
        text = f"\n<b>{title}</b>\n\n"

        for h in items:
            hid, name, days, *_ = h

            days_list = days.split(",")
            logs = get_habit_logs(hid, c.from_user.id)

            done = sum(1 for l in logs if l[1] == "done")
            skip = sum(1 for l in logs if l[1] == "skip")

            total = len(days_list)

            bar = (
                "🟩" * done +
                "🟥" * skip +
                "⬜" * (total - done - skip)
            )

            labels = " ".join(days_list)

            text += f"{name}\n{labels}\n{bar}\n\n"

        return text

    text = "📊 <b>Прогресс</b>\n"

    if personal:
        text += build_block("👤 Личные", personal)

    if family:
        text += build_block("👥 Общие", family)

    await c.message.edit_text(
        text,
        reply_markup=habits_menu(),
        parse_mode="HTML"
    )


# -------------------------
# ACTIONS (done / skip / delete)
# -------------------------

@dp.callback_query(F.data.startswith("done_"))
async def habit_done(c: CallbackQuery):
    hid = int(c.data.split("_")[1])
    add_habit_log(hid, c.from_user.id, "done")
    await c.answer("Отмечено ✅")
    await habit_list(c)
    await c.answer()



@dp.callback_query(F.data.startswith("skip_"))
async def habit_skip(c: CallbackQuery):
    hid = int(c.data.split("_")[1])
    add_habit_log(hid, c.from_user.id, "skip")
    await c.answer("Пропущено ❌")
    await habit_list(c)
    await c.answer()


@dp.callback_query(F.data.startswith("del_"))
async def habit_delete(c: CallbackQuery):
    hid = int(c.data.split("_")[1])
    delete_habit(hid, c.from_user.id)

    await c.answer("Удалено 🗑")
    await habit_list(c)
    await c.answer()
    


# =========================
# СТАРТ
# =========================
async def main():
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())