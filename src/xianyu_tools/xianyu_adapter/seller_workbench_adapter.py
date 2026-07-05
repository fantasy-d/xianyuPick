from __future__ import annotations

import asyncio
import re
import threading
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Literal

from xianyu_tools.xianyu_adapter.browser_transport import (
    PlaywrightBrowserConfig,
    PlaywrightBrowserTransport,
    default_desktop_context_options,
)


GOODS_MANAGE_URL = "https://seller.goofish.com/?site=COMMONPRO#/seller-item/goods-manage"
OFFLINE_API_KEYWORDS = (
    "mtop.alibaba.idle.seller.pc.item.offline",
    "mtop.alibaba.idle.seller.pc.item.batch.offline",
)
DELETE_API_KEYWORDS = (
    "mtop.alibaba.idle.seller.pc.item.delete",
    "mtop.alibaba.idle.seller.pc.item.batch.delete",
)
API_RE = re.compile(r"/h5/([^/?]+)/")


class SellerWorkbenchAdapterError(RuntimeError):
    pass


@dataclass(slots=True)
class SellerWorkbenchItem:
    item_id: str
    title: str
    price_text: str
    stock_text: str
    sold_text: str
    created_at: str
    status: str
    row_text: str = ""

    def to_dict(self) -> dict[str, str]:
        return asdict(self)


@dataclass(slots=True)
class SellerWorkbenchMutationResult:
    item_id: str
    action: Literal["offline", "delete"]
    status: str
    message: str
    api_response: dict[str, Any] | None
    before_contains_item: bool
    after_contains_item: bool
    before_contains_expected_title: bool | None = None
    after_contains_expected_title: bool | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def extract_api_name(url: str) -> str:
    match = API_RE.search(url)
    return match.group(1).lower() if match else ""


def summarize_payload(payload: Any) -> dict[str, Any]:
    if not isinstance(payload, dict):
        return {"type": type(payload).__name__}
    data = payload.get("data")
    summary: dict[str, Any] = {
        "ret": payload.get("ret"),
        "success": payload.get("success"),
        "data_type": type(data).__name__ if data is not None else None,
    }
    if isinstance(data, dict):
        summary["data_keys"] = sorted(str(key) for key in data.keys())[:80]
        for key in ("code", "msg", "message"):
            if key in data:
                summary[key] = data.get(key)
    return summary


class SellerWorkbenchAdapter:
    """Official Goofish seller workbench adapter backed by a browser session.

    This is intentionally narrower than PublisherV3. It only contains the
    POC-proven list/offline/delete paths and does not replace OpenAPI publishing.
    """

    def __init__(
        self,
        *,
        config: PlaywrightBrowserConfig | None = None,
        timeout_ms: int = 30000,
        settle_ms: int = 5000,
        response_timeout_ms: int = 8000,
    ) -> None:
        self.config = config or PlaywrightBrowserConfig(
            state_file="xianyu_state.json",
            headless=True,
            browser_channel="chrome",
            context_options=default_desktop_context_options(),
        )
        self.timeout_ms = timeout_ms
        self.settle_ms = settle_ms
        self.response_timeout_ms = response_timeout_ms
        self.transport = PlaywrightBrowserTransport(config=self.config)

    @classmethod
    def from_state_file(
        cls,
        state_file: str,
        *,
        headless: bool = True,
        browser_channel: str = "chrome",
        launch_args: list[str] | None = None,
    ) -> "SellerWorkbenchAdapter":
        if not Path(state_file).exists():
            raise SellerWorkbenchAdapterError(f"state file not found: {state_file}")
        return cls(
            config=PlaywrightBrowserConfig(
                state_file=state_file,
                headless=headless,
                browser_channel=browser_channel,
                launch_args=list(launch_args or []),
                context_options=default_desktop_context_options(),
            )
        )

    def list_items(self, *, status: Literal["on_sale", "offline"] = "on_sale") -> list[SellerWorkbenchItem]:
        return self._run_sync(self._list_items(status=status))

    def depublish_item(
        self,
        item_id: str,
        *,
        confirm_item_id: str,
        expected_title_substring: str = "",
    ) -> SellerWorkbenchMutationResult:
        self._validate_confirmed_item(item_id, confirm_item_id)
        return self._run_sync(
            self._mutate_item(
                action="offline",
                item_id=item_id,
                expected_title_substring=expected_title_substring,
            )
        )

    def delete_item(
        self,
        item_id: str,
        *,
        confirm_item_id: str,
        expected_title_substring: str,
    ) -> SellerWorkbenchMutationResult:
        self._validate_confirmed_item(item_id, confirm_item_id)
        if not expected_title_substring:
            raise SellerWorkbenchAdapterError("expected_title_substring is required for delete_item")
        return self._run_sync(
            self._mutate_item(
                action="delete",
                item_id=item_id,
                expected_title_substring=expected_title_substring,
            )
        )

    async def _list_items(self, *, status: Literal["on_sale", "offline"]) -> list[SellerWorkbenchItem]:
        async with self.transport._playwright_context() as playwright:
            browser = await playwright.chromium.launch(
                channel=self.config.browser_channel,
                headless=self.config.headless,
                args=self.transport._launch_args(),
            )
            try:
                context = await self.transport._new_context(browser)
                page = await context.new_page()
                try:
                    await page.goto(GOODS_MANAGE_URL, wait_until="domcontentloaded", timeout=self.timeout_ms)
                    await page.wait_for_timeout(self.settle_ms)
                    if status == "offline":
                        await self._switch_to_offline_tab(page)
                        await page.wait_for_timeout(self.settle_ms)
                    rows = await self._extract_table_rows(page)
                    return [SellerWorkbenchItem(status=status, **row) for row in rows]
                finally:
                    await page.close()
                    await context.close()
            finally:
                await browser.close()

    async def _mutate_item(
        self,
        *,
        action: Literal["offline", "delete"],
        item_id: str,
        expected_title_substring: str,
    ) -> SellerWorkbenchMutationResult:
        self._validate_item_id(item_id)
        api_keywords = OFFLINE_API_KEYWORDS if action == "offline" else DELETE_API_KEYWORDS
        button_text = "下架" if action == "offline" else "删除"
        confirm_texts = ("确 定", "确定", "确认", "立即下架", "下架") if action == "offline" else (
            "确 定",
            "确定",
            "确认",
            "立即删除",
            "删除",
        )

        mutation_responses: list[dict[str, Any]] = []
        pending_tasks: set[asyncio.Task[None]] = set()

        async with self.transport._playwright_context() as playwright:
            browser = await playwright.chromium.launch(
                channel=self.config.browser_channel,
                headless=self.config.headless,
                args=self.transport._launch_args(),
            )
            try:
                context = await self.transport._new_context(browser)
                page = await context.new_page()

                async def capture_response(response: Any) -> None:
                    api_name = extract_api_name(response.url)
                    if not api_name or not any(keyword in api_name for keyword in api_keywords):
                        return
                    entry: dict[str, Any] = {
                        "api": api_name,
                        "status": response.status,
                        "url": response.url.split("?")[0],
                    }
                    try:
                        payload = await asyncio.wait_for(
                            response.json(),
                            timeout=max(self.response_timeout_ms / 1000, 1),
                        )
                        entry["summary"] = summarize_payload(payload)
                    except Exception as exc:
                        entry["error"] = str(exc)
                    mutation_responses.append(entry)

                def handle_response(response: Any) -> None:
                    task = asyncio.create_task(capture_response(response))
                    pending_tasks.add(task)
                    task.add_done_callback(pending_tasks.discard)

                page.on("response", handle_response)
                try:
                    await page.goto(GOODS_MANAGE_URL, wait_until="domcontentloaded", timeout=self.timeout_ms)
                    await page.wait_for_timeout(self.settle_ms)
                    if action == "delete":
                        await self._switch_to_offline_tab(page)
                        await page.wait_for_timeout(self.settle_ms)

                    before_text = await page.locator("body").inner_text(timeout=self.timeout_ms)
                    self._assert_target_present(before_text, item_id, expected_title_substring, action)
                    row = page.locator("tr", has_text=item_id)
                    row_count = await row.count()
                    if row_count != 1:
                        raise SellerWorkbenchAdapterError(f"expected exactly one row for item {item_id}, got {row_count}")
                    row_text = await row.first.inner_text(timeout=self.timeout_ms)
                    if expected_title_substring and expected_title_substring not in row_text:
                        raise SellerWorkbenchAdapterError("matched row does not contain expected title substring")

                    action_button = row.locator("button", has_text=button_text)
                    if await action_button.count() < 1:
                        action_button = row.locator(f"text={button_text}")
                    if await action_button.count() < 1:
                        raise SellerWorkbenchAdapterError(f"{button_text} button for item {item_id} not found")

                    await action_button.first.click(timeout=self.timeout_ms)
                    await page.wait_for_timeout(1000)
                    await self._click_confirm_if_present(page, confirm_texts)
                    await page.wait_for_timeout(self.settle_ms)

                    await self._drain_response_tasks(pending_tasks)
                    if action == "delete":
                        await page.goto(GOODS_MANAGE_URL, wait_until="domcontentloaded", timeout=self.timeout_ms)
                        await page.wait_for_timeout(self.settle_ms)
                        await self._switch_to_offline_tab(page)
                        await page.wait_for_timeout(self.settle_ms)
                    else:
                        await page.goto(GOODS_MANAGE_URL, wait_until="domcontentloaded", timeout=self.timeout_ms)
                        await page.wait_for_timeout(self.settle_ms)
                    after_text = await page.locator("body").inner_text(timeout=self.timeout_ms)
                finally:
                    page.remove_listener("response", handle_response)
                    await self._drain_response_tasks(pending_tasks)
                    await page.close()
                    await context.close()
            finally:
                await browser.close()

        api_response = mutation_responses[-1] if mutation_responses else None
        succeeded = self._response_succeeded(api_response) and item_id not in after_text
        message = self._response_message(api_response) or ("成功" if succeeded else "未确认成功")
        return SellerWorkbenchMutationResult(
            item_id=item_id,
            action=action,
            status="success" if succeeded else "failed",
            message=message,
            api_response=api_response,
            before_contains_item=item_id in before_text,
            after_contains_item=item_id in after_text,
            before_contains_expected_title=bool(expected_title_substring and expected_title_substring in before_text)
            if expected_title_substring
            else None,
            after_contains_expected_title=bool(expected_title_substring and expected_title_substring in after_text)
            if expected_title_substring
            else None,
        )

    async def _extract_table_rows(self, page: Any) -> list[dict[str, str]]:
        return await page.evaluate(
            """() => {
              const rows = [];
              for (const row of Array.from(document.querySelectorAll('tbody tr'))) {
                const cells = Array.from(row.querySelectorAll('td'))
                  .map((cell) => (cell.innerText || '').trim())
                  .filter(Boolean);
                const rowText = (row.innerText || '').trim();
                const idMatch = rowText.match(/商品ID\\s*(\\d{8,})/) || rowText.match(/\\b(\\d{8,})\\b/);
                if (!idMatch || cells.length < 2) continue;
                const titleLines = (cells[0] || '').split(/\\n+/)
                  .map((line) => line.trim())
                  .filter((line) => line && line !== '商品ID' && !/^\\d{8,}$/.test(line));
                rows.push({
                  item_id: idMatch[1],
                  title: titleLines[0] || '',
                  price_text: cells[1] || '',
                  stock_text: cells[2] || '',
                  sold_text: cells[3] || '',
                  created_at: cells[4] || '',
                  row_text: rowText,
                });
              }
              return rows;
            }"""
        )

    async def _switch_to_offline_tab(self, page: Any) -> None:
        clicked = await page.evaluate(
            """() => {
              const visible = (el) => {
                const rect = el.getBoundingClientRect();
                const style = window.getComputedStyle(el);
                return rect.width > 0 && rect.height > 0 && style.visibility !== 'hidden' && style.display !== 'none';
              };
              const candidates = Array.from(document.querySelectorAll('*'))
                .filter((el) => visible(el) && (el.innerText || '').trim() === '下架')
                .map((el) => ({ el, rect: el.getBoundingClientRect() }))
                .filter((entry) => entry.rect.top < 320)
                .sort((a, b) => a.rect.top - b.rect.top || a.rect.left - b.rect.left);
              if (!candidates.length) return false;
              candidates[0].el.click();
              return true;
            }"""
        )
        if not clicked:
            raise SellerWorkbenchAdapterError("failed to switch to offline tab")

    async def _click_confirm_if_present(self, page: Any, texts: tuple[str, ...]) -> None:
        scoped_selectors = (".ant-modal", ".ant-popconfirm", ".ant-popover")
        for scope in scoped_selectors:
            for text in texts:
                locator = page.locator(scope).locator("button", has_text=text)
                try:
                    if await locator.count():
                        await locator.last.click(timeout=self.timeout_ms)
                        return
                except Exception:
                    continue
        safe_fallback_texts = tuple(text for text in texts if text not in {"下架", "删除"})
        for text in safe_fallback_texts:
            locator = page.get_by_text(text, exact=True)
            try:
                if await locator.count():
                    await locator.last.click(timeout=self.timeout_ms)
                    return
            except Exception:
                continue

    async def _drain_response_tasks(self, pending_tasks: set[asyncio.Task[None]]) -> None:
        if not pending_tasks:
            return
        _, pending = await asyncio.wait(
            list(pending_tasks),
            timeout=max(self.response_timeout_ms / 1000, 1),
        )
        for task in pending:
            task.cancel()

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

    def _assert_target_present(
        self,
        page_text: str,
        item_id: str,
        expected_title_substring: str,
        action: str,
    ) -> None:
        if item_id not in page_text:
            raise SellerWorkbenchAdapterError(f"item {item_id} not found before {action}")
        if expected_title_substring and expected_title_substring not in page_text:
            raise SellerWorkbenchAdapterError(
                f"expected title substring {expected_title_substring!r} not found before {action}"
            )

    @staticmethod
    def _validate_confirmed_item(item_id: str, confirm_item_id: str) -> None:
        SellerWorkbenchAdapter._validate_item_id(item_id)
        if confirm_item_id != item_id:
            raise SellerWorkbenchAdapterError("confirm_item_id must match item_id")

    @staticmethod
    def _validate_item_id(item_id: str) -> None:
        if not re.fullmatch(r"\d{8,}", item_id):
            raise SellerWorkbenchAdapterError("item id must be numeric")

    @staticmethod
    def _response_succeeded(response: dict[str, Any] | None) -> bool:
        if not response:
            return False
        summary = response.get("summary")
        if not isinstance(summary, dict):
            return False
        ret = summary.get("ret")
        code = str(summary.get("code") or "").lower()
        return code == "success" or (
            isinstance(ret, list) and any(str(item).startswith("SUCCESS::") for item in ret)
        )

    @staticmethod
    def _response_message(response: dict[str, Any] | None) -> str:
        if not response:
            return ""
        summary = response.get("summary")
        if not isinstance(summary, dict):
            return str(response.get("error") or "")
        return str(summary.get("msg") or summary.get("message") or "")
