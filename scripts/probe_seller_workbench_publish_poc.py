#!/usr/bin/env python3
"""Controlled publish POC for the official Goofish seller workbench.

This script creates a real test listing. It requires an explicit confirmation
flag and intentionally does not offline or delete the listing after publishing.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import re
import sys
from datetime import datetime
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


PUBLISH_URL = "https://seller.goofish.com/?site=COMMONPRO#/seller-item/publish"
GOODS_MANAGE_URL = "https://seller.goofish.com/?site=COMMONPRO#/seller-item/goods-manage"
PUBLISH_API_KEYWORDS = (
    "mtop.idle.pc.backend.idleitem.publish",
    "mtop.idle.pc.first.hand.idleitem.publish",
)
MUTATION_KEYWORDS = (
    ".publish",
    ".offline",
    ".delete",
    ".update",
    ".online",
    ".set",
    ".unbind",
    ".create",
    ".modify",
    ".del",
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
        item_id = find_item_id(data)
        if item_id:
            summary["item_id"] = item_id
        for key in ("code", "msg", "message"):
            if key in data:
                summary[key] = data.get(key)
    return summary


def find_item_id(value: Any) -> str:
    if isinstance(value, dict):
        for key in ("itemId", "item_id", "itemID", "id", "itemid"):
            item_id = value.get(key)
            if item_id and re.fullmatch(r"\d{8,}", str(item_id)):
                return str(item_id)
        for child in value.values():
            item_id = find_item_id(child)
            if item_id:
                return item_id
    elif isinstance(value, list):
        for child in value:
            item_id = find_item_id(child)
            if item_id:
                return item_id
    return ""


async def run(args: argparse.Namespace) -> dict[str, Any]:
    if not args.i_understand_this_publishes:
        raise SystemExit("Refusing to run without --i-understand-this-publishes")
    image_path = Path(args.image).resolve()
    if not image_path.exists():
        raise FileNotFoundError(f"image not found: {image_path}")
    state_file = Path(args.state_file)
    if not state_file.exists():
        raise FileNotFoundError(f"state file not found: {state_file}")
    if "[POC勿拍]" not in args.title:
        raise ValueError("title must contain [POC勿拍]")
    if float(args.price) < 9999:
        raise ValueError("price must be >= 9999 for safety")
    if int(args.stock) != 1:
        raise ValueError("stock must be exactly 1 for safety")

    transport = PlaywrightBrowserTransport(
        config=PlaywrightBrowserConfig(
            state_file=str(state_file),
            headless=not args.headed,
            browser_channel=args.browser_channel,
            launch_args=list(args.launch_arg or []),
            context_options=default_desktop_context_options(),
        )
    )
    responses: list[dict[str, Any]] = []
    publish_response: dict[str, Any] | None = None
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
                nonlocal publish_response
                api_name = extract_api_name(response.url)
                if not api_name or not any(keyword in api_name for keyword in MUTATION_KEYWORDS):
                    return
                entry: dict[str, Any] = {
                    "api": api_name,
                    "status": response.status,
                    "url": response.url.split("?")[0],
                }
                try:
                    payload = await asyncio.wait_for(response.json(), timeout=args.response_timeout_ms / 1000)
                    entry["summary"] = summarize_payload(payload)
                    if any(keyword in api_name for keyword in PUBLISH_API_KEYWORDS):
                        publish_response = entry
                except Exception as exc:
                    entry["error"] = str(exc)
                responses.append(entry)

            page.on("response", lambda response: asyncio.create_task(handle_response(response)))

            await page.goto(PUBLISH_URL, wait_until="domcontentloaded", timeout=args.timeout_ms)
            await page.wait_for_timeout(args.settle_ms)
            await close_location_modal(page)

            await page.locator('input[type="file"][accept*="image"]').set_input_files(str(image_path))
            await page.wait_for_timeout(args.upload_wait_ms)

            description = f"{args.title}\n\n{args.description}"
            editor = page.locator('[contenteditable="true"]').first
            await editor.wait_for(state="visible", timeout=args.timeout_ms)
            await editor.click()
            await editor.fill(description)

            visible_price_inputs = page.locator('input[placeholder="0.00"]:visible')
            if await visible_price_inputs.count() < 1:
                raise RuntimeError("price input not found")
            await visible_price_inputs.nth(0).fill(str(args.price))
            if await visible_price_inputs.count() >= 2:
                await visible_price_inputs.nth(1).fill(str(args.price))

            stock_input = page.locator('input[placeholder="1"]:visible')
            if await stock_input.count() < 1:
                raise RuntimeError("stock input not found")
            await stock_input.nth(0).fill(str(args.stock))

            await page.wait_for_timeout(args.settle_ms)
            page_snapshots.append(await page_summary(page, "before_publish"))

            publish_button = page.locator("button", has_text="发布").last
            await publish_button.wait_for(state="visible", timeout=args.timeout_ms)
            if not await publish_button.is_enabled():
                screenshot = str((ROOT_DIR / "scratch/seller-workbench-poc/publish-button-disabled.png").resolve())
                await page.screenshot(path=screenshot, full_page=True)
                raise RuntimeError(f"publish button is disabled; screenshot={screenshot}")

            await publish_button.click()
            await page.wait_for_timeout(args.after_publish_wait_ms)
            page_snapshots.append(await page_summary(page, "after_publish"))

            await page.goto(GOODS_MANAGE_URL, wait_until="domcontentloaded", timeout=args.timeout_ms)
            await page.wait_for_timeout(args.settle_ms)
            goods_text = await page.locator("body").inner_text(timeout=args.timeout_ms)
            page_snapshots.append(await page_summary(page, "goods_manage_after_publish"))

            screenshot_path = ROOT_DIR / "scratch/seller-workbench-poc/publish-result.png"
            await page.screenshot(path=str(screenshot_path), full_page=True)

            return {
                "title": args.title,
                "price": args.price,
                "stock": args.stock,
                "image": str(image_path),
                "publish_response": publish_response,
                "mutation_responses": responses,
                "goods_manage_contains_title": args.title in goods_text,
                "goods_manage_contains_poc": "[POC勿拍]" in goods_text,
                "page_snapshots": page_snapshots,
                "screenshot": str(screenshot_path.resolve()),
            }
        finally:
            await browser.close()


async def close_location_modal(page: Any) -> None:
    for selector in (
        ".ant-modal .closeIcon--WKQQBdVj",
        ".ant-modal .ant-modal-close",
        '.ant-modal [aria-label="Close"]',
    ):
        locator = page.locator(selector)
        try:
            if await locator.count():
                await locator.first.click(timeout=2000)
                await page.wait_for_timeout(1000)
                return
        except Exception:
            continue


async def page_summary(page: Any, label: str) -> dict[str, Any]:
    return await page.evaluate(
        """(label) => ({
          label,
          href: location.href,
          title: document.title,
          textSample: (document.body && document.body.innerText || '').slice(0, 1600),
          publishButtonDisabled: Array.from(document.querySelectorAll('button'))
            .filter((btn) => (btn.innerText || '').trim() === '发布')
            .map((btn) => !!btn.disabled),
        })""",
        label,
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Create a real POC listing in the official Goofish seller workbench.")
    parser.add_argument("--i-understand-this-publishes", action="store_true")
    parser.add_argument("--state-file", default="xianyu_state.json")
    parser.add_argument("--browser-channel", default="chrome")
    parser.add_argument("--headed", action="store_true")
    parser.add_argument("--launch-arg", action="append", default=[])
    parser.add_argument("--timeout-ms", type=int, default=30000)
    parser.add_argument("--settle-ms", type=int, default=3000)
    parser.add_argument("--upload-wait-ms", type=int, default=10000)
    parser.add_argument("--after-publish-wait-ms", type=int, default=15000)
    parser.add_argument("--response-timeout-ms", type=int, default=8000)
    parser.add_argument("--image", required=True)
    parser.add_argument(
        "--title",
        default=f"[POC勿拍] 官方卖家工作台适配器联调测试 {datetime.now().strftime('%Y%m%d-%H%M')}",
    )
    parser.add_argument(
        "--description",
        default="系统联调测试商品，请勿拍，不发货。用于验证官方卖家工作台适配器发布链路。",
    )
    parser.add_argument("--price", default="9999.00")
    parser.add_argument("--stock", default="1")
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
