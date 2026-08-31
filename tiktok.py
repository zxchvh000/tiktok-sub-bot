import asyncio
import re
from typing import Optional
from urllib.parse import urlparse

from playwright.async_api import async_playwright, Page, BrowserContext


def extract_username(url: str) -> Optional[str]:
    url = url.strip()
    m = re.search(r"tiktok\.com/@([\w.\-]+)", url)
    if m:
        return m.group(1)
    m = re.search(r"^@([\w.\-]+)$", url)
    if m:
        return m.group(1)
    return None


async def subscribe_to_profile(
    cookies: list[dict],
    user_agent: str,
    target_url: str,
) -> tuple[bool, str]:
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context: BrowserContext = await browser.new_context(user_agent=user_agent)
        await context.add_cookies(cookies)

        page: Page = await context.new_page()

        try:
            await page.goto(target_url, wait_until="domcontentloaded", timeout=30000)
            await page.wait_for_timeout(3000)

            follow_btn = page.locator(
                'button:has-text("Follow"), button:has-text("Подписаться")'
            )
            if await follow_btn.count() == 0:
                await browser.close()
                return False, "Кнопка подписки не найдена (возможно, уже подписаны)"

            await follow_btn.first.click()
            await page.wait_for_timeout(2000)
            await browser.close()
            return True, "Подписка выполнена"
        except Exception as e:
            await browser.close()
            return False, f"Ошибка: {e}"


async def subscribe_with_all_accounts(
    accounts: list[dict],
    target_url: str,
) -> list[dict]:
    results = []
    for acc in accounts:
        ok, msg = await subscribe_to_profile(
            cookies=acc["cookies"],
            user_agent=acc["user_agent"],
            target_url=target_url,
        )
        results.append({"username": acc["username"], "ok": ok, "message": msg})
        await asyncio.sleep(2)
    return results
