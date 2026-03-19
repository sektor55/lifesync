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

conn.commit()

def add_transaction(uid, amount, t, cat):
    cur.execute("INSERT INTO transactions VALUES(?,?,?,?)",(uid,amount,t,cat))
    conn.commit()

def get_stats(uid):
    cur.execute("SELECT category, SUM(amount) FROM transactions WHERE user_id=? AND type='expense' GROUP BY category",(uid,))
    return cur.fetchall()