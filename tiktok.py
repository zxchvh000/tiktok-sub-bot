import asyncio
import json
import re
from typing import Optional, Union
from urllib.parse import urlparse

from playwright.async_api import async_playwright, Page, BrowserContext


TIKTOK_LOGIN_URL = "https://www.tiktok.com/login/phone-or-email/email"
DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/131.0.0.0 Safari/537.36"
)


def extract_username(url: str) -> Optional[str]:
    url = url.strip()
    m = re.search(r"tiktok\.com/@([\w.\-]+)", url)
    if m:
        return m.group(1)
    m = re.search(r"^@([\w.\-]+)$", url)
    if m:
        return m.group(1)
    return None


async def login_to_tiktok(
    email: str,
    password: str,
) -> tuple[bool, str, Optional[str], Optional[list], Optional[str]]:
    """
    Returns: (success, message, username, cookies, user_agent)
    """
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context: BrowserContext = await browser.new_context(
            user_agent=DEFAULT_USER_AGENT
        )
        page: Page = await context.new_page()

        try:
            await page.goto(TIKTOK_LOGIN_URL, wait_until="domcontentloaded", timeout=30000)
            await page.wait_for_timeout(3000)

            email_input = page.locator('input[name="username"], input[type="text"], input[placeholder*="mail"], input[placeholder*="Mail"]')
            if await email_input.count() == 0:
                await browser.close()
                return False, "Поле email не найдено", None, None, None

            await email_input.first.fill(email)
            await page.wait_for_timeout(500)

            password_input = page.locator('input[type="password"], input[name="password"]')
            if await password_input.count() == 0:
                await browser.close()
                return False, "Поле пароля не найдено", None, None, None

            await password_input.first.fill(password)
            await page.wait_for_timeout(500)

            login_btn = page.locator('button[type="submit"], button:has-text("Log in"), button:has-text("Войти")')
            if await login_btn.count() > 0:
                await login_btn.first.click()
            else:
                await password_input.first.press("Enter")

            await page.wait_for_timeout(5000)

            current_url = page.url
            if "login" in current_url.lower():
                error_el = page.locator('[class*="error"], [class*="Error"], [data-e2e="login-error"]')
                error_text = ""
                if await error_el.count() > 0:
                    error_text = await error_el.first.text_content() or ""
                await browser.close()
                return False, f"Логин не удался: {error_text or 'проверьте данные'}", None, None, None

            cookies = await context.cookies()
            cookies_json = json.dumps(cookies)

            username = None
            try:
                me_resp = await page.goto("https://www.tiktok.com/api/user/info/", wait_until="commit", timeout=10000)
                if me_resp and me_resp.ok:
                    data = await me_resp.json()
                    username = data.get("userInfo", {}).get("user", {}).get("uniqueId")
            except Exception:
                pass

            if not username:
                cookie_username = None
                for c in cookies:
                    if c.get("name") == "passport_csrf_token":
                        continue
                    if "user" in c.get("name", "").lower() and c.get("value"):
                        cookie_username = c["value"]
                        break
                username = cookie_username or email.split("@")[0]

            ua = context._options.get("user_agent", DEFAULT_USER_AGENT)
            await browser.close()
            return True, "Аккаунт добавлен", username, cookies_json, ua

        except Exception as e:
            await browser.close()
            return False, f"Ошибка: {e}", None, None, None


async def subscribe_to_profile(
    cookies: Union[list, str],
    user_agent: str,
    target_url: str,
) -> tuple[bool, str]:
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context: BrowserContext = await browser.new_context(user_agent=user_agent)

        if isinstance(cookies, str):
            cookies = json.loads(cookies)
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
