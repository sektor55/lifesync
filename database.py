import sqlite3

conn = sqlite3.connect("data.db")
cur = conn.cursor()

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


# СТАРОЕ (не ломаем)
def get_stats(uid):
    return get_expense_stats(uid)


def add_rule(uid, keyword, category):
    cur.execute("INSERT INTO rules VALUES(?,?,?)",(uid, keyword, category))
    conn.commit()


def get_rules(uid):
    cur.execute("SELECT keyword, category FROM rules WHERE user_id=?", (uid,))
    return cur.fetchall()