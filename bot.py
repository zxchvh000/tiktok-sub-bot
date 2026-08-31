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
from tiktok import extract_username, subscribe_with_all_accounts

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

bot = Bot(token=config.BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher()
router = Router()
dp.include_router(router)

WAITING_COOKIES: dict[int, dict] = {}
LOGGED_IN_USERS: set[int] = set()
WAITING_AUTH: dict[int, dict] = {}


def is_allowed(message: Message) -> bool:
    uid = message.from_user.id
    if uid in LOGGED_IN_USERS:
        return True
    if not config.ALLOWED_USERS:
        return True
    return uid in config.ALLOWED_USERS


@router.message(CommandStart())
async def cmd_start(message: Message):
    if not is_allowed(message):
        return await message.answer("Нет доступа. Используйте /register или /login для входа.")
    await message.answer(
        "<b>TikTok Subscribe Bot</b>\n\n"
        "Команды:\n"
        "/add — добавить аккаунт\n"
        "/list — список аккаунтов\n"
        "/remove — удалить аккаунт\n"
        "/sub &lt;ссылка&gt; — подписка всеми аккаунтами\n"
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
        "<b>Как добавить аккаунт:</b>\n"
        "1. Откройте TikTok в браузере, войдите в аккаунт\n"
        "2. Откройте DevTools (F12) → Application → Cookies → www.tiktok.com\n"
        "3. Скопируйте ВСЕ куки в формате JSON (Name, Value, Domain, Path, и т.д.)\n"
        "4. Отправьте боту: /add\n"
        "5. Бот попросит ввести имя аккаунта и куки\n\n"
        "<b>Формат кук:</b>\n"
        "Просто скопируйте JSON-массив из браузерного расширения "
        "(например, EditThisCookie) или из DevTools.\n\n"
        "<b>Пример:</b>\n"
        '[{"name":"sessionid","value":"abc123","domain":".tiktok.com","path":"/"},...]'
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


@router.message(Command("add"))
async def cmd_add(message: Message):
    if not is_allowed(message):
        return
    await message.answer("Введите <b>имя</b> TikTok-аккаунта (username без @):")
    WAITING_COOKIES[message.from_user.id] = {"step": "username"}


@router.message(Command("remove"))
async def cmd_remove(message: Message):
    if not is_allowed(message):
        return
    accounts = db.get_all_accounts()
    if not accounts:
        return await message.answer("Нет сохранённых аккаунтов.")
    text = "\n".join(f"• <code>{a['username']}</code>" for a in accounts)
    WAITING_COOKIES[message.from_user.id] = {"step": "remove"}
    await message.answer(f"Введите username для удаления:\n{text}")


@router.message(Command("list"))
async def cmd_list(message: Message):
    if not is_allowed(message):
        return
    accounts = db.get_all_accounts()
    if not accounts:
        return await message.answer("Нет сохранённых аккаунтов.")
    text = "\n".join(f"• <code>{a['username']}</code>" for a in accounts)
    await message.answer(f"<b>Аккаунты ({len(accounts)}):</b>\n{text}")


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
        return await message.answer("Нет добавленных аккаунтов. Сначала /add")

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


@router.message()
async def on_message(message: Message):
    if not is_allowed(message):
        return
    uid = message.from_user.id
    state = WAITING_COOKIES.get(uid)

    if not state:
        return

    if state["step"] == "username":
        username = message.text.strip().lstrip("@")
        if not username:
            return await message.answer("Имя не может быть пустым.")
        state["username"] = username
        state["step"] = "cookies"
        return await message.answer(
            "Теперь отправьте <b>куки</b> в формате JSON-массива.\n"
            "Пример:\n<code>[{\"name\":\"sessionid\",\"value\":\"...\",...}]</code>"
        )

    if state["step"] == "cookies":
        raw = message.text.strip()
        try:
            cookies = json.loads(raw)
            if not isinstance(cookies, list):
                raise ValueError
        except Exception:
            return await message.answer("Неверный формат. Отправьте JSON-массив кук.")

        ua = (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/131.0.0.0 Safari/537.36"
        )

        ok = db.add_account(state["username"], cookies, ua)
        del WAITING_COOKIES[uid]

        if ok:
            await message.answer(f"✅ Аккаунт <code>{state['username']}</code> добавлен.")
        else:
            await message.answer("Аккаунт с таким именем уже есть.")

    if state["step"] == "remove":
        username = message.text.strip().lstrip("@")
        ok = db.remove_account(username)
        del WAITING_COOKIES[uid]
        if ok:
            await message.answer(f"✅ Аккаунт <code>{username}</code> удалён.")
        else:
            await message.answer("Аккаунт не найден.")


async def main():
    db.init_db()
    logger.info("Bot started")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
