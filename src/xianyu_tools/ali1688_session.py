from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from typing import Any

from xianyu_tools.xianyu_adapter.browser_transport import default_desktop_context_options, default_launch_args


@dataclass(slots=True)
class Ali1688SessionConfig:
    user_data_dir: str
    browser_channel: str = "chrome"
    profile_directory: str | None = None
    launch_args: list[str] = field(default_factory=list)
    slow_mo_ms: int = 0


def looks_like_login_url(url: str) -> bool:
    lowered = url.lower()
    return any(token in lowered for token in ["login.taobao.com", "login.1688.com", "member/modify_evolve"])


async def slider_still_present(page) -> bool:
    for frame in list(page.frames):
        try:
            locator = frame.locator(".errloading, .nc_scale, .btn_slide, .nc_1_n1z, #nc_1_wrapper").first
            if await locator.count() and await locator.is_visible():
                return True
        except Exception:
            continue
    return False


async def search_input_locator(page):
    selectors = [
        "input.ali-search-input",
        "input#alisearch-input",
        "input[name='keywords']",
        "input[type='search']",
        "input[placeholder*='搜索']",
    ]
    for selector in selectors:
        locator = page.locator(selector).first
        try:
            if await locator.count():
                return locator
        except Exception:
            continue
    return None


async def wait_for_search_or_slider(page, timeout_seconds: float = 8.0) -> str:
    deadline = asyncio.get_running_loop().time() + timeout_seconds
    while asyncio.get_running_loop().time() < deadline:
        if looks_like_login_url(page.url):
            return "login"
        if await slider_still_present(page):
            return "slider"
        if await search_input_locator(page) is not None:
            return "search"
        await asyncio.sleep(0.2)
    return "unknown"


async def inspect_ali1688_session(config: Ali1688SessionConfig) -> dict[str, Any]:
    from playwright.async_api import async_playwright
    from playwright._impl._errors import Error as PlaywrightError

    launch_args = [*default_launch_args(), *config.launch_args]
    async with async_playwright() as playwright:
        persistent_args = list(launch_args)
        if config.profile_directory:
            persistent_args.append(f"--profile-directory={config.profile_directory}")
        try:
            context = await playwright.chromium.launch_persistent_context(
                config.user_data_dir,
                channel=config.browser_channel,
                headless=False,
                slow_mo=config.slow_mo_ms,
                args=persistent_args,
                **default_desktop_context_options(),
            )
        except PlaywrightError as exc:
            message = str(exc)
            if "ProcessSingleton" in message or "profile is already in use" in message:
                return {
                    "state": "profile_locked",
                    "url": "",
                    "title": "",
                    "user_data_dir": config.user_data_dir,
                    "profile_directory": config.profile_directory,
                    "error": message,
                }
            raise
        try:
            page = context.pages[0] if context.pages else await context.new_page()
            await page.goto("https://www.1688.com/", wait_until="domcontentloaded", timeout=30000)
            state = await wait_for_search_or_slider(page)
            title = await page.title()
            return {
                "state": state,
                "url": page.url,
                "title": title,
                "user_data_dir": config.user_data_dir,
                "profile_directory": config.profile_directory,
            }
        finally:
            await context.close()
