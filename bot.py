import asyncio
import logging

from aiogram import Bot, Dispatcher, Router
from aiogram.types import Message
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


@router.message(CommandStart())
async def cmd_start(message: Message):
    await message.answer(
        "<b>TikTok Subscribe Bot</b>\n\n"
        "Команды:\n"
        "/addtiktok email пароль — добавить TikTok аккаунт\n"
        "/sub &lt;ссылка&gt; — подписка всеми аккаунтами\n"
        "/list — список аккаунтов\n"
        "/help — справка"
    )


@router.message(Command("help"))
async def cmd_help(message: Message):
    await message.answer(
        "<b>TikTok Subscribe Bot</b>\n\n"
        "/addtiktok email пароль — добавить TikTok аккаунт\n"
        "/sub &lt;ссылка&gt; — подписка всеми аккаунтами\n"
        "/list — список аккаунтов"
    )


@router.message(Command("addtiktok"))
async def cmd_addtiktok(message: Message):
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


@router.message(Command("list"))
async def cmd_list(message: Message):
    accounts = db.get_all_accounts()
    if not accounts:
        return await message.answer("Нет добавленных аккаунтов.")
    lines = [f"<b>TikTok аккаунты ({len(accounts)}):</b>"]
    for acc in accounts:
        lines.append(f"  • <code>@{acc['username']}</code>")
    await message.answer("\n".join(lines))


@router.message(Command("sub"))
async def cmd_sub(message: Message):
    parts = message.text.split(maxsplit=1)
    if len(parts) < 2:
        return await message.answer("Укажите ссылку: /sub https://tiktok.com/@user")

    target_url = parts[1].strip()
    username = extract_username(target_url)
    if not username:
        return await message.answer("Не удалось распознать username из ссылки.")

    accounts = db.get_all_accounts()
    if not accounts:
        return await message.answer("Нет добавленных аккаунтов. Используйте /addtiktok")

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
