import sqlite3

conn = sqlite3.connect("data.db")
cur = conn.cursor()

cur.execute("""
CREATE TABLE IF NOT EXISTS users(
    user_id INTEGER PRIMARY KEY,
    family_id INTEGER
)
""")

cur.execute("""
CREATE TABLE IF NOT EXISTS families(
    id INTEGER PRIMARY KEY,
    code TEXT
)
""")

cur.execute("""
CREATE TABLE IF NOT EXISTS transactions(
    id INTEGER PRIMARY KEY,
    user_id INTEGER,
    username TEXT,
    amount INTEGER,
    type TEXT,
    category TEXT
)
""")

cur.execute("""
CREATE TABLE IF NOT EXISTS learn(
    word TEXT,
    category TEXT
)
""")

cur.execute("""
CREATE TABLE IF NOT EXISTS habits(
    id INTEGER PRIMARY KEY,
    user_id INTEGER,
    name TEXT,
    days TEXT,
    done TEXT
)
""")

conn.commit()