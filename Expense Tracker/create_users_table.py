import sqlite3
import os

DB = os.path.join(os.path.dirname(__file__), 'app.db')  # match DATABASE in app.py

conn = sqlite3.connect(DB)
cur = conn.cursor()

cur.execute('''
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
''')
conn.commit()
conn.close()
print('users table ensured in', DB)
