import asyncio
import json
import logging
import os

from aiogram import Bot, Dispatcher, Router, F
from aiogram.types import Message, FSInputFile
from aiogram.filters import CommandStart, Command
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties

import config
import db
from tiktok import extract_username, subscribe_with_all_accounts, login_to_tiktok

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

bot = Bot(token=config.BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher()
router = Router()
dp.include_router(router)

LOGGED_IN_USERS: set[int] = set()


def is_allowed(message: Message) -> bool:
    uid = message.from_user.id
    if uid in LOGGED_IN_USERS:
        return True
    if config.ALLOWED_USERS:
        return uid in config.ALLOWED_USERS
    return False


@router.message(CommandStart())
async def cmd_start(message: Message):
    if not is_allowed(message):
        return await message.answer("Нет доступа. Используйте /register или /login для входа.")
    await message.answer(
        "<b>TikTok Subscribe Bot</b>\n\n"
        "Команды:\n"
        "/sub &lt;ссылка&gt; — подписка всеми аккаунтами\n"
        "/addtiktok email пароль — добавить TikTok аккаунт\n"
        "/list — список аккаунтов\n"
        "/register &lt;email&gt; &lt;пароль&gt; — регистрация\n"
        "/login &lt;email&gt; &lt;пароль&gt; — вход\n"
        "/logout — выход\n"
        "/help — справка"
    )


@router.message(Command("help"))
async def cmd_help(message: Message):
    if not is_allowed(message):
        return
    await message.answer(
        "<b>TikTok Subscribe Bot</b>\n\n"
        "Используйте /sub &lt;ссылка&gt; чтобы подписаться на профиль TikTok.\n"
        "Пример: /sub https://tiktok.com/@user"
    )


@router.message(Command("register"))
async def cmd_register(message: Message):
    parts = message.text.split(maxsplit=2)
    if len(parts) < 3:
        return await message.answer("Формат: /register email пароль\nПример: /register user@mail.ru mypass123")
    email = parts[1].strip()
    password = parts[2].strip()
    ok, msg = db.register_user(email, password, message.from_user.id)
    if ok:
        LOGGED_IN_USERS.add(message.from_user.id)
        await message.answer(f"✅ {msg}\nДобро пожаловать!")
    else:
        await message.answer(f"❌ {msg}")


@router.message(Command("login"))
async def cmd_login(message: Message):
    parts = message.text.split(maxsplit=2)
    if len(parts) < 3:
        return await message.answer("Формат: /login email пароль\nПример: /login user@mail.ru mypass123")
    email = parts[1].strip()
    password = parts[2].strip()
    user = db.login_user(email, password)
    if user:
        LOGGED_IN_USERS.add(message.from_user.id)
        await message.answer(f"✅ Вход выполнен! Добро пожаловать, <code>{user['email']}</code>")
    else:
        await message.answer("❌ Неверный email или пароль")


@router.message(Command("logout"))
async def cmd_logout(message: Message):
    uid = message.from_user.id
    if uid in LOGGED_IN_USERS:
        LOGGED_IN_USERS.discard(uid)
        await message.answer("✅ Вы вышли из аккаунта.")
    else:
        await message.answer("Вы не были в системе.")


@router.message(Command("list"))
async def cmd_list(message: Message):
    if not is_allowed(message):
        return await message.answer("Нет доступа.")
    users = db.get_all_users()
    accounts = db.get_all_accounts()
    lines = []
    if users:
        lines.append(f"<b>Пользователи ({len(users)}):</b>")
        for u in users:
            lines.append(f"  • <code>{u['email']}</code> (tg_id: {u['telegram_id']})")
    if accounts:
        lines.append(f"<b>TikTok аккаунты ({len(accounts)}):</b>")
        for acc in accounts:
            lines.append(f"  • <code>@{acc['username']}</code>")
    if not lines:
        return await message.answer("Нет данных.")
    await message.answer("\n".join(lines))


@router.message(Command("addtiktok"))
async def cmd_addtiktok(message: Message):
    if not is_allowed(message):
        return await message.answer("Нет доступа.")
    parts = message.text.split(maxsplit=2)
    if len(parts) < 3:
        return await message.answer(
            "Формат: /addtiktok email пароль\n"
            "Пример: /addtiktok user@mail.ru mypass123"
        )
    email = parts[1].strip()
    password = parts[2].strip()

    await message.answer("⏳ Открываю TikTok, вхожу в аккаунт...")

    ok, msg, username, cookies, ua = await login_to_tiktok(email, password)
    if not ok:
        return await message.answer(f"❌ {msg}")

    db.add_account(username, cookies, ua)
    await message.answer(f"✅ {msg}\nАккаунт: <code>@{username}</code>")


@router.message(Command("sub"))
async def cmd_sub(message: Message):
    if not is_allowed(message):
        return
    parts = message.text.split(maxsplit=1)
    if len(parts) < 2:
        return await message.answer("Укажите ссылку: /sub https://tiktok.com/@user")

    target_url = parts[1].strip()
    username = extract_username(target_url)
    if not username:
        return await message.answer("Не удалось распознать username из ссылки.")

    accounts = db.get_all_accounts()
    if not accounts:
        return await message.answer("Нет добавленных аккаунтов.")

    await message.answer(
        f"Запускаю подписку на <code>@{username}</code> "
        f"с {len(accounts)} аккаунтов..."
    )

    results = await subscribe_with_all_accounts(accounts, target_url)

    lines = []
    for r in results:
        icon = "✅" if r["ok"] else "❌"
        lines.append(f"{icon} <code>{r['username']}</code> — {r['message']}")
    await message.answer("\n".join(lines))


async def main():
    db.init_db()
    logger.info("Bot started")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
