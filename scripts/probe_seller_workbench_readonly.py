#!/usr/bin/env python3
"""Read-only probe for the official Goofish seller workbench.

The probe reuses an existing Xianyu storage-state file, opens seller workbench
pages, and records summaries of allowlisted read-only mtop responses. It does
not call publish/offline/delete/update APIs.
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


SELLER_BASE_URL = "https://seller.goofish.com/?site=COMMONPRO#/seller-item"
PAGE_URLS = {
    "goods-manage": f"{SELLER_BASE_URL}/goods-manage",
    "publish": f"{SELLER_BASE_URL}/publish",
}

READONLY_APIS = {
    "mtop.alibaba.idle.seller.pc.common.item.search",
    "mtop.taobao.idle.seller.platform.pc.item.status.statistics",
    "mtop.idle.pc.backend.idleitem.preget",
    "mtop.alibaba.idle.seller.platform.freight.template.pc.all",
    "mtop.taobao.idle.local.poi.get",
    "mtop.taobao.idle.seller.platform.item.pc.search.categories",
    "mtop.taobao.idle.seller.platform.item.pc.fix.search.term.query",
    "mtop.taobao.idle.item.pc.category.list",
    "mtop.taobao.idle.seller.platform.item.pc.category.property.query",
}

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

    summary: dict[str, Any] = {
        "ret": payload.get("ret"),
        "success": payload.get("success"),
    }
    data = payload.get("data")
    if isinstance(data, dict):
        summary["data_keys"] = sorted(str(key) for key in data.keys())[:80]
        counts: dict[str, int] = {}
        samples: dict[str, list[str]] = {}
        collect_list_summaries(data, counts, samples)
        if counts:
            summary["list_counts"] = counts
        if samples:
            summary["samples"] = samples
    elif data is not None:
        summary["data_type"] = type(data).__name__
    return summary


def collect_list_summaries(
    value: Any,
    counts: dict[str, int],
    samples: dict[str, list[str]],
    *,
    path: str = "data",
    depth: int = 0,
) -> None:
    if depth > 4:
        return
    if isinstance(value, list):
        counts[path] = len(value)
        item_ids: list[str] = []
        titles: list[str] = []
        for item in value[:5]:
            if not isinstance(item, dict):
                continue
            item_id = first_text_value(item, ("itemId", "item_id", "id"))
            title = first_text_value(item, ("title", "itemTitle", "name"))
            if item_id:
                item_ids.append(item_id)
            if title:
                titles.append(title[:80])
        if item_ids:
            samples[f"{path}.ids"] = item_ids
        if titles:
            samples[f"{path}.titles"] = titles
        return
    if isinstance(value, dict):
        for key, child in value.items():
            if isinstance(child, (dict, list)):
                collect_list_summaries(
                    child,
                    counts,
                    samples,
                    path=f"{path}.{key}",
                    depth=depth + 1,
                )


def first_text_value(payload: dict[str, Any], keys: tuple[str, ...]) -> str:
    for key in keys:
        value = payload.get(key)
        if value is not None:
            text = str(value).strip()
            if text:
                return text
    return ""


async def run_probe(args: argparse.Namespace) -> dict[str, Any]:
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
    captures: dict[str, dict[str, Any]] = {}
    mutation_hits: list[dict[str, str]] = []
    page_summaries: list[dict[str, Any]] = []
    pending_response_tasks: set[asyncio.Task[None]] = set()

    async with transport._playwright_context() as playwright:
        browser = await playwright.chromium.launch(
            channel=args.browser_channel,
            headless=not args.headed,
            args=transport._launch_args(),
        )
        try:
            context = await transport._new_context(browser)
            page = await context.new_page()

            async def capture_response(response: Any) -> None:
                api_name = extract_api_name(response.url)
                if not api_name:
                    return
                if any(keyword in api_name for keyword in MUTATION_KEYWORDS):
                    mutation_hits.append({"api": api_name, "url": response.url.split("?")[0]})
                    return
                if api_name not in READONLY_APIS or api_name in captures:
                    return
                try:
                    payload = await asyncio.wait_for(
                        response.json(),
                        timeout=max(args.response_timeout_ms / 1000, 1),
                    )
                    captures[api_name] = {
                        "status": response.status,
                        "url": response.url.split("?")[0],
                        "summary": summarize_payload(payload),
                    }
                except Exception as exc:
                    captures[api_name] = {
                        "status": response.status,
                        "url": response.url.split("?")[0],
                        "error": str(exc),
                    }

            def handle_response(response: Any) -> None:
                task = asyncio.create_task(capture_response(response))
                pending_response_tasks.add(task)
                task.add_done_callback(pending_response_tasks.discard)

            page.on("response", handle_response)
            try:
                for page_name in args.pages:
                    url = PAGE_URLS[page_name]
                    await page.goto(url, wait_until="domcontentloaded", timeout=args.timeout_ms)
                    await page.wait_for_timeout(args.settle_ms)
                    if pending_response_tasks:
                        _, pending = await asyncio.wait(
                            list(pending_response_tasks),
                            timeout=max(args.response_timeout_ms / 1000, 1),
                        )
                        for task in pending:
                            task.cancel()
                    page_summaries.append(
                        await page.evaluate(
                            """
                            () => ({
                              href: location.href,
                              title: document.title,
                              textSample: (document.body && document.body.innerText || '').slice(0, 1200),
                            })
                            """
                        )
                    )
            finally:
                if pending_response_tasks:
                    _, pending = await asyncio.wait(
                        list(pending_response_tasks),
                        timeout=max(args.response_timeout_ms / 1000, 1),
                    )
                    for task in pending:
                        task.cancel()
                page.remove_listener("response", handle_response)
                await page.close()
                await context.close()
        finally:
            await browser.close()

    return {
        "pages": page_summaries,
        "captured_readonly_apis": captures,
        "missing_readonly_apis": sorted(READONLY_APIS - set(captures)),
        "mutation_api_hits": mutation_hits,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Probe official Goofish seller workbench read-only mtop responses.")
    parser.add_argument("--state-file", default="xianyu_state.json", help="Playwright storage-state or exported Xianyu state JSON.")
    parser.add_argument("--browser-channel", default="chrome")
    parser.add_argument("--headed", action="store_true", help="Run with a visible browser.")
    parser.add_argument("--timeout-ms", type=int, default=30000)
    parser.add_argument("--settle-ms", type=int, default=5000, help="Wait after each page load to collect responses.")
    parser.add_argument("--response-timeout-ms", type=int, default=8000, help="Maximum time to read each mtop response body.")
    parser.add_argument("--launch-arg", action="append", default=[])
    parser.add_argument(
        "--pages",
        nargs="+",
        choices=sorted(PAGE_URLS),
        default=["goods-manage", "publish"],
        help="Seller workbench pages to open.",
    )
    parser.add_argument("--output-file", help="Optional JSON output path.")
    args = parser.parse_args()

    result = asyncio.run(run_probe(args))
    text = json.dumps(result, ensure_ascii=False, indent=2)
    if args.output_file:
        Path(args.output_file).write_text(text + "\n", encoding="utf-8")
    print(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
