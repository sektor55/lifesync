import asyncio
from aiogram import Bot, Dispatcher, F
from aiogram.types import Message, CallbackQuery
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext

from config import TOKEN
from database import *
from keyboards import *
from states import *

bot = Bot(token=TOKEN)
dp = Dispatcher()

# --- СТАРТ ---
@dp.message(CommandStart())
async def start(m: Message):
    await m.answer("🚀 LifeSync", reply_markup=main_menu())

# --- НАВИГАЦИЯ ---
@dp.callback_query(F.data == "back_main")
async def back(c: CallbackQuery):
    await c.message.edit_text("Главное меню", reply_markup=main_menu())

# --- БЮДЖЕТ ---
@dp.callback_query(F.data == "budget")
async def budget(c: CallbackQuery):
    await c.message.edit_text("📊 Бюджет", reply_markup=budget_menu())

# --- РАСХОД ---
@dp.callback_query(F.data == "expense")
async def expense(c: CallbackQuery, state: FSMContext):
    await state.set_state(AddTransaction.waiting_sum)
    await c.message.answer("Введи сумму")

@dp.message(AddTransaction.waiting_sum)
async def get_sum(m: Message, state: FSMContext):
    await state.update_data(amount=int(m.text))
    await state.set_state(AddTransaction.waiting_category)
    await m.answer("Выбери категорию", reply_markup=categories_menu())

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

    await state.clear()
    await m.answer(f"✅ {data['amount']} ₽ → {m.text}", reply_markup=budget_menu())

# --- АНАЛИТИКА ---
@dp.callback_query(F.data == "stats")
async def stats(c: CallbackQuery):
    data = get_stats(c.from_user.id)

    text = ""
    total = sum(x[1] for x in data)

    for cat, val in data:
        perc = int(val / total * 100)
        text += f"{cat} — {val} ₽ ({perc}%)\n"

    await c.message.answer(text, reply_markup=budget_menu())

# --- ПРИВЫЧКИ ---
@dp.callback_query(F.data == "habits")
async def habits(c: CallbackQuery):
    await c.message.edit_text("🏋️ Привычки", reply_markup=habits_menu())

@dp.callback_query(F.data == "habit_add")
async def habit_add(c: CallbackQuery, state: FSMContext):
    await state.set_state(AddHabit.name)
    await c.message.answer("Название привычки")

@dp.message(AddHabit.name)
async def habit_name(m: Message, state: FSMContext):
    await state.update_data(name=m.text)
    await state.set_state(AddHabit.days)
    await m.answer("Дни (например: пн вт ср)")

@dp.message(AddHabit.days)
async def habit_days(m: Message, state: FSMContext):
    data = await state.get_data()

    cur.execute("INSERT INTO habits VALUES(?,?,?)",(m.from_user.id,data["name"],m.text))
    conn.commit()

    await state.clear()
    await m.answer("✅ Привычка добавлена", reply_markup=habits_menu())

# --- СЕМЬЯ ---
@dp.callback_query(F.data == "family")
async def family(c: CallbackQuery):
    await c.message.edit_text("👨‍👩‍👧 Семья", reply_markup=family_menu())

async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())