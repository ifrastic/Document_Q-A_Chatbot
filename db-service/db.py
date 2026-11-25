import os
import sqlite3
from sql import MASTER, DOC, CHAT_HISTORY,FEEDBACK

DB_PATH = os.getenv("DATABASE_PATH", "embedding.db")
os.makedirs(os.path.dirname(DB_PATH) or ".", exist_ok=True)

def get_connection():
    return sqlite3.connect(DB_PATH)


def create_tables():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(MASTER)
    cursor.execute(DOC)
    cursor.execute(CHAT_HISTORY)
    cursor.execute(FEEDBACK)
    conn.commit()
    conn.close()