#!/usr/bin/env python3
"""Controlled delete POC for one down-shelf Goofish seller workbench item.

This script performs a real delete action for one item ID. It requires an
explicit confirmation flag and only deletes a row that matches the expected
title marker.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import re
import sys
from pathlib import Path
from typing import Any

ROOT_DIR = Path(__file__).resolve().parents[1]
SRC_DIR = ROOT_DIR / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from xianyu_tools.xianyu_adapter.browser_transport import (
    PlaywrightBrowserConfig,
    PlaywrightBrowserTransport,
    default_desktop_context_options,
)


GOODS_MANAGE_URL = "https://seller.goofish.com/?site=COMMONPRO#/seller-item/goods-manage"
DELETE_API_KEYWORDS = (
    "mtop.alibaba.idle.seller.pc.item.delete",
    "mtop.alibaba.idle.seller.pc.item.batch.delete",
)
API_RE = re.compile(r"/h5/([^/?]+)/")


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


async def run(args: argparse.Namespace) -> dict[str, Any]:
    if not args.i_understand_this_deletes:
        raise SystemExit("Refusing to run without --i-understand-this-deletes")
    if not re.fullmatch(r"\d{8,}", args.item_id):
        raise ValueError("item id must be numeric")
    if not args.expected_title_substring:
        raise ValueError("expected title substring is required")
    state_file = Path(args.state_file)
    if not state_file.exists():
        raise FileNotFoundError(f"state file not found: {state_file}")

    transport = PlaywrightBrowserTransport(
        config=PlaywrightBrowserConfig(
            state_file=str(state_file),
            headless=not args.headed,
            browser_channel=args.browser_channel,
            launch_args=list(args.launch_arg or []),
            context_options=default_desktop_context_options(),
        )
    )

    mutation_responses: list[dict[str, Any]] = []
    delete_response: dict[str, Any] | None = None
    page_snapshots: list[dict[str, Any]] = []

    async with transport._playwright_context() as playwright:
        browser = await playwright.chromium.launch(
            channel=args.browser_channel,
            headless=not args.headed,
            args=transport._launch_args(),
        )
        try:
            context = await transport._new_context(browser)
            page = await context.new_page()

            async def handle_response(response: Any) -> None:
                nonlocal delete_response
                api_name = extract_api_name(response.url)
                if not api_name or not any(keyword in api_name for keyword in DELETE_API_KEYWORDS):
                    return
                entry: dict[str, Any] = {
                    "api": api_name,
                    "status": response.status,
                    "url": response.url.split("?")[0],
                }
                try:
                    payload = await asyncio.wait_for(response.json(), timeout=args.response_timeout_ms / 1000)
                    entry["summary"] = summarize_payload(payload)
                except Exception as exc:
                    entry["error"] = str(exc)
                mutation_responses.append(entry)
                delete_response = entry

            page.on("response", lambda response: asyncio.create_task(handle_response(response)))

            await page.goto(GOODS_MANAGE_URL, wait_until="domcontentloaded", timeout=args.timeout_ms)
            await page.wait_for_timeout(args.settle_ms)
            page_snapshots.append(await page_summary(page, "on_sale_before_switch"))

            await switch_to_offline_tab(page)
            await page.wait_for_timeout(args.settle_ms)
            before_text = await page.locator("body").inner_text(timeout=args.timeout_ms)
            page_snapshots.append(await page_summary(page, "offline_before_delete"))
            if args.item_id not in before_text:
                raise RuntimeError(f"item {args.item_id} not found in offline list before delete")
            if args.expected_title_substring not in before_text:
                raise RuntimeError(
                    f"expected title substring {args.expected_title_substring!r} not found before delete"
                )

            row = page.locator("tr", has_text=args.item_id)
            row_count = await row.count()
            if row_count < 1:
                raise RuntimeError(f"table row for item {args.item_id} not found in offline list")
            if row_count > 1:
                raise RuntimeError(f"ambiguous rows for item {args.item_id}: {row_count}")
            row_text = await row.first.inner_text(timeout=args.timeout_ms)
            if args.expected_title_substring not in row_text:
                raise RuntimeError(f"matched row does not contain expected title marker: {row_text[:200]}")

            delete_button = row.locator("button", has_text="删除")
            if await delete_button.count() < 1:
                delete_button = row.locator("text=删除")
            if await delete_button.count() < 1:
                raise RuntimeError(f"delete button for item {args.item_id} not found")

            await delete_button.first.click(timeout=args.timeout_ms)
            await page.wait_for_timeout(1000)
            await click_confirm_if_present(page, args.timeout_ms)
            await page.wait_for_timeout(args.after_delete_wait_ms)
            page_snapshots.append(await page_summary(page, "after_delete_click"))

            await page.goto(GOODS_MANAGE_URL, wait_until="domcontentloaded", timeout=args.timeout_ms)
            await page.wait_for_timeout(args.settle_ms)
            await switch_to_offline_tab(page)
            await page.wait_for_timeout(args.settle_ms)
            after_text = await page.locator("body").inner_text(timeout=args.timeout_ms)
            page_snapshots.append(await page_summary(page, "offline_after_delete"))

            screenshot_path = ROOT_DIR / "scratch/seller-workbench-poc/delete-result.png"
            await page.screenshot(path=str(screenshot_path), full_page=True)

            return {
                "item_id": args.item_id,
                "expected_title_substring": args.expected_title_substring,
                "delete_response": delete_response,
                "mutation_responses": mutation_responses,
                "before_contains_item": args.item_id in before_text,
                "after_contains_item": args.item_id in after_text,
                "after_contains_expected_title": args.expected_title_substring in after_text,
                "page_snapshots": page_snapshots,
                "screenshot": str(screenshot_path.resolve()),
            }
        finally:
            await browser.close()


async def switch_to_offline_tab(page: Any) -> None:
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
        raise RuntimeError("failed to switch to offline tab")


async def click_confirm_if_present(page: Any, timeout_ms: int) -> None:
    scoped_selectors = (".ant-modal", ".ant-popconfirm", ".ant-popover", "body")
    texts = ("确 定", "确定", "确认", "删除", "立即删除")
    for scope in scoped_selectors:
        for text in texts:
            locator = page.locator(scope).locator("button", has_text=text)
            try:
                count = await locator.count()
                if count:
                    await locator.last.click(timeout=timeout_ms)
                    return
            except Exception:
                continue
    for text in texts:
        locator = page.get_by_text(text, exact=True)
        try:
            count = await locator.count()
            if count:
                await locator.last.click(timeout=timeout_ms)
                return
        except Exception:
            continue


async def page_summary(page: Any, label: str) -> dict[str, Any]:
    return await page.evaluate(
        """(label) => ({
          label,
          href: location.href,
          title: document.title,
          textSample: (document.body && document.body.innerText || '').slice(0, 2000),
        })""",
        label,
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Delete one down-shelf real item in the official Goofish seller workbench.")
    parser.add_argument("--i-understand-this-deletes", action="store_true")
    parser.add_argument("--item-id", required=True)
    parser.add_argument("--expected-title-substring", default="[POC勿拍]")
    parser.add_argument("--state-file", default="xianyu_state.json")
    parser.add_argument("--browser-channel", default="chrome")
    parser.add_argument("--headed", action="store_true", help="Run with a visible browser. Default is headless.")
    parser.add_argument("--launch-arg", action="append", default=[])
    parser.add_argument("--timeout-ms", type=int, default=30000)
    parser.add_argument("--settle-ms", type=int, default=5000)
    parser.add_argument("--after-delete-wait-ms", type=int, default=8000)
    parser.add_argument("--response-timeout-ms", type=int, default=8000)
    parser.add_argument("--output-file", help="Optional JSON output path.")
    args = parser.parse_args()

    result = asyncio.run(run(args))
    text = json.dumps(result, ensure_ascii=False, indent=2)
    if args.output_file:
        Path(args.output_file).write_text(text + "\n", encoding="utf-8")
    print(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
