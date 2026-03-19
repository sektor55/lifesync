import asyncio
import re
import random
import matplotlib.pyplot as plt

from aiogram import Bot, Dispatcher
from aiogram.types import Message, CallbackQuery, FSInputFile
from aiogram.filters import CommandStart

from config import TOKEN
from database import *
from keyboards import *
from states import user_state

bot = Bot(token=TOKEN)
dp = Dispatcher()

LIMIT = 50


BASE = {
    "Еда": ["пятерочка","магнит","ашан","еда","kfc","mcd","burger"],
    "Быт": ["ozon","wildberries","аптека"],
    "Транспорт": ["лукойл","газпром","бензин"],
    "Развлечения": ["steam","netflix"],
    "Кредиты": ["кредит","ипотека"]
}


def detect(text):
    text = text.lower()

    for w, c in cur.execute("SELECT * FROM learn"):
        if w in text:
            return c, True, w

    for cat, words in BASE.items():
        for w in words:
            if w in text:
                return cat, False, w

    return "Другое", False, None


def parse(text):
    nums = re.findall(r"\d+", text)
    return int(nums[0]) if nums else None


@dp.message(CommandStart())
async def start(m: Message):
    await m.answer("🚀 LifeSync", reply_markup=main_menu())


@dp.callback_query()
async def click(c: CallbackQuery):
    uid = c.from_user.id

    if c.data == "budget":
        await c.message.edit_text("📊 Бюджет", reply_markup=budget_menu())

    elif c.data == "habits":
        await c.message.edit_text("🏋️ Привычки", reply_markup=habits_menu())

    elif c.data == "family":
        await c.message.edit_text("👨‍👩‍👧 Семья", reply_markup=family_menu())

    elif c.data == "back":
        await c.message.edit_text("🏠 Меню", reply_markup=main_menu())

    # ---------- ДОХОД/РАСХОД ----------
    elif c.data in ["expense","income"]:
        user_state[uid] = {"type": c.data}
        await c.message.answer("Введи сумму или текст")

    elif c.data == "ok":
        d = user_state[uid]

        cur.execute("INSERT INTO transactions VALUES(NULL,?,?,?,?,?)",
                    (uid, c.from_user.username, d["amount"], d["type"], d["cat"]))
        conn.commit()

        if not d["learn"] and d["word"]:
            await c.message.answer("Запомнить?", reply_markup=confirm_menu())
            return

        await c.message.answer("Сохранено ✅")

    elif c.data.startswith("cat_"):
        user_state[uid]["cat"] = c.data.split("_")[1]
        await c.message.answer("Выбрано", reply_markup=confirm_menu())

    elif c.data == "change_cat":
        await c.message.answer("Выбери:", reply_markup=categories_menu())

    # ---------- ПРИВЫЧКИ ----------
    elif c.data == "add_habit":
        user_state[uid] = {"habit_name": True}
        await c.message.answer("Название:")

    elif c.data.startswith("day_"):
        day = c.data.split("_")[1]
        user_state[uid]["days"].append(day)
        await c.message.edit_reply_markup(reply_markup=days_menu(user_state[uid]["days"]))

    elif c.data == "days_done":
        d = user_state[uid]
        cur.execute("INSERT INTO habits VALUES(NULL,?,?,?,?)",
                    (uid, d["name"], ",".join(d["days"]), ""))
        conn.commit()
        await c.message.answer("Привычка создана")
        user_state.pop(uid)

    elif c.data == "progress":
        cur.execute("SELECT name,done FROM habits WHERE user_id=?", (uid,))
        data = cur.fetchall()

        text = ""
        for n,dn in data:
            done = len(dn.split(",")) if dn else 0
            bar = "🟩"*done + "⬜"*(7-done)
            text += f"{n}\n{bar}\n\n"

        await c.message.answer(text)

    elif c.data == "history":
        await c.message.answer("История: скоро (заготовка)")

    # ---------- СЕМЬЯ ----------
    elif c.data == "create_family":
        code = str(random.randint(10000,99999))
        cur.execute("INSERT INTO families VALUES(NULL,?)", (code,))
        conn.commit()
        await c.message.answer(f"Код: {code}")

    elif c.data == "join_family":
        user_state[uid] = {"join": True}
        await c.message.answer("Код семьи:")

    # ---------- СТАТИСТИКА ----------
    elif c.data == "stats":
        cur.execute("""
        SELECT category, SUM(amount)
        FROM transactions
        WHERE user_id=? AND type='expense'
        GROUP BY category
        """,(uid,))
        data = cur.fetchall()

        if not data:
            await c.message.answer("Нет данных")
            return

        labels = [x[0] for x in data]
        sizes = [x[1] for x in data]

        plt.clf()
        plt.pie(sizes, labels=labels, autopct='%1.1f%%')
        plt.savefig("chart.png")

        await c.message.answer_photo(FSInputFile("chart.png"))

    await c.answer()


@dp.message()
async def msg(m: Message):
    uid = m.from_user.id

    # JOIN
    if uid in user_state and user_state[uid].get("join"):
        cur.execute("SELECT id FROM families WHERE code=?", (m.text,))
        fam = cur.fetchone()
        if fam:
            cur.execute("INSERT OR REPLACE INTO users VALUES(?,?)", (uid, fam[0]))
            conn.commit()
            await m.answer("В семье ✅")
        else:
            await m.answer("Ошибка")
        user_state.pop(uid)
        return

    # HABIT NAME
    if uid in user_state and user_state[uid].get("habit_name"):
        user_state[uid] = {"name": m.text, "days": []}
        await m.answer("Выбери дни:", reply_markup=days_menu([]))
        return

    # ТРАНЗАКЦИЯ
    amount = parse(m.text)
    if amount and uid in user_state:
        cat, learned, word = detect(m.text)

        user_state[uid].update({
            "amount": amount,
            "cat": cat,
            "learn": learned,
            "word": word
        })

        await m.answer(f"{amount} ₽ → {cat}", reply_markup=confirm_menu())


async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())