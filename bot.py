import asyncio
import re
import matplotlib.pyplot as plt
from datetime import datetime

from aiogram import Bot, Dispatcher
from aiogram.types import Message, CallbackQuery, FSInputFile
from aiogram.filters import CommandStart

from config import TOKEN
from database import *
from keyboards import *

bot = Bot(token=TOKEN, timeout=60)
dp = Dispatcher()

user_temp = {}

BASE = {
    "Еда": ["пятерочка","магнит","ашан","лента","еда","суши","роллы","pizza","burger","kfc","mcd"],
    "Быт": ["ozon","wildberries","аптека","ikea","fixprice"],
    "Транспорт": ["лукойл","газпром","benz","fuel"],
    "Развлечения": ["steam","netflix","игра"],
    "Кредиты": ["ипотека","кредит","loan"]
}

def detect(text):
    text = text.lower()

    for w, c in get_learn():
        if w in text:
            return c, True

    for cat, words in BASE.items():
        for w in words:
            if w in text:
                return cat, False

    return "Другое", False

def parse(text):
    nums = re.findall(r"\d+", text)
    return int(nums[0]) if nums else None

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
        data = get_stats(uid)

        if not data:
            await c.message.answer("Нет данных")
            return

        labels = [x[0] for x in data]
        sizes = [x[1] for x in data]

        total = sum(sizes)

        text = ""
        for l, s in zip(labels, sizes):
            perc = int(s / total * 100)
            text += f"{l} — {s} ₽ ({perc}%)\n"

        plt.clf()
        plt.pie(sizes, labels=labels, autopct='%1.1f%%')
        plt.savefig("chart.png")

        await c.message.answer(text)
        await c.message.answer_photo(FSInputFile("chart.png"))

    await c.answer()

@dp.message()
async def msg(m: Message):
    uid = m.from_user.id

    if uid not in user_temp:
        return

    amount = parse(m.text)
    cat, learned = detect(m.text)

    if not amount:
        await m.answer("Не понял сумму")
        return

    add_transaction(uid, amount, user_temp[uid]["type"], cat)

    if not learned:
        word = m.text.split()[-1]
        add_learn(word, cat)

    await m.answer(f"✅ {amount} ₽ → {cat}")

async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())