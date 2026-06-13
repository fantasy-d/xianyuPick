from __future__ import annotations

import asyncio
import json
import threading
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from urllib.parse import quote

SEARCH_API_PATTERN = "h5api.m.goofish.com/h5/mtop.taobao.idlemtopsearch.pc.search/"
DETAIL_API_PATTERN = "h5api.m.goofish.com/h5/mtop.taobao.idle.pc.detail"
USER_HEAD_API_PATTERN = "mtop.idle.web.user.page.head"
USER_RATINGS_API_PATTERN = "mtop.idle.web.trade.rate.list"
HOME_URL = "https://www.goofish.com/"
SEARCH_INPUT_SELECTOR = "input[placeholder]"
SEARCH_SUBMIT_SELECTOR = "button[type='submit']"
FISH_SHOP_FILTER_SELECTOR = "text=超赞鱼小铺"
NEXT_PAGE_SELECTOR = (
    "button[class*='search-pagination-arrow-container']"
    ":has([class*='search-pagination-arrow-right'])"
    ":not([disabled])"
)
RATINGS_TAB_SELECTOR = "//div[text()='信用及评价']/ancestor::li"


class XianyuBrowserTransportError(RuntimeError):
    pass


class XianyuStateInvalidError(XianyuBrowserTransportError):
    pass


class XianyuSearchTimeoutError(XianyuBrowserTransportError):
    pass


@dataclass(slots=True)
class PlaywrightBrowserConfig:
    state_file: str | None = None
    headless: bool = True
    browser_channel: str = "chrome"
    launch_args: list[str] = field(default_factory=list)
    search_timeout_ms: int = 20000
    detail_timeout_ms: int = 25000
    seller_timeout_ms: int = 20000
    search_max_retries: int = 2
    retry_delay_seconds: float = 1.0
    search_url_template: str = "https://www.goofish.com/search?keyword={keyword}"
    detail_url_template: str = "https://www.goofish.com/item?id={item_id}"
    seller_url_template: str = "https://www.goofish.com/personal?userId={user_id}"
    context_options: dict[str, Any] = field(default_factory=dict)


def default_desktop_context_options() -> dict[str, Any]:
    return {
        "user_agent": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/146.0.0.0 Safari/537.36"
        ),
        "no_viewport": True,
        "is_mobile": False,
        "has_touch": False,
        "locale": "zh-CN",
        "timezone_id": "Asia/Shanghai",
        "color_scheme": "light",
    }


def default_mobile_context_options() -> dict[str, Any]:
    return {
        "no_viewport": False,
        "user_agent": (
            "Mozilla/5.0 (Linux; Android 6.0; Nexus 5 Build/MRA58N) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Mobile Safari/537.36"
        ),
        "viewport": {"width": 412, "height": 915},
        "device_scale_factor": 2.625,
        "is_mobile": True,
        "has_touch": True,
        "locale": "zh-CN",
        "timezone_id": "Asia/Shanghai",
        "permissions": ["geolocation"],
        "geolocation": {"longitude": 121.4737, "latitude": 31.2304},
        "color_scheme": "light",
    }


def default_launch_args() -> list[str]:
    return [
        "--disable-blink-features=AutomationControlled",
        "--disable-dev-shm-usage",
        "--no-first-run",
        "--no-default-browser-check",
        "--disable-infobars",
    ]


def _sanitize_launch_args(args: list[str], *, headless: bool) -> list[str]:
    if not headless:
        return args
    disallowed_prefixes = (
        "--start-maximized",
        "--window-position=",
        "--app=",
    )
    return [
        arg
        for arg in args
        if not any(arg == prefix or arg.startswith(prefix) for prefix in disallowed_prefixes)
    ]


class PlaywrightBrowserTransport:
    def __init__(
        self,
        *,
        config: PlaywrightBrowserConfig | None = None,
        async_playwright_factory: Any | None = None,
    ) -> None:
        self.config = config or PlaywrightBrowserConfig()
        self.async_playwright_factory = async_playwright_factory

    def search_payload(self, keyword: str, page: int) -> dict[str, Any]:
        return self._run_sync(self._search_payload(keyword, page))

    def search_all_payloads(
        self,
        keyword: str,
        *,
        max_pages: int = 5,
        require_chaozan_fish_shop: bool = False,
    ) -> list[dict[str, Any]]:
        return self._run_sync(
            self._search_all_payloads(
                keyword,
                max_pages=max_pages,
                require_chaozan_fish_shop=require_chaozan_fish_shop,
            )
        )

    def detail_payload(self, item_url_or_id: str) -> dict[str, Any]:
        return self._run_sync(self._detail_payload(item_url_or_id))

    def seller_payload(self, user_id: str) -> tuple[dict[str, Any], list[dict[str, Any]] | None]:
        return self._run_sync(self._seller_payload(user_id))

    async def _search_payload(self, keyword: str, page: int) -> dict[str, Any]:
        last_error: BaseException | None = None
        attempts = max(self.config.search_max_retries + 1, 1)
        for attempt in range(1, attempts + 1):
            try:
                return await self._search_payload_once(keyword, page)
            except asyncio.TimeoutError as exc:
                last_error = XianyuSearchTimeoutError(
                    f"xianyu search timed out after {self.config.search_timeout_ms}ms"
                )
                if attempt >= attempts:
                    raise last_error from exc
            except Exception as exc:
                last_error = exc
                if attempt >= attempts:
                    raise
                if self.config.retry_delay_seconds > 0:
                    await asyncio.sleep(self.config.retry_delay_seconds)
        if last_error is not None:
            raise last_error
        raise XianyuBrowserTransportError("search failed without raising a concrete error")

    async def _search_payload_once(self, keyword: str, page: int) -> dict[str, Any]:
        payloads = await self._search_all_payloads(
            keyword,
            max_pages=max(page, 1),
            require_chaozan_fish_shop=False,
        )
        if not payloads:
            return {"data": {"resultList": []}}
        return payloads[min(max(page, 1), len(payloads)) - 1]

    async def _search_all_payloads(
        self,
        keyword: str,
        *,
        max_pages: int = 5,
        require_chaozan_fish_shop: bool = False,
    ) -> list[dict[str, Any]]:
        async with self._playwright_context() as playwright:
            browser = await playwright.chromium.launch(
                channel=self.config.browser_channel,
                headless=self.config.headless,
                args=self._launch_args(),
            )
            try:
                context = await self._new_context(browser)
                page_obj = await context.new_page()
                try:
                    payloads: list[dict[str, Any]] = []
                    await page_obj.goto(
                        HOME_URL,
                        wait_until="domcontentloaded",
                        timeout=self.config.search_timeout_ms,
                    )
                    input_locator = page_obj.locator(SEARCH_INPUT_SELECTOR).first
                    submit_locator = page_obj.locator(SEARCH_SUBMIT_SELECTOR).first
                    await input_locator.wait_for(state="visible", timeout=self.config.search_timeout_ms)
                    await input_locator.click()
                    await input_locator.clear()
                    await input_locator.fill(keyword)
                    input_value = await input_locator.input_value()
                    if input_value.strip() != keyword.strip():
                        raise XianyuBrowserTransportError(
                            f"search input mismatch: expected {keyword!r}, got {input_value!r}"
                        )
                    async with page_obj.expect_response(
                        lambda response: self._is_search_response(response),
                        timeout=self.config.search_timeout_ms,
                    ) as response_info:
                        await submit_locator.click(timeout=min(self.config.search_timeout_ms, 10000))
                    response = await response_info.value
                    payloads.append(await response.json())
                    if require_chaozan_fish_shop:
                        filtered_payload = await self._apply_chaozan_fish_shop_filter(page_obj)
                        payloads = [filtered_payload]
                    for _ in range(1, max(max_pages, 1)):
                        response = await self._advance_search_page(page_obj)
                        payloads.append(await response.json())
                    return payloads
                finally:
                    await page_obj.close()
                    await context.close()
            finally:
                await browser.close()

    async def _apply_chaozan_fish_shop_filter(self, page_obj: Any) -> dict[str, Any]:
        filter_locator = page_obj.locator(FISH_SHOP_FILTER_SELECTOR).first
        if not await filter_locator.count():
            raise XianyuBrowserTransportError("超赞鱼小铺 filter not found")
        await filter_locator.scroll_into_view_if_needed()
        async with page_obj.expect_response(
            lambda response: self._is_search_response(response),
            timeout=self.config.search_timeout_ms,
        ) as response_info:
            await filter_locator.click(timeout=min(self.config.search_timeout_ms, 10000))
        return await (await response_info.value).json()

    async def _detail_payload(self, item_url_or_id: str) -> dict[str, Any]:
        detail_url = item_url_or_id if item_url_or_id.startswith("http") else self.config.detail_url_template.format(
            item_id=item_url_or_id
        )
        async with self._playwright_context() as playwright:
            browser = await playwright.chromium.launch(
                channel=self.config.browser_channel,
                headless=self.config.headless,
                args=self._launch_args(),
            )
            try:
                context = await self._new_context(browser)
                page_obj = await context.new_page()
                try:
                    async with page_obj.expect_response(
                        lambda response: DETAIL_API_PATTERN in response.url and response.request.method == "POST",
                        timeout=self.config.detail_timeout_ms,
                    ) as response_info:
                        await page_obj.goto(
                            detail_url,
                            wait_until="domcontentloaded",
                            timeout=self.config.detail_timeout_ms,
                        )
                    return await (await response_info.value).json()
                finally:
                    await page_obj.close()
                    await context.close()
            finally:
                await browser.close()

    async def _seller_payload(self, user_id: str) -> tuple[dict[str, Any], list[dict[str, Any]] | None]:
        async with self._playwright_context() as playwright:
            browser = await playwright.chromium.launch(
                channel=self.config.browser_channel,
                headless=self.config.headless,
                args=self._launch_args(),
            )
            try:
                context = await self._new_context(browser)
                page_obj = await context.new_page()
                try:
                    loop = asyncio.get_running_loop()
                    head_future = loop.create_future()
                    ratings_future = loop.create_future()

                    async def handle_response(response: Any) -> None:
                        try:
                            if USER_HEAD_API_PATTERN in response.url and not head_future.done():
                                head_future.set_result(await response.json())
                            elif USER_RATINGS_API_PATTERN in response.url and not ratings_future.done():
                                data = await response.json()
                                ratings_future.set_result(data.get("data", {}).get("cardList", []))
                        except Exception as exc:
                            if USER_HEAD_API_PATTERN in response.url and not head_future.done():
                                head_future.set_exception(exc)
                            if USER_RATINGS_API_PATTERN in response.url and not ratings_future.done():
                                ratings_future.set_exception(exc)

                    page_obj.on("response", handle_response)
                    await page_obj.goto(
                        self.config.seller_url_template.format(user_id=user_id),
                        wait_until="domcontentloaded",
                        timeout=self.config.seller_timeout_ms,
                    )
                    head_payload = await asyncio.wait_for(head_future, timeout=self.config.seller_timeout_ms / 1000)

                    ratings_payload: list[dict[str, Any]] | None = None
                    rating_tab = page_obj.locator(RATINGS_TAB_SELECTOR)
                    if await rating_tab.count():
                        await rating_tab.click()
                        try:
                            ratings_payload = await asyncio.wait_for(
                                ratings_future,
                                timeout=min(self.config.seller_timeout_ms / 1000, 8),
                            )
                        except asyncio.TimeoutError:
                            ratings_payload = None
                    return head_payload, ratings_payload
                finally:
                    await page_obj.close()
                    await context.close()
            finally:
                await browser.close()

    async def _advance_search_page(self, page_obj: Any) -> Any:
        next_button = page_obj.locator(NEXT_PAGE_SELECTOR).first
        if not await next_button.count():
            raise XianyuBrowserTransportError("next page button not found")
        await next_button.scroll_into_view_if_needed()
        async with page_obj.expect_response(
            lambda response: self._is_search_response(response),
            timeout=self.config.search_timeout_ms,
        ) as response_info:
            await next_button.click(timeout=min(self.config.search_timeout_ms, 10000))
        return await response_info.value

    async def _new_context(self, browser: Any) -> Any:
        base_context = default_desktop_context_options()
        context_options = {**base_context, **self.config.context_options}
        state_file = self.config.state_file
        extra_headers: dict[str, str] = {}
        if state_file:
            state_path = Path(state_file)
            if not state_path.exists():
                raise XianyuBrowserTransportError(f"state file not found: {state_file}")
            state_payload = self._load_json(state_path)
            if not self._state_payload_has_usable_cookies(state_payload):
                raise XianyuStateInvalidError(f"state file has no usable cookies: {state_file}")
            if self._is_playwright_storage_state(state_payload):
                context_options["storage_state"] = state_payload
            else:
                context_options.update(self._build_context_overrides(state_payload))
                storage_state = self._extract_storage_state(state_payload)
                if storage_state:
                    context_options["storage_state"] = storage_state
                extra_headers = self._build_extra_headers(state_payload.get("headers"))
        context_options = self._sanitize_context_options(context_options)
        context = await browser.new_context(**context_options)
        if extra_headers:
            await context.set_extra_http_headers(extra_headers)
        return context

    def _launch_args(self) -> list[str]:
        args = default_launch_args()
        for arg in self.config.launch_args:
            if arg not in args:
                args.append(arg)
        return _sanitize_launch_args(args, headless=self.config.headless)

    def _playwright_context(self) -> Any:
        factory = self.async_playwright_factory
        if factory is None:
            try:
                from playwright.async_api import async_playwright
            except ImportError as exc:
                raise XianyuBrowserTransportError(
                    "playwright is not installed; run `python3 -m pip install playwright` and `python3 -m playwright install chromium`"
                ) from exc
            factory = async_playwright
        return factory()

    @staticmethod
    def _is_search_response(response: Any) -> bool:
        url = getattr(response, "url", "")
        return SEARCH_API_PATTERN in url and ".shade/" not in url and getattr(response.request, "method", None) == "POST"

    def _run_sync(self, coro: Any) -> Any:
        try:
            asyncio.get_running_loop()
        except RuntimeError:
            return asyncio.run(coro)

        outcome: dict[str, Any] = {}
        error: dict[str, BaseException] = {}

        def runner() -> None:
            try:
                outcome["value"] = asyncio.run(coro)
            except BaseException as exc:  # pragma: no cover
                error["exc"] = exc

        thread = threading.Thread(target=runner, daemon=True)
        thread.start()
        thread.join()
        if "exc" in error:
            raise error["exc"]
        return outcome.get("value")

    @staticmethod
    def _load_json(path: Path) -> dict[str, Any]:
        with path.open("r", encoding="utf-8") as handle:
            return json.load(handle)

    @staticmethod
    def _is_playwright_storage_state(payload: dict[str, Any]) -> bool:
        return isinstance(payload, dict) and isinstance(payload.get("cookies"), list) and "origins" in payload

    @staticmethod
    def _extract_storage_state(payload: dict[str, Any]) -> dict[str, Any] | None:
        cookies = payload.get("cookies")
        origins = payload.get("origins")
        if isinstance(cookies, list) or isinstance(origins, list):
            return {
                "cookies": cookies if isinstance(cookies, list) else [],
                "origins": origins if isinstance(origins, list) else [],
            }
        return None

    @staticmethod
    def _state_payload_has_usable_cookies(payload: dict[str, Any]) -> bool:
        storage_state = PlaywrightBrowserTransport._extract_storage_state(payload)
        return bool(storage_state and storage_state.get("cookies"))

    def _build_context_overrides(self, snapshot: dict[str, Any]) -> dict[str, Any]:
        env = snapshot.get("env") or {}
        headers = snapshot.get("headers") or {}
        navigator = env.get("navigator") or {}
        screen = env.get("screen") or {}
        intl = env.get("intl") or {}

        overrides: dict[str, Any] = {}
        user_agent = headers.get("User-Agent") or headers.get("user-agent") or navigator.get("userAgent")
        if user_agent:
            overrides["user_agent"] = user_agent

        accept_language = headers.get("Accept-Language") or headers.get("accept-language")
        locale = accept_language.split(",")[0].strip() if accept_language else navigator.get("language")
        if locale:
            overrides["locale"] = locale

        timezone_id = intl.get("timeZone")
        if timezone_id:
            overrides["timezone_id"] = timezone_id

        width = screen.get("width")
        height = screen.get("height")
        if isinstance(width, (int, float)) and isinstance(height, (int, float)):
            overrides["viewport"] = {"width": int(width), "height": int(height)}

        dpr = screen.get("devicePixelRatio")
        if isinstance(dpr, (int, float)):
            overrides["device_scale_factor"] = float(dpr)

        max_touch_points = navigator.get("maxTouchPoints")
        if isinstance(max_touch_points, (int, float)):
            overrides["has_touch"] = max_touch_points > 0

        mobile_flag = self._looks_like_mobile(user_agent or "")
        if mobile_flag is not None:
            overrides["is_mobile"] = mobile_flag
        return overrides

    @staticmethod
    def _build_extra_headers(raw_headers: Any) -> dict[str, str]:
        if not isinstance(raw_headers, dict):
            return {}
        excluded = {"cookie", "content-length"}
        headers: dict[str, str] = {}
        for key, value in raw_headers.items():
            if not key or value is None or str(key).lower() in excluded:
                continue
            headers[str(key)] = str(value)
        return headers

    @staticmethod
    def _looks_like_mobile(user_agent: str) -> bool | None:
        lowered = user_agent.lower()
        if not lowered:
            return None
        if "mobile" in lowered or "android" in lowered or "iphone" in lowered:
            return True
        if "windows" in lowered or "macintosh" in lowered:
            return False
        return None

    @staticmethod
    def _sanitize_context_options(options: dict[str, Any]) -> dict[str, Any]:
        sanitized = dict(options)
        if sanitized.get("no_viewport"):
            sanitized.pop("viewport", None)
            sanitized.pop("device_scale_factor", None)
        return sanitized
