from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from xianyu_tools.xianyu_adapter.browser_transport import (
    PlaywrightBrowserConfig,
    PlaywrightBrowserTransport,
    XianyuBrowserTransportError,
    default_desktop_context_options,
    default_launch_args,
    default_mobile_context_options,
)

MAX_STORAGE_ENTRY_LENGTH = 4096
ALLOWED_HEADERS = {
    "user-agent",
    "accept",
    "accept-language",
    "accept-encoding",
    "referer",
    "sec-ch-ua",
    "sec-ch-ua-mobile",
    "sec-ch-ua-platform",
    "sec-fetch-site",
    "sec-fetch-mode",
    "sec-fetch-dest",
    "sec-fetch-user",
    "origin",
    "cache-control",
    "pragma",
    "upgrade-insecure-requests",
    "content-type",
}


@dataclass(slots=True)
class StateExportConfig:
    output_file: str
    state_file: str | None = None
    browser_channel: str = "chrome"
    headless: bool = False
    launch_args: list[str] = field(default_factory=list)
    cdp_url: str | None = None
    user_data_dir: str | None = None
    profile_directory: str | None = None
    page_url: str = "https://www.goofish.com/"
    timeout_ms: int = 20000
    wait_after_login_seconds: float = 0.0
    prompt_for_login: bool = False


class PlaywrightStateExporter:
    def __init__(
        self,
        *,
        config: StateExportConfig,
        async_playwright_factory: Any | None = None,
    ) -> None:
        self.config = config
        self.async_playwright_factory = async_playwright_factory

    def export(self) -> dict[str, Any]:
        snapshot = self._run_sync(self._export())
        output_path = Path(self.config.output_file)
        output_path.write_text(json.dumps(snapshot, ensure_ascii=False, indent=2), encoding="utf-8")
        return snapshot

    async def _export(self) -> dict[str, Any]:
        if self.config.cdp_url:
            return await self._export_from_cdp_browser()
        if self.config.user_data_dir:
            return await self._export_from_persistent_profile()
        return await self._export_from_ephemeral_context()

    async def _export_from_ephemeral_context(self) -> dict[str, Any]:
        transport = PlaywrightBrowserTransport(
            config=PlaywrightBrowserConfig(
                state_file=self.config.state_file,
                headless=self.config.headless,
                browser_channel=self.config.browser_channel,
                launch_args=list(self.config.launch_args or []),
                context_options=default_mobile_context_options(),
            ),
            async_playwright_factory=self.async_playwright_factory,
        )
        async with transport._playwright_context() as playwright:
            browser = await playwright.chromium.launch(
                channel=self.config.browser_channel,
                headless=self.config.headless,
                args=self._launch_args(),
            )
            try:
                context = await transport._new_context(browser)
                page = await context.new_page()
                try:
                    return await self._capture_snapshot(context, page)
                finally:
                    await page.close()
                    await context.close()
            finally:
                await browser.close()

    async def _export_from_persistent_profile(self) -> dict[str, Any]:
        transport = PlaywrightBrowserTransport(
            config=PlaywrightBrowserConfig(
                headless=self.config.headless,
                browser_channel=self.config.browser_channel,
                launch_args=list(self.config.launch_args or []),
            ),
            async_playwright_factory=self.async_playwright_factory,
        )
        launch_kwargs: dict[str, Any] = {
            "channel": self.config.browser_channel,
            "headless": self.config.headless,
            "args": self._launch_args(),
        }
        if self.config.profile_directory:
            launch_kwargs["args"] = [
                *launch_kwargs["args"],
                f"--profile-directory={self.config.profile_directory}",
            ]

        async with transport._playwright_context() as playwright:
            context = await playwright.chromium.launch_persistent_context(
                self.config.user_data_dir,
                **launch_kwargs,
            )
            try:
                page = context.pages[0] if context.pages else await context.new_page()
                return await self._capture_snapshot(context, page)
            finally:
                await context.close()

    async def _export_from_cdp_browser(self) -> dict[str, Any]:
        transport = PlaywrightBrowserTransport(
            config=PlaywrightBrowserConfig(
                headless=self.config.headless,
                browser_channel=self.config.browser_channel,
                launch_args=list(self.config.launch_args or []),
                context_options=default_desktop_context_options(),
            ),
            async_playwright_factory=self.async_playwright_factory,
        )
        async with transport._playwright_context() as playwright:
            browser = await playwright.chromium.connect_over_cdp(self.config.cdp_url)
            try:
                context = browser.contexts[0] if browser.contexts else await browser.new_context()
                page = context.pages[0] if context.pages else await context.new_page()
                return await self._capture_snapshot(context, page)
            finally:
                await browser.close()

    async def _capture_snapshot(self, context: Any, page: Any) -> dict[str, Any]:
        captured_headers = await self._capture_headers(page)
        await page.goto(
            self.config.page_url,
            wait_until="domcontentloaded",
            timeout=self.config.timeout_ms,
        )
        if self.config.prompt_for_login:
            input("登录完成后按回车继续导出 xianyu_state.json ... ")
        if self.config.wait_after_login_seconds > 0:
            await asyncio.sleep(self.config.wait_after_login_seconds)
        page_data = await self._capture_page_data(page)
        headers = captured_headers or await self._capture_headers(page)
        cookies = await context.cookies(self.config.page_url)
        return build_snapshot(page.url, page_data, headers, cookies)

    async def _capture_page_data(self, page: Any) -> dict[str, Any]:
        return await page.evaluate(
            """
            () => {
              const safeEntries = (storage) => {
                try {
                  const obj = {};
                  for (let i = 0; i < storage.length; i += 1) {
                    const key = storage.key(i);
                    if (key !== null) obj[key] = storage.getItem(key);
                  }
                  return obj;
                } catch (e) {
                  return {};
                }
              };
              const intl = (() => {
                try { return Intl.DateTimeFormat().resolvedOptions(); } catch (e) { return {}; }
              })();
              const uaData = (() => {
                try { return navigator.userAgentData ? navigator.userAgentData.toJSON() : null; } catch (e) { return null; }
              })();
              return {
                page: {
                  pageUrl: location.href,
                  referrer: document.referrer || null,
                  visibilityState: document.visibilityState,
                },
                env: {
                  navigator: {
                    userAgent: navigator.userAgent,
                    platform: navigator.platform,
                    vendor: navigator.vendor,
                    language: navigator.language,
                    languages: navigator.languages,
                    hardwareConcurrency: navigator.hardwareConcurrency,
                    deviceMemory: navigator.deviceMemory,
                    webdriver: navigator.webdriver,
                    doNotTrack: navigator.doNotTrack,
                    maxTouchPoints: navigator.maxTouchPoints,
                    userAgentData: uaData,
                  },
                  screen: {
                    width: screen.width,
                    height: screen.height,
                    availWidth: screen.availWidth,
                    availHeight: screen.availHeight,
                    colorDepth: screen.colorDepth,
                    pixelDepth: screen.pixelDepth,
                    devicePixelRatio: window.devicePixelRatio,
                  },
                  intl,
                },
                storage: {
                  local: safeEntries(localStorage),
                  session: safeEntries(sessionStorage),
                },
              };
            }
            """
        )

    async def _capture_headers(self, page: Any) -> dict[str, str]:
        loop = asyncio.get_running_loop()
        future: asyncio.Future[dict[str, str]] = loop.create_future()

        async def handle_request(request: Any) -> None:
            if future.done():
                return
            if "goofish.com" not in request.url:
                return
            future.set_result(dict(request.headers))

        page.on("request", handle_request)
        try:
            await page.evaluate(
                """
                () => {
                  try {
                    fetch(`${window.location.origin}/__codex_probe?ts=${Date.now()}`, {
                      credentials: "include",
                      cache: "no-store",
                      redirect: "follow",
                    }).catch(() => {});
                  } catch (e) {}
                }
                """
            )
            try:
                return await asyncio.wait_for(future, timeout=2.0)
            except asyncio.TimeoutError:
                return {}
        finally:
            page.remove_listener("request", handle_request)

    def _run_sync(self, coro: Any) -> Any:
        return PlaywrightBrowserTransport(config=PlaywrightBrowserConfig())._run_sync(coro)

    def _launch_args(self) -> list[str]:
        args = default_launch_args()
        for arg in self.config.launch_args or []:
            if arg not in args:
                args.append(arg)
        return args


def build_snapshot(
    page_url: str,
    page_data: dict[str, Any],
    headers: dict[str, Any],
    cookies: list[dict[str, Any]],
) -> dict[str, Any]:
    filtered_env = filter_env_data(page_data.get("env") or {})
    local_pruned = prune_storage_entries((page_data.get("storage") or {}).get("local") or {})
    session_pruned = prune_storage_entries((page_data.get("storage") or {}).get("session") or {})
    return {
        "capturedAt": _iso_now(),
        "pageUrl": page_url,
        "page": page_data.get("page") or {},
        "env": filtered_env,
        "storage": {
            "local": local_pruned["data"],
            "session": session_pruned["data"],
        },
        "meta": {
            "droppedStorageKeys": {
                "local": local_pruned["dropped"],
                "session": session_pruned["dropped"],
            }
        },
        "headers": filter_headers(headers),
        "cookies": normalize_cookies(cookies),
    }


def filter_env_data(env: dict[str, Any]) -> dict[str, Any]:
    nav = env.get("navigator") or {}
    screen = env.get("screen") or {}
    intl = env.get("intl") or {}
    return {
        "navigator": {
            "userAgent": nav.get("userAgent"),
            "platform": nav.get("platform"),
            "language": nav.get("language"),
            "languages": nav.get("languages"),
            "hardwareConcurrency": nav.get("hardwareConcurrency"),
            "deviceMemory": nav.get("deviceMemory"),
            "maxTouchPoints": nav.get("maxTouchPoints"),
            "webdriver": nav.get("webdriver"),
            "doNotTrack": nav.get("doNotTrack"),
            "userAgentData": nav.get("userAgentData"),
        },
        "screen": {
            "width": screen.get("width"),
            "height": screen.get("height"),
            "devicePixelRatio": screen.get("devicePixelRatio"),
            "colorDepth": screen.get("colorDepth"),
        },
        "intl": {
            "timeZone": intl.get("timeZone"),
            "locale": intl.get("locale"),
        },
    }


def prune_storage_entries(entries: dict[str, Any]) -> dict[str, Any]:
    data: dict[str, Any] = {}
    dropped: list[str] = []
    for key, value in entries.items():
        text = "" if value is None else str(value)
        if len(text) <= MAX_STORAGE_ENTRY_LENGTH:
            data[key] = value
        else:
            dropped.append(key)
    return {"data": data, "dropped": dropped}


def filter_headers(raw_headers: dict[str, Any]) -> dict[str, str]:
    normalized: dict[str, str] = {}
    for key, value in raw_headers.items():
        if str(key).lower() in ALLOWED_HEADERS and value is not None:
            normalized[str(key)] = str(value)
    return normalized


def normalize_cookies(cookies: list[dict[str, Any]]) -> list[dict[str, Any]]:
    normalized = []
    for cookie in cookies:
        normalized.append(
            {
                "name": cookie.get("name"),
                "value": cookie.get("value"),
                "domain": cookie.get("domain"),
                "path": cookie.get("path"),
                "expires": cookie.get("expires"),
                "httpOnly": cookie.get("httpOnly"),
                "secure": cookie.get("secure"),
                "sameSite": _map_same_site(cookie.get("sameSite")),
            }
        )
    return normalized


def _map_same_site(value: Any) -> str:
    mapping = {
        None: "Lax",
        "None": "None",
        "Lax": "Lax",
        "Strict": "Strict",
        "no_restriction": "None",
        "lax": "Lax",
        "strict": "Strict",
        "unspecified": "Lax",
    }
    return mapping.get(value, "Lax")


def _iso_now() -> str:
    from datetime import datetime

    return datetime.utcnow().isoformat() + "Z"
