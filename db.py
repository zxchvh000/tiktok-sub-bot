import sqlite3
import json
from pathlib import Path
from typing import Optional

DB_PATH = Path(__file__).parent / "accounts.db"


def _get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    with _get_conn() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS accounts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                cookies TEXT NOT NULL,
                user_agent TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)


def add_account(username: str, cookies: list, user_agent: str) -> bool:
    try:
        with _get_conn() as conn:
            conn.execute(
                "INSERT INTO accounts (username, cookies, user_agent) VALUES (?, ?, ?)",
                (username, json.dumps(cookies), user_agent),
            )
        return True
    except sqlite3.IntegrityError:
        return False


def remove_account(username: str) -> bool:
    with _get_conn() as conn:
        cur = conn.execute("DELETE FROM accounts WHERE username = ?", (username,))
        return cur.rowcount > 0


def get_all_accounts() -> list[dict]:
    with _get_conn() as conn:
        rows = conn.execute("SELECT * FROM accounts").fetchall()
    return [
        {
            "id": r["id"],
            "username": r["username"],
            "cookies": json.loads(r["cookies"]),
            "user_agent": r["user_agent"],
        }
        for r in rows
    ]


def get_account_count() -> int:
    with _get_conn() as conn:
        return conn.execute("SELECT COUNT(*) FROM accounts").fetchone()[0]
