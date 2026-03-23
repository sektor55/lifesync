import sqlite3

conn = sqlite3.connect("data.db")
cur = conn.cursor()

# =========================
# HABITS UPDATE (ДОБАВЛЕНО)
# =========================
def init_habits_update():
    try:
        cur.execute("ALTER TABLE habits ADD COLUMN type TEXT")
    except:
        pass

    try:
        cur.execute("ALTER TABLE habits ADD COLUMN time TEXT")
    except:
        pass

    try:
        cur.execute("ALTER TABLE habits ADD COLUMN task_type TEXT")
    except:
        pass

    try:
        cur.execute("ALTER TABLE habits ADD COLUMN family_id TEXT")
    except:
        pass

    try:
        cur.execute("ALTER TABLE habits ADD COLUMN reminder INTEGER")
    except:
        pass

    # 🔥 ВОТ СЮДА ДОБАВЛЯЕМ
    cur.execute("""
    CREATE TABLE IF NOT EXISTS habit_reminders(
        habit_id INTEGER,
        user_id INTEGER,
        day_key TEXT
    )
    """)

    conn.commit()

init_habits_update()


cur.execute("""CREATE TABLE IF NOT EXISTS transactions(
user_id INTEGER,
amount INTEGER,
type TEXT,
category TEXT
)""")

cur.execute("""CREATE TABLE IF NOT EXISTS habits(
user_id INTEGER,
name TEXT,
days TEXT
)""")

cur.execute("""CREATE TABLE IF NOT EXISTS family(
user_id INTEGER,
family_id TEXT
)""")

cur.execute("""CREATE TABLE IF NOT EXISTS rules(
user_id INTEGER,
keyword TEXT,
category TEXT
)""")

conn.commit()


def add_transaction(uid, amount, t, cat):
    cur.execute("INSERT INTO transactions VALUES(?,?,?,?)",(uid,amount,t,cat))
    conn.commit()


# ✅ РАСХОДЫ
def get_expense_stats(uid):
    cur.execute("""
        SELECT category, SUM(amount)
        FROM transactions
        WHERE user_id=? AND type='expense'
        GROUP BY category
    """,(uid,))
    return cur.fetchall()


# ✅ ДОХОДЫ
def get_income_stats(uid):
    cur.execute("""
        SELECT category, SUM(amount)
        FROM transactions
        WHERE user_id=? AND type='income'
        GROUP BY category
    """,(uid,))
    return cur.fetchall()


# СТАРОЕ (НЕ ЛОМАЕМ)
def get_stats(uid):
    return get_expense_stats(uid)


def add_rule(uid, keyword, category):
    cur.execute("INSERT INTO rules VALUES(?,?,?)",(uid, keyword, category))
    conn.commit()


def get_rules(uid):
    cur.execute("SELECT keyword, category FROM rules WHERE user_id=?", (uid,))
    return cur.fetchall()


# =========================
# HABITS V2 (НОВОЕ)
# =========================

cur.execute("""
CREATE TABLE IF NOT EXISTS habit_logs(
habit_id INTEGER,
user_id INTEGER,
date TEXT,
status TEXT
)
""")

conn.commit()


def add_habit(user_id, name, days, h_type, time, task_type, family_id=None, reminder=None):
    cur.execute("""
        INSERT INTO habits(user_id, name, days, type, time, task_type, family_id, reminder)
        VALUES(?,?,?,?,?,?,?,?)
    """, (user_id, name, days, h_type, time, task_type, family_id, reminder))
    conn.commit()


def get_habits(user_id):
    cur.execute("""
        SELECT rowid, name, days, type, time, task_type, reminder
        FROM habits
        WHERE user_id=?
    """, (user_id,))
    return cur.fetchall()


def add_habit_log(habit_id, user_id, date, status):
    cur.execute("""
        INSERT INTO habit_logs VALUES(?,?,?,?)
    """, (habit_id, user_id, date, status))
    conn.commit()


def get_habit_logs(habit_id, user_id):
    cur.execute("""
        SELECT date, status FROM habit_logs
        WHERE habit_id=? AND user_id=?
    """, (habit_id, user_id))
    return cur.fetchall()


def delete_habit(habit_id):
    cur.execute("DELETE FROM habits WHERE rowid=?", (habit_id,))
    cur.execute("DELETE FROM habit_logs WHERE habit_id=?", (habit_id,))
    conn.commit()
    
    
def set_habit_reminder(habit_id, minutes_before):
    cur.execute("""
        UPDATE habits
        SET reminder = ?
        WHERE rowid = ?
    """, (minutes_before, habit_id))

    conn.commit()
    
def get_all_habits_with_time():
    cur.execute("""
        SELECT rowid, user_id, name, time, reminder
        FROM habits
        WHERE time IS NOT NULL AND reminder IS NOT NULL
    """)
    return cur.fetchall()
    
def was_reminded_today(habit_id, user_id, day_key):
    cur.execute("""
        SELECT 1 FROM habit_reminders
        WHERE habit_id=? AND user_id=? AND day_key=?
    """, (habit_id, user_id, day_key))
    return cur.fetchone() is not None


def mark_reminded(habit_id, user_id, day_key):
    cur.execute("""
        INSERT INTO habit_reminders (habit_id, user_id, day_key)
        VALUES (?, ?, ?)
    """, (habit_id, user_id, day_key))
    conn.commit()
    
  