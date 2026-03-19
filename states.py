from aiogram.fsm.state import StatesGroup, State

class AddTransaction(StatesGroup):
    waiting_sum = State()
    waiting_category = State()
    waiting_custom_category = State()

class AddHabit(StatesGroup):
    name = State()
    type = State()
    days = State()
    time = State()

class Family(StatesGroup):
    create_password = State()
    join_code = State()
    join_password = State()