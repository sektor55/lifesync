import sqlite3

conn = sqlite3.connect("data.db")
cur = conn.cursor()

# =========================
# HABITS UPDATE (ДОБАВЛЕНО)
# =========================
def init_habits_update():
    # ===== HABITS =====
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
        
    try:
        cur.execute("ALTER TABLE habits ADD COLUMN tz INTEGER DEFAULT 0")
    except:
        pass 
        
    try:
        cur.execute("ALTER TABLE users ADD COLUMN family_id INTEGER")
    except:
        pass            

    # ===== USERS =====
    cur.execute("""
    CREATE TABLE IF NOT EXISTS users(
        id INTEGER PRIMARY KEY,
        timezone INTEGER
    )
    """)

    # 🔥 ДОБАВЛЯЕМ НОВЫЕ ПОЛЯ БЕЗ ЛОМА
    try:
        cur.execute("ALTER TABLE users ADD COLUMN name TEXT")
    except:
        pass

    try:
        cur.execute("ALTER TABLE users ADD COLUMN color TEXT")
    except:
        pass

    conn.commit()

    # ===== REMINDERS =====
    cur.execute("""
    CREATE TABLE IF NOT EXISTS habit_reminders(
        habit_id INTEGER,
        user_id INTEGER,
        day_key TEXT
    )
    """)

    conn.commit()

init_habits_update()

# =========================
# USERS UPDATE (НОВОЕ)
# =========================
def init_users_update():
    try:
        cur.execute("ALTER TABLE users ADD COLUMN shared_finance INTEGER DEFAULT 1")
    except:
        pass

    conn.commit()

init_users_update()


cur.execute("""CREATE TABLE IF NOT EXISTS transactions(
user_id INTEGER,
amount INTEGER,
type TEXT,
category TEXT
)""")

cur.execute("""
CREATE TABLE IF NOT EXISTS habits(
    user_id INTEGER,
    name TEXT,
    days TEXT,
    type TEXT,
    time TEXT,
    task_type TEXT,
    family_id TEXT,
    reminder INTEGER,
    tz INTEGER DEFAULT 0
)
""")

cur.execute("""
CREATE TABLE IF NOT EXISTS families(
    family_id TEXT,
    name TEXT,
    password TEXT
)
""")

cur.execute("""
CREATE TABLE IF NOT EXISTS family_members(
    user_id INTEGER,
    family_id TEXT
)
""")

cur.execute("""CREATE TABLE IF NOT EXISTS rules(
user_id INTEGER,
keyword TEXT,
category TEXT
)""")

conn.commit()


def add_transaction(uid, amount, t, cat):
    cur.execute("INSERT INTO transactions VALUES(?,?,?,?)",(uid,amount,t,cat))
    conn.commit()


def get_expense_stats(uid):
    family_id = get_family_id(uid)

    if family_id:
        cur.execute("SELECT shared_finance FROM users WHERE id=?", (uid,))
        res = cur.fetchone()
        shared = res[0] if res else 1

        if shared:
            users = get_family_members(uid)
        else:
            users = [uid]
    else:
        users = [uid]

    if not users:
        return []

    cur.execute(f"""
        SELECT category, SUM(amount)
        FROM transactions
        WHERE user_id IN ({",".join("?"*len(users))})
        AND type='expense'
        GROUP BY category
    """, users)

    return cur.fetchall()


def get_income_stats(uid):
    family_id = get_family_id(uid)

    if family_id:
        cur.execute("SELECT shared_finance FROM users WHERE id=?", (uid,))
        res = cur.fetchone()
        shared = res[0] if res else 1

        if shared:
            users = get_family_members(uid)
        else:
            users = [uid]
    else:
        users = [uid]

    if not users:
        return []

    cur.execute(f"""
        SELECT category, SUM(amount)
        FROM transactions
        WHERE user_id IN ({",".join("?"*len(users))})
        AND type='income'
        GROUP BY category
    """, users)

    return cur.fetchall()


def get_category_breakdown(uid, t):
    users = get_family_members(uid)

    cur.execute(f"""
        SELECT category, user_id, SUM(amount)
        FROM transactions
        WHERE user_id IN ({",".join("?"*len(users))})
        AND type=?
        GROUP BY category, user_id
    """, (*users, t))

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


def add_habit(user_id, name, days, h_type, time, task_type, family_id=None, reminder=None, tz=0):
    if h_type == "family":
        family_id = get_family_id(user_id)

    cur.execute("""
        INSERT INTO habits (user_id, name, days, type, time, task_type, family_id, reminder, tz)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (user_id, name, days, h_type, time, task_type, family_id, reminder, tz))

    conn.commit()


def get_habits(user_id):
    family_id = get_family_id(user_id)

    if family_id:
        cur.execute("""
            SELECT rowid, name, days, type, time, task_type, reminder
            FROM habits
            WHERE user_id=? OR (family_id=? AND type='family')
        """, (user_id, family_id))
    else:
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
    
def add_user(user_id, name="User"):
    cur.execute("""
        INSERT OR IGNORE INTO users (id, name)
        VALUES (?, ?)
    """, (user_id, name))


def get_user(user_id):
    cur.execute("SELECT id FROM users WHERE id=?", (user_id,))
    return cur.fetchone()


def save_user_timezone(user_id, tz):
    cur.execute("UPDATE users SET timezone=? WHERE id=?", (tz, user_id))
    conn.commit()


def get_user_timezone(user_id):
    cur.execute("SELECT timezone FROM users WHERE id=?", (user_id,))
    res = cur.fetchone()
    return res[0] if res else None    
    
# =========================
# 👥 FAMILY
# =========================

import uuid

def create_family(user_id, name, password):
    family_id = str(uuid.uuid4())[:6]

    cur.execute(
        "INSERT INTO families VALUES (?, ?, ?)",
        (family_id, name, password)
    )

    cur.execute(
        "INSERT INTO family_members VALUES (?, ?)",
        (user_id, family_id)
    )

    conn.commit()
    return family_id


def join_family(user_id, family_id, password):
    cur.execute(
        "SELECT name, password FROM families WHERE family_id=?",
        (family_id,)
    )
    res = cur.fetchone()

    if not res or res[1] != password:
        return False, None

    cur.execute(
        "INSERT INTO family_members VALUES (?, ?)",
        (user_id, family_id)
    )

    conn.commit()
    return True, res[0]


def get_family(user_id):
    cur.execute(
        """SELECT f.family_id, f.name
           FROM families f
           JOIN family_members m ON f.family_id = m.family_id
           WHERE m.user_id=?""",
        (user_id,)
    )
    return cur.fetchone()


def leave_family(user_id):
    cur.execute(
        "DELETE FROM family_members WHERE user_id=?",
        (user_id,)
    )
    conn.commit()


def get_family_members(user_id):
    cur.execute(
        "SELECT family_id FROM family_members WHERE user_id=?",
        (user_id,)
    )
    res = cur.fetchone()

    if not res:
        return [user_id]

    family_id = res[0]

    cur.execute(
        "SELECT user_id FROM family_members WHERE family_id=?",
        (family_id,)
    )
    return [x[0] for x in cur.fetchall()]
    
def set_user_profile(user_id, name, color):
    cur.execute("""
        INSERT INTO users (id, name, color)
        VALUES (?, ?, ?)
        ON CONFLICT(id) DO UPDATE SET
            name=excluded.name,
            color=excluded.color
    """, (user_id, name, color))
    conn.commit()


def get_user_profile(user_id):
    cur.execute("""
        SELECT name, timezone, color FROM users WHERE id=?
    """, (user_id,))
    return cur.fetchone()    
    
import sqlite3

def ensure_family_column():
    conn = sqlite3.connect("data.db")
    cur = conn.cursor()

    try:
        cur.execute("ALTER TABLE users ADD COLUMN family_id INTEGER")
        conn.commit()
    except:
        pass

    conn.close()


def get_family_id(user_id):
    cur.execute("""
        SELECT family_id FROM family_members WHERE user_id=?
    """, (user_id,))
    
    res = cur.fetchone()
    return res[0] if res else None
   
ensure_family_column()   

def get_family_name(family_id):
    cur.execute("SELECT name FROM families WHERE id=?", (family_id,))
    row = cur.fetchone()
    return row[0] if row else "Без названия"