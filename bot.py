import asyncio
import sqlite3
import re
import random
from datetime import datetime
import matplotlib.pyplot as plt

from aiogram import Bot, Dispatcher
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import CommandStart

from config import TOKEN

bot = Bot(token=TOKEN)
dp = Dispatcher()

# ===================== БД =====================

conn = sqlite3.connect("data.db")
cur = conn.cursor()

cur.execute("""
CREATE TABLE IF NOT EXISTS transactions(
uid INT, amount INT, type TEXT, category TEXT, user TEXT
)
""")

cur.execute("""
CREATE TABLE IF NOT EXISTS learn(
word TEXT, category TEXT
)
""")

cur.execute("""
CREATE TABLE IF NOT EXISTS habits(
id INTEGER PRIMARY KEY AUTOINCREMENT,
uid INT, name TEXT, days TEXT, done TEXT
)
""")

cur.execute("""
CREATE TABLE IF NOT EXISTS family(
code TEXT, password TEXT
)
""")

cur.execute("""
CREATE TABLE IF NOT EXISTS family_members(
code TEXT, uid INT, name TEXT
)
""")

conn.commit()

# ===================== ПАМЯТЬ =====================

user_temp = {}

LIMIT = 50

# ===================== БАЗА =====================

BASE = {
    "Еда": ["пятерочка","магнит","ашан","лента","burger","kfc","pizza","суши","роллы"],
    "Транспорт": ["лукойл","газпром","shell","benz","fuel"],
    "Быт": ["ozon","wildberries","ikea","аптека"],
    "Развлечения": ["steam","netflix","игра"]
}

# ===================== КНОПКИ =====================

def main_menu():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📊 Бюджет", callback_data="budget")],
        [InlineKeyboardButton(text="🏋️ Привычки", callback_data="habits")],
        [InlineKeyboardButton(text="👨‍👩‍👧 Семья", callback_data="family")]
    ])

def budget_menu():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💸 Расход", callback_data="exp")],
        [InlineKeyboardButton(text="💰 Доход", callback_data="inc")],
        [InlineKeyboardButton(text="📈 Аналитика", callback_data="stats")],
        [InlineKeyboardButton(text="⬅️ Назад", callback_data="back")]
    ])

def confirm_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Да", callback_data="yes")],
        [InlineKeyboardButton(text="❌ Нет", callback_data="no")]
    ])

def days_kb(selected):
    days = ["Пн","Вт","Ср","Чт","Пт","Сб","Вс"]
    kb = []
    row = []
    for d in days:
        text = f"✅ {d}" if d in selected else d
        row.append(InlineKeyboardButton(text=text, callback_data=f"day_{d}"))
    kb.append(row)
    kb.append([InlineKeyboardButton(text="Готово", callback_data="days_done")])
    return InlineKeyboardMarkup(inline_keyboard=kb)

# ===================== ЛОГИКА =====================

def detect(text):
    text = text.lower()

    cur.execute("SELECT * FROM learn")
    for w, c in cur.fetchall():
        if w in text:
            return c, True

    for cat, words in BASE.items():
        for w in words:
            if w in text:
                return cat, False

    return None, False

def parse(text):
    nums = re.findall(r"\d+", text)
    return int(nums[0]) if nums else None

# ===================== START =====================

@dp.message(CommandStart())
async def start(m: Message):
    await m.answer("🚀 LifeSync", reply_markup=main_menu())

# ===================== CALLBACK =====================

@dp.callback_query()
async def click(c: CallbackQuery):
    uid = c.from_user.id

    if c.data == "budget":
        await c.message.edit_text("📊 Бюджет", reply_markup=budget_menu())

    elif c.data == "exp":
        user_temp[uid] = {"type": "expense"}
        await c.message.answer("Введи сумму")

    elif c.data == "inc":
        user_temp[uid] = {"type": "income"}
        await c.message.answer("Введи сумму")

    elif c.data == "stats":
        cur.execute("SELECT category, SUM(amount) FROM transactions WHERE uid=? AND type='expense' GROUP BY category", (uid,))
        data = cur.fetchall()

        if not data:
            await c.message.answer("Нет данных")
            return

        labels = [x[0] for x in data]
        sizes = [x[1] for x in data]

        total = sum(sizes)

        text = ""
        for l, s in data:
            perc = int(s/total*100)
            text += f"{l} — {s} ₽ ({perc}%)\n"

        plt.clf()
        plt.pie(sizes, labels=[f"{l}\n{s}₽" for l,s in data], autopct='%1.1f%%')
        plt.savefig("chart.png")

        await c.message.answer(text)
        await c.message.answer_photo(open("chart.png","rb"))

    elif c.data.startswith("day_"):
        day = c.data.split("_")[1]
        days = user_temp[uid].setdefault("days", [])

        if day in days:
            days.remove(day)
        else:
            days.append(day)

        await c.message.edit_reply_markup(reply_markup=days_kb(days))

    elif c.data == "habits":
        await c.message.edit_text("🏋️ Привычки", reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="➕ Добавить", callback_data="add_habit")],
            [InlineKeyboardButton(text="📋 Мои", callback_data="my_habits")],
            [InlineKeyboardButton(text="⬅️ Назад", callback_data="back")]
        ]))

    elif c.data == "add_habit":
        user_temp[uid] = {}
        await c.message.answer("Название привычки")

    elif c.data == "days_done":
        name = user_temp[uid]["name"]
        days = ",".join(user_temp[uid]["days"])
        cur.execute("INSERT INTO habits(uid,name,days,done) VALUES(?,?,?,?)",
                    (uid,name,days,""))
        conn.commit()
        await c.message.answer("Добавлено ✅", reply_markup=main_menu())

    elif c.data == "family":
        await c.message.edit_text("👨‍👩‍👧 Семья", reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="➕ Создать", callback_data="fam_create")],
            [InlineKeyboardButton(text="👥 Участники", callback_data="fam_members")],
            [InlineKeyboardButton(text="⬅️ Назад", callback_data="back")]
        ]))

    elif c.data == "fam_create":
        code = f"FAM-{random.randint(1000,9999)}"
        user_temp[uid] = {"code": code}
        await c.message.answer(f"Код: {code}\nВведи пароль")

    elif c.data == "back":
        await c.message.edit_text("🏠 Меню", reply_markup=main_menu())

    await c.answer()

# ===================== MESSAGE =====================

@dp.message()
async def msg(m: Message):
    uid = m.from_user.id

    # привычки
    if uid in user_temp and "name" not in user_temp[uid]:
        user_temp[uid]["name"] = m.text
        user_temp[uid]["days"] = []
        await m.answer("Выбери дни", reply_markup=days_kb([]))
        return

    if uid not in user_temp:
        return

    amount = parse(m.text)
    cat, learned = detect(m.text)

    if not amount:
        await m.answer("Не понял сумму")
        return

    if not cat:
        user_temp[uid]["custom"] = True
        user_temp[uid]["amount"] = amount
        await m.answer("Введи категорию")
        return

    cur.execute("INSERT INTO transactions VALUES(?,?,?,?,?)",
                (uid, amount, user_temp[uid]["type"], cat, m.from_user.first_name))
    conn.commit()

    await m.answer(f"{amount} ₽ → {cat}", reply_markup=budget_menu())

# ===================== RUN =====================

async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())