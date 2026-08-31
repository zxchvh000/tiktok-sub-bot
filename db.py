import sqlite3
import json
import hashlib
import os
from pathlib import Path
from typing import Optional

DB_PATH = Path(__file__).parent / "accounts.db"


def _get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def _hash_password(password: str) -> str:
    salt = os.getenv("PASSWORD_SALT", "tiktok-bot-salt-2024")
    return hashlib.sha256(f"{salt}{password}".encode()).hexdigest()


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
        conn.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                email TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                telegram_id INTEGER UNIQUE,
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


def register_user(email: str, password: str, telegram_id: int) -> tuple[bool, str]:
    email = email.strip().lower()
    if not email or "@" not in email:
        return False, "Некорректный email"
    if len(password) < 4:
        return False, "Пароль минимум 4 символа"
    try:
        with _get_conn() as conn:
            conn.execute(
                "INSERT INTO users (email, password_hash, telegram_id) VALUES (?, ?, ?)",
                (email, _hash_password(password), telegram_id),
            )
        return True, "Регистрация успешна"
    except sqlite3.IntegrityError:
        return False, "Email уже зарегистрирован"


def login_user(email: str, password: str) -> Optional[dict]:
    email = email.strip().lower()
    with _get_conn() as conn:
        row = conn.execute(
            "SELECT * FROM users WHERE email = ? AND password_hash = ?",
            (email, _hash_password(password)),
        ).fetchone()
    if row:
        return {"id": row["id"], "email": row["email"], "telegram_id": row["telegram_id"]}
    return None


def get_user_by_email(email: str) -> Optional[dict]:
    email = email.strip().lower()
    with _get_conn() as conn:
        row = conn.execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()
    if row:
        return {"id": row["id"], "email": row["email"], "telegram_id": row["telegram_id"]}
    return None


def get_all_users() -> list[dict]:
    with _get_conn() as conn:
        rows = conn.execute("SELECT id, email, telegram_id, created_at FROM users").fetchall()
    return [
        {"id": r["id"], "email": r["email"], "telegram_id": r["telegram_id"], "created_at": r["created_at"]}
        for r in rows
    ]
