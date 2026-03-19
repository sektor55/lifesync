import sqlite3

conn = sqlite3.connect("data.db")
cursor = conn.cursor()

cursor.execute("""
CREATE TABLE IF NOT EXISTS users (
    user_id INTEGER PRIMARY KEY,
    family_id INTEGER
)
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS transactions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    amount INTEGER,
    type TEXT,
    category TEXT
)
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS learned (
    word TEXT,
    category TEXT
)
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS habits (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    name TEXT,
    type TEXT,
    days TEXT,
    time TEXT
)
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS habit_logs (
    user_id INTEGER,
    habit_id INTEGER,
    date TEXT,
    status TEXT
)
""")

conn.commit()

def add_transaction(user_id, amount, t_type, category):
    cursor.execute("INSERT INTO transactions (user_id, amount, type, category) VALUES (?, ?, ?, ?)",
                   (user_id, amount, t_type, category))
    conn.commit()

def get_stats(user_id):
    cursor.execute("SELECT category, SUM(amount) FROM transactions WHERE user_id=? AND type='expense' GROUP BY category",
                   (user_id,))
    return cursor.fetchall()

def add_learn(word, category):
    cursor.execute("INSERT INTO learned VALUES (?, ?)", (word, category))
    conn.commit()

def get_learn():
    cursor.execute("SELECT word, category FROM learned")
    return cursor.fetchall()