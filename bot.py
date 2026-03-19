import asyncio
import re
import sqlite3
from datetime import datetime

import matplotlib.pyplot as plt

from aiogram import Bot, Dispatcher
from aiogram.types import Message, CallbackQuery, FSInputFile
from aiogram.filters import CommandStart
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

from config import TOKEN

bot = Bot(token=TOKEN)
dp = Dispatcher()

user_temp = {}

# ---------------- DATABASE ----------------

conn = sqlite3.connect("data.db")
cur = conn.cursor()

cur.execute("""
CREATE TABLE IF NOT EXISTS transactions(
    user_id INTEGER,
    amount INTEGER,
    type TEXT,
    category TEXT,
    date TEXT
)
""")

cur.execute("""
CREATE TABLE IF NOT EXISTS habits(
    user_id INTEGER,
    name TEXT,
    done INTEGER
)
""")

cur.execute("""
CREATE TABLE IF NOT EXISTS family(
    user_id INTEGER,
    name TEXT
)
""")

conn.commit()

# ---------------- BASE ----------------

BASE = {
    "Еда": [
        "еда","продукты","магазин","супермаркет",
        "пятерочка","магнит","лента","ашан","перекресток",
        "kfc","mcd","burger","пицца","pizza","суши",
        "кафе","ресторан","кофе"
    ],
    "Транспорт": [
        "бензин","заправка","fuel",
        "лукойл","газпром",
        "такси","uber","яндекс","метро"
    ],
    "Быт": [
        "ozon","wildberries","wb",
        "аптека","ikea","fixprice"
    ],
    "Развлечения": [
        "steam","игра","netflix",
        "кино","подписка"
    ],
    "Кредиты": [
        "кредит","ипотека","банк"
    ]
}

# ---------------- UTILS ----------------

def detect(text):
    text = text.lower()
    for cat, words in BASE.items():
        for w in words:
            if w in text:
                return cat
    return "Другое"

def parse(text):
    nums = re.findall(r"\d+", text)
    return int(nums[0]) if nums else None

# ---------------- KEYBOARDS ----------------

def main_menu():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📊 Бюджет", callback_data="budget")],
        [InlineKeyboardButton(text="🏆 Привычки", callback_data="habits")],
        [InlineKeyboardButton(text="👨‍👩‍👧‍👦 Семья", callback_data="family")]
    ])

def budget_menu():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💸 Расход", callback_data="expense")],
        [InlineKeyboardButton(text="💰 Доход", callback_data="income")],
        [InlineKeyboardButton(text="📈 Аналитика", callback_data="stats")]
    ])

# ---------------- HANDLERS ----------------

@dp.message(CommandStart())
async def start(m: Message):
    await m.answer("LifeSync 🚀", reply_markup=main_menu())

@dp.callback_query()
async def click(c: CallbackQuery):
    uid = c.from_user.id

    if c.data == "budget":
        await c.message.edit_text("📊 Бюджет", reply_markup=budget_menu())

    elif c.data == "expense":
        user_temp[uid] = {"type": "expense"}
        await c.message.answer("Введи сумму или сообщение банка")

    elif c.data == "income":
        user_temp[uid] = {"type": "income"}
        await c.message.answer("Введи сумму")

    elif c.data == "stats":
        cur.execute("SELECT category, SUM(amount) FROM transactions WHERE user_id=? GROUP BY category", (uid,))
        data = cur.fetchall()

        if not data:
            await c.message.answer("Нет данных")
            return

        labels = [x[0] for x in data]
        sizes = [x[1] for x in data]

        text = ""
        total = sum(sizes)

        for l, s in zip(labels, sizes):
            perc = int(s / total * 100)
            text += f"{l} — {s} ₽ ({perc}%)\n"

        plt.clf()
        plt.pie(sizes, labels=labels, autopct='%1.1f%%')
        plt.savefig("chart.png")

        await c.message.answer(text)
        await c.message.answer_photo(FSInputFile("chart.png"))

    elif c.data == "habits":
        await c.message.answer("🏆 Привычки\nНапиши: добавить привычку")

    elif c.data == "family":
        await c.message.answer("👨‍👩‍👧‍👦 Семья\nНапиши имя участника")

    await c.answer()

# ---------------- MESSAGE ----------------

@dp.message()
async def msg(m: Message):
    uid = m.from_user.id
    text = m.text.lower()

    # ---- привычки ----
    if "привычку" in text:
        name = text.replace("добавить привычку", "").strip()
        cur.execute("INSERT INTO habits VALUES (?, ?, 0)", (uid, name))
        conn.commit()
        await m.answer(f"Добавлена привычка: {name}")
        return

    # ---- семья ----
    if "семья" not in user_temp and len(text.split()) == 1:
        cur.execute("INSERT INTO family VALUES (?, ?)", (uid, text))
        conn.commit()
        await m.answer(f"Добавлен: {text}")
        return

    # ---- бюджет ----
    if uid not in user_temp:
        return

    amount = parse(text)
    if not amount:
        await m.answer("Не понял сумму")
        return

    cat = detect(text)

    cur.execute(
        "INSERT INTO transactions VALUES (?, ?, ?, ?, ?)",
        (uid, amount, user_temp[uid]["type"], cat, datetime.now().strftime("%Y-%m-%d"))
    )
    conn.commit()

    await m.answer(f"✅ {amount} ₽ → {cat}")

# ---------------- RUN ----------------

async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())