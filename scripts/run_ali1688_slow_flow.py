#!/usr/bin/env python3
from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path
import random

from playwright.async_api import async_playwright
import pyautogui

from xianyu_tools.xianyu_adapter.browser_transport import (
    default_desktop_context_options,
    default_launch_args,
)

DEFAULT_ALI1688_USER_DATA_DIR = str(
    (Path(__file__).resolve().parents[1] / "profiles" / "ali1688_chrome_profile").resolve()
)


async def _dump_page(page, output_dir: Path, name: str) -> None:
    html = await page.content()
    (output_dir / f"{name}.html").write_text(html, encoding="utf-8")
    print(json.dumps({"step": "dump", "name": name, "url": page.url}, ensure_ascii=False), flush=True)


async def _dump_json(output_dir: Path, name: str, payload: dict) -> None:
    (output_dir / f"{name}.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"step": "dump_json", "name": name}, ensure_ascii=False), flush=True)


def _write_summary(path: str | None, payload: dict) -> None:
    if not path:
        return
    Path(path).write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


async def _switch_to_latest_page(context, page, output_dir: Path, name: str):
    pages = context.pages
    latest = pages[-1] if pages else page
    if latest is not page:
        await latest.wait_for_load_state("domcontentloaded", timeout=15000)
        print(
            json.dumps(
                {"step": "switch_page", "name": name, "from_url": page.url, "to_url": latest.url, "page_count": len(pages)},
                ensure_ascii=False,
            ),
            flush=True,
        )
        await _dump_page(latest, output_dir, name)
        return latest
    print(json.dumps({"step": "page_count", "name": name, "page_count": len(pages), "url": page.url}, ensure_ascii=False), flush=True)
    return page


async def _recover_to_ali1688_search_page(context, page):
    pages = list(context.pages)
    for candidate in reversed(pages):
        try:
            if candidate.is_closed():
                continue
        except Exception:
            continue
        url = candidate.url or ""
        if "login.taobao.com" in url:
            try:
                await candidate.close()
            except Exception:
                pass
            continue
        if "1688.com" in url:
            return candidate
    recovered = await context.new_page()
    await recovered.goto("https://www.1688.com/", wait_until="domcontentloaded", timeout=30000)
    return recovered


async def _drag_slider_track(locator) -> bool:
    handle = await locator.element_handle()
    if handle is None:
        return False
    geometry = await handle.evaluate(
        """
        (node) => {
          const handleRect = node.getBoundingClientRect();
          const trackNode = node.closest('.nc_scale') || node.parentElement;
          const trackRect = trackNode ? trackNode.getBoundingClientRect() : handleRect;
          return {
            handle: {x: handleRect.x, y: handleRect.y, width: handleRect.width, height: handleRect.height},
            track: {x: trackRect.x, y: trackRect.y, width: trackRect.width, height: trackRect.height},
          };
        }
        """
    )
    if not geometry:
        return False
    handle_rect = geometry["handle"]
    track = geometry["track"]
    if track["width"] <= 0 or track["height"] <= 0 or handle_rect["width"] <= 0 or handle_rect["height"] <= 0:
        return False
    page = locator.page
    start_x = handle_rect["x"] + handle_rect["width"] / 2
    start_y = handle_rect["y"] + handle_rect["height"] / 2
    end_x = track["x"] + track["width"] - handle_rect["width"] / 2 - 2
    y = start_y
    rng = random.Random()
    # Temporarily bypass the global slow_mo cadence for the slider itself.
    original_timeout = page.context._impl_obj._timeout_settings.default_timeout()
    page.set_default_timeout(5000)
    await page.mouse.move(start_x - rng.uniform(3, 7), start_y + rng.uniform(-0.5, 0.5))
    await asyncio.sleep(rng.uniform(0.01, 0.02))
    await page.mouse.move(start_x, start_y, steps=4)
    await asyncio.sleep(rng.uniform(0.005, 0.01))
    await page.mouse.down()
    await asyncio.sleep(rng.uniform(0.002, 0.006))

    current_x = start_x
    total_distance = max(1.0, end_x - start_x)
    progress_points = [0.05, 0.1, 0.16, 0.23, 0.31, 0.4, 0.5, 0.6, 0.69, 0.77, 0.84, 0.9, 0.95, 0.98, 1.0]
    for progress in progress_points:
        target_x = start_x + total_distance * progress
        target_x = max(current_x + 1, min(end_x + 3, target_x))
        target_y = y + rng.uniform(-1.1, 1.1)
        steps = rng.randint(10, 16)
        await page.mouse.move(target_x, target_y, steps=steps)
        current_x = target_x

    overshoot_x = min(end_x + rng.uniform(0.8, 1.8), track["x"] + track["width"] - handle_rect["width"] / 2)
    await page.mouse.move(overshoot_x, y + rng.uniform(-0.8, 0.8), steps=rng.randint(12, 18))
    await page.mouse.move(end_x - rng.uniform(0.1, 0.5), y + rng.uniform(-0.6, 0.6), steps=rng.randint(12, 18))
    await asyncio.sleep(rng.uniform(0.01, 0.02))
    await page.mouse.up()
    page.set_default_timeout(original_timeout)
    return True


async def _frame_viewport_offset(frame, page) -> tuple[float, float]:
    if frame == page.main_frame:
        return 0.0, 0.0
    frame_element = await frame.frame_element()
    box = await frame_element.bounding_box()
    if not box:
        return 0.0, 0.0
    return float(box["x"]), float(box["y"])


async def _drag_slider_system_mouse(page, frame, locator) -> bool:
    await locator.wait_for(state="visible", timeout=5000)
    handle = await locator.element_handle()
    if handle is None:
        return False
    await asyncio.sleep(0.2)
    handle = await locator.element_handle()
    if handle is None:
        return False
    geometry = await handle.evaluate(
        """
        (node) => {
          const handleRect = node.getBoundingClientRect();
          const trackNode = node.closest('.nc_scale') || node.parentElement;
          const trackRect = trackNode ? trackNode.getBoundingClientRect() : handleRect;
          return {
            handle: {x: handleRect.x, y: handleRect.y, width: handleRect.width, height: handleRect.height},
            track: {x: trackRect.x, y: trackRect.y, width: trackRect.width, height: trackRect.height},
          };
        }
        """
    )
    viewport = await page.evaluate(
        """
        () => ({
          screenX: window.screenX ?? window.screenLeft ?? 0,
          screenY: window.screenY ?? window.screenTop ?? 0,
          outerWidth: window.outerWidth || 0,
          outerHeight: window.outerHeight || 0,
          innerWidth: window.innerWidth || 0,
          innerHeight: window.innerHeight || 0,
        })
        """
    )
    if not geometry or not viewport:
        return False
    frame_offset_x, frame_offset_y = await _frame_viewport_offset(frame, page)
    handle_rect = geometry["handle"]
    track = geometry["track"]
    border_x = max(0.0, (viewport["outerWidth"] - viewport["innerWidth"]) / 2)
    chrome_y = max(0.0, viewport["outerHeight"] - viewport["innerHeight"] - border_x)
    origin_x = viewport["screenX"] + border_x
    origin_y = viewport["screenY"] + chrome_y

    start_x = origin_x + frame_offset_x + handle_rect["x"] + handle_rect["width"] / 2
    start_y = origin_y + frame_offset_y + handle_rect["y"] + handle_rect["height"] / 2
    track_end_x = origin_x + frame_offset_x + track["x"] + track["width"] - handle_rect["width"] / 2 - 2
    end_x = track_end_x + max(handle_rect["width"] * 1.6, 36.0)
    base_y = start_y

    rng = random.Random()
    pyautogui.moveTo(start_x, base_y, duration=0.04)
    pyautogui.mouseDown()
    total_distance = end_x - start_x
    move_steps = max(90, int(abs(total_distance) / 3.0))
    for index in range(1, move_steps + 1):
        progress = index / move_steps
        # Ease-in acceleration: starts slower, ends faster, close to a human throw.
        eased = progress * progress
        target_x = start_x + total_distance * eased
        # Keep Y nearly flat; only tiny jitter to avoid a mechanically perfect line.
        target_y = base_y + rng.uniform(-0.35, 0.35)
        pyautogui.moveTo(target_x, target_y, duration=0)
    await asyncio.sleep(0.02)

    released = False
    try:
        for _ in range(60):
            if not await _slider_still_present(page):
                pyautogui.mouseUp()
                released = True
                return True
            pyautogui.moveTo(end_x + rng.uniform(3.0, 7.0), base_y + rng.uniform(-0.3, 0.3), duration=0)
            await asyncio.sleep(0.02)
        return False
    finally:
        if not released:
            pyautogui.mouseUp()


async def _read_slider_geometry(locator, frame, page) -> dict | None:
    handle = await locator.element_handle()
    if handle is None:
        return None
    geometry = await handle.evaluate(
        """
        (node) => {
          const handleRect = node.getBoundingClientRect();
          const trackNode = node.closest('.nc_scale') || node.parentElement;
          const wrapperNode = node.closest('.nc_wrapper') || trackNode?.parentElement || null;
          const trackRect = trackNode ? trackNode.getBoundingClientRect() : handleRect;
          const wrapperRect = wrapperNode ? wrapperNode.getBoundingClientRect() : trackRect;
          return {
            handle: {x: handleRect.x, y: handleRect.y, width: handleRect.width, height: handleRect.height},
            track: {x: trackRect.x, y: trackRect.y, width: trackRect.width, height: trackRect.height},
            wrapper: {x: wrapperRect.x, y: wrapperRect.y, width: wrapperRect.width, height: wrapperRect.height},
          };
        }
        """
    )
    viewport = await page.evaluate(
        """
        () => ({
          screenX: window.screenX ?? window.screenLeft ?? 0,
          screenY: window.screenY ?? window.screenTop ?? 0,
          outerWidth: window.outerWidth || 0,
          outerHeight: window.outerHeight || 0,
          innerWidth: window.innerWidth || 0,
          innerHeight: window.innerHeight || 0,
          devicePixelRatio: window.devicePixelRatio || 1,
          url: location.href,
          title: document.title,
        })
        """
    )
    frame_offset_x, frame_offset_y = await _frame_viewport_offset(frame, page)
    return {"geometry": geometry, "viewport": viewport, "frame_offset": {"x": frame_offset_x, "y": frame_offset_y}}


async def _find_slider_control(frame):
    selectors = [
        ".btn_slide",
        ".nc_1_n1z",
        ".nc_scale .btn_slide",
        "[class*='btn_slide']",
        "[class*='nc_1_n1z']",
    ]
    for selector in selectors:
        locator = frame.locator(selector).first
        try:
            if await locator.count() and await locator.is_visible():
                return locator
        except Exception:
            continue
    return None


async def _find_slider_frame_box(frame):
    selectors = [
        "#nc_1_wrapper",
        ".nc_wrapper",
        ".nc_scale",
        "#nocaptcha",
    ]
    for selector in selectors:
        locator = frame.locator(selector).first
        try:
            if await locator.count() and await locator.is_visible():
                return locator
        except Exception:
            continue
    return None


async def _click_slider_frame(locator) -> None:
    handle = await locator.element_handle()
    if handle is None:
        return
    rect = await handle.evaluate(
        """
        (node) => {
          let current = node;
          while (current) {
            const r = current.getBoundingClientRect();
            if (r.width >= 180 && r.height >= 24) {
              return {x: r.x, y: r.y, width: r.width, height: r.height};
            }
            current = current.parentElement;
          }
          const r = node.getBoundingClientRect();
          return {x: r.x, y: r.y, width: r.width, height: r.height};
        }
        """
    )
    if not rect or rect["width"] <= 0 or rect["height"] <= 0:
        return
    x = rect["x"] + rect["width"] / 2
    y = rect["y"] + rect["height"] / 2
    await locator.page.mouse.click(x, y)


async def _slider_verification_passed(page) -> bool:
    if await _slider_still_present(page):
        return False
    try:
        title = await page.title()
    except Exception:
        return False
    return "验证码拦截" not in title


async def _read_slider_hidden_state(page) -> dict[str, str]:
    state: dict[str, str] = {}
    field_ids = ["nc-session-id", "nc-sig", "x5step", "x5secdata", "ajax", "nc_app_key"]
    for frame in list(page.frames):
        for field_id in field_ids:
            try:
                value = await frame.locator(f"#{field_id}").input_value(timeout=300)
                state[field_id] = value
            except Exception:
                continue
        if state:
            break
    return state


async def _read_slider_visual_state(page) -> dict[str, dict[str, str]]:
    selectors = {
        "wrapper": "#nc_1_wrapper",
        "track": "#nc_1_n1t",
        "handle": "#nc_1_n1z",
        "bg": "#nc_1__bg",
        "text": "#nc_1__scale_text",
        "error": ".errloading",
    }
    snapshot: dict[str, dict[str, str]] = {}
    for frame in list(page.frames):
        frame_snapshot: dict[str, dict[str, str]] = {}
        for key, selector in selectors.items():
            locator = frame.locator(selector).first
            if not await locator.count():
                continue
            try:
                state = await locator.evaluate(
                    """
                    (node) => ({
                      className: node.className || '',
                      style: node.getAttribute('style') || '',
                      text: (node.innerText || node.textContent || '').trim().slice(0, 120),
                    })
                    """
                )
                frame_snapshot[key] = state
            except Exception:
                continue
        if frame_snapshot:
            return frame_snapshot
    return snapshot


async def _slider_still_present(page) -> bool:
    for frame in list(page.frames):
        try:
            locator = frame.locator(".errloading, .nc_scale, .btn_slide, .nc_1_n1z, #nc_1_wrapper").first
            if await locator.count() and await locator.is_visible():
                return True
        except Exception:
            continue
    return False


async def _search_input_locator(page):
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


async def _search_button_locator(page):
    selectors = [
        "form#alisearch-from .input-button",
        ".input-button",
        "button[type='submit']",
        "button:has-text('搜索')",
        "[role='button']:has-text('搜索')",
    ]
    for selector in selectors:
        locator = page.locator(selector).first
        try:
            if await locator.count():
                return locator
        except Exception:
            continue
    return None


async def _page_ready_for_direct_search(page) -> bool:
    try:
        if "1688.com" not in page.url:
            return False
        if await _slider_still_present(page):
            return False
        locator = await _search_input_locator(page)
        return locator is not None
    except Exception:
        return False


async def _subject_region_locators(page):
    selectors = [
        "div[class*='cropRegion--']",
        "div[class*='selectRegion--']",
    ]
    for selector in selectors:
        locator = page.locator(selector)
        try:
            if await locator.count():
                return locator
        except Exception:
            continue
    return None


async def _visible_subject_region_locators(page):
    locator = await _subject_region_locators(page)
    if locator is None:
        return []
    visible = []
    total = await locator.count()
    for index in range(total):
        candidate = locator.nth(index)
        try:
            if await candidate.is_visible():
                visible.append(candidate)
        except Exception:
            continue
    return visible


async def _count_subject_regions(page) -> int:
    return len(await _visible_subject_region_locators(page))


async def _select_subject_region(page, subject_index: int) -> dict[str, object]:
    visible_locators = await _visible_subject_region_locators(page)
    subject_count = len(visible_locators)
    if subject_count <= 0:
        return {"subject_count": 0, "selected_subject_index": 0, "subject_switched": False}
    selected_index = max(0, min(subject_index, subject_count - 1))
    if selected_index > 0:
        target = visible_locators[selected_index]
        await target.scroll_into_view_if_needed()
        await asyncio.sleep(0.5)
        await target.click(timeout=8000)
        await asyncio.sleep(5)
    return {
        "subject_count": subject_count,
        "selected_subject_index": selected_index,
        "subject_switched": selected_index > 0,
    }


async def _select_subject_region_by_index(page, subject_index: int) -> bool:
    visible_locators = await _visible_subject_region_locators(page)
    if not visible_locators:
        return False
    selected_index = max(0, min(subject_index, len(visible_locators) - 1))
    if selected_index == 0:
        return True
    target = visible_locators[selected_index]
    await target.scroll_into_view_if_needed()
    await asyncio.sleep(0.4)
    await target.click(timeout=8000)
    await asyncio.sleep(5)
    return True


def _looks_like_login_url(url: str) -> bool:
    lowered = url.lower()
    return any(token in lowered for token in ["login.taobao.com", "login.1688.com", "member/modify_evolve"])


async def _wait_for_search_or_slider(page, timeout_seconds: float = 8.0) -> str:
    deadline = asyncio.get_running_loop().time() + timeout_seconds
    while asyncio.get_running_loop().time() < deadline:
        if _looks_like_login_url(page.url):
            return "login"
        if await _slider_still_present(page):
            return "slider"
        if await _search_input_locator(page) is not None:
            return "search"
        await asyncio.sleep(0.2)
    return "unknown"


async def _clear_home_slider(page, output_dir: Path | None = None, stage: str = "home", round_index: int | None = None) -> bool:
    for attempt in range(1, 4):
        try:
            frames = list(page.frames)
        except Exception:
            return False
        for frame in frames:
            frame_box = await _find_slider_frame_box(frame)
            slider = await _find_slider_control(frame)
            if frame_box is None and slider is None:
                continue
            try:
                if slider is None and frame_box is not None:
                    await _click_slider_frame(frame_box)
                    print(
                        json.dumps(
                            {"step": "slider_retry_click", "attempt": attempt, "frame_url": frame.url},
                            ensure_ascii=False,
                        ),
                        flush=True,
                    )
                    await asyncio.sleep(0.4)
                    slider = await _find_slider_control(frame)
                if slider is None:
                    continue
                slider_identity = await slider.evaluate("node => node.className || node.id || node.tagName")
                geometry = await _read_slider_geometry(slider, frame, page)
                if geometry is not None:
                    handle_x = geometry["geometry"]["handle"]["x"]
                    track_x = geometry["geometry"]["track"]["x"]
                    if handle_x - track_x > 40 and frame_box is not None:
                        await _click_slider_frame(frame_box)
                        print(
                            json.dumps(
                                {
                                    "step": "slider_pre_reset",
                                    "attempt": attempt,
                                    "frame_url": frame.url,
                                    "handle_x": handle_x,
                                    "track_x": track_x,
                                },
                                ensure_ascii=False,
                            ),
                            flush=True,
                        )
                        await asyncio.sleep(0.5)
                        slider = await _find_slider_control(frame)
                        if slider is None:
                            continue
                        slider_identity = await slider.evaluate("node => node.className || node.id || node.tagName")
                        geometry = await _read_slider_geometry(slider, frame, page)
                if output_dir is not None:
                    dump_prefix = f"{stage}_round{round_index or 0}_attempt{attempt}"
                    await _dump_page(page, output_dir, f"{dump_prefix}_before_drag")
                    if geometry is not None:
                        await _dump_json(
                            output_dir,
                            f"{dump_prefix}_geometry",
                            {
                                "stage": stage,
                                "round": round_index,
                                "attempt": attempt,
                                "frame_url": frame.url,
                                "selector": slider_identity,
                                **geometry,
                            },
                        )
                if await _drag_slider_system_mouse(page, frame, slider):
                    print(
                        json.dumps(
                            {
                                "step": "slider_dragged",
                                "attempt": attempt,
                                "mode": "system_mouse",
                                "selector": slider_identity,
                                "frame_url": frame.url,
                            },
                            ensure_ascii=False,
                        ),
                        flush=True,
                    )
                    await asyncio.sleep(0.8)
                    hidden_state = await _read_slider_hidden_state(page)
                    visual_state = await _read_slider_visual_state(page)
                    print(
                        json.dumps(
                            {"step": "slider_hidden_state", "attempt": attempt, "state": hidden_state},
                            ensure_ascii=False,
                        ),
                        flush=True,
                    )
                    print(
                        json.dumps(
                            {"step": "slider_visual_state", "attempt": attempt, "state": visual_state},
                            ensure_ascii=False,
                        ),
                        flush=True,
                    )
                    passed = await _slider_verification_passed(page)
                    print(
                        json.dumps(
                            {"step": "slider_verify", "attempt": attempt, "passed": passed},
                            ensure_ascii=False,
                        ),
                        flush=True,
                    )
                    if passed:
                        return True
                    if frame_box is not None:
                        await _click_slider_frame(frame_box)
                        print(
                            json.dumps(
                                {"step": "slider_retry_click", "attempt": attempt, "frame_url": frame.url},
                                ensure_ascii=False,
                            ),
                            flush=True,
                        )
                        await asyncio.sleep(0.4)
            except Exception as exc:
                print(
                    json.dumps(
                        {
                            "step": "slider_drag_error",
                            "attempt": attempt,
                            "frame_url": frame.url,
                            "error": f"{type(exc).__name__}: {exc}",
                        },
                        ensure_ascii=False,
                    ),
                    flush=True,
                )
        await asyncio.sleep(0.8)
    return False


async def _clear_slider_if_present(page, stage: str) -> bool:
    state = await _wait_for_search_or_slider(page)
    print(json.dumps({"step": "slider_stage_state", "stage": stage, "state": state}, ensure_ascii=False), flush=True)
    if state == "search":
        print(json.dumps({"step": "slider_not_present", "stage": stage}, ensure_ascii=False), flush=True)
        return True
    if state == "login":
        print(json.dumps({"step": "login_redirect_detected", "stage": stage, "url": page.url}, ensure_ascii=False), flush=True)
        return False
    passed = await _clear_home_slider(page)
    print(json.dumps({"step": "slider_stage_ready", "stage": stage, "passed": passed}, ensure_ascii=False), flush=True)
    return passed


async def _stabilize_home_until_search_ready(page, output_dir: Path, stage: str, max_rounds: int = 6) -> bool:
    for round_index in range(1, max_rounds + 1):
        state = await _wait_for_search_or_slider(page)
        print(
            json.dumps(
                {"step": "home_stage_state", "stage": stage, "round": round_index, "state": state},
                ensure_ascii=False,
            ),
            flush=True,
        )
        if state == "search":
            return True
        if state != "slider":
            await asyncio.sleep(0.5)
            continue
        passed = await _clear_home_slider(page, output_dir=output_dir, stage=stage, round_index=round_index)
        print(
            json.dumps(
                {"step": "home_slider_round", "stage": stage, "round": round_index, "passed": passed},
                ensure_ascii=False,
            ),
            flush=True,
        )
        if not passed and round_index in {2, 4}:
            print(
                json.dumps(
                    {"step": "home_reload_after_failed_rounds", "stage": stage, "round": round_index},
                    ensure_ascii=False,
                ),
                flush=True,
            )
            await page.reload(wait_until="domcontentloaded", timeout=30000)
        await asyncio.sleep(0.8)
    return await _search_input_locator(page) is not None


async def _set_search_keyword(page, search_input, keyword: str) -> None:
    await search_input.click(timeout=5000)
    await search_input.press("Meta+A")
    await search_input.press("Backspace")
    await search_input.press_sequentially(keyword, delay=12)
    await asyncio.sleep(0.3)
    actual_value = await search_input.input_value()
    if actual_value != keyword:
        raise RuntimeError(f"Search input value mismatch: expected={keyword!r}, actual={actual_value!r}")


async def _read_main_search_button_text(page) -> str:
    button = await _search_button_locator(page)
    if button is None:
        return ""


async def _ensure_ali1688_filter(page, text: str, url_token: str, dump_name: str, output_dir: Path) -> None:
    if url_token and url_token in page.url:
        await _dump_page(page, output_dir, dump_name)
        return
    locator = page.locator(f"text={text}").first
    if await locator.count():
        await locator.scroll_into_view_if_needed()
        await asyncio.sleep(1)
        await locator.click(timeout=8000)
        await asyncio.sleep(6)
        if not await _clear_slider_if_present(page, dump_name):
            raise RuntimeError(f"slider_blocking_after_filter:{text}")
        await _dump_page(page, output_dir, dump_name)
        return
    print(json.dumps({"step": "filter_not_found", "filter": text}, ensure_ascii=False), flush=True)


async def _capture_all_subject_runs(page, output_dir: Path, summary: dict[str, object], *, max_subjects: int | None = None) -> None:
    subject_count = await _count_subject_regions(page)
    summary["subject_count"] = subject_count
    subject_runs: list[dict[str, object]] = []
    if subject_count <= 0:
        summary["subject_runs"] = subject_runs
        return

    limit = subject_count if max_subjects is None else max(0, min(subject_count, max_subjects))
    for subject_index in range(limit):
        if not await _select_subject_region_by_index(page, subject_index):
            continue
        await _dump_page(page, output_dir, f"04_subject_{subject_index}")
        await _ensure_ali1688_filter(page, "退货包运费", "complexTags=1001", f"06_subject_{subject_index}_return_shipping", output_dir)
        await _ensure_ali1688_filter(page, "一件代发", "offerTags=1988226", f"07_subject_{subject_index}_dropship", output_dir)
        await _ensure_ali1688_filter(page, "1件代发包邮", "", f"08_subject_{subject_index}_dropship_free_shipping", output_dir)
        subject_runs.append(
            {
                "subject_index": subject_index,
                "final_url": page.url,
                "html_path": str((output_dir / f"08_subject_{subject_index}_dropship_free_shipping.html").resolve()),
            }
        )
    summary["subject_runs"] = subject_runs


async def _run_flow_on_page(
    *,
    context,
    page,
    keyword: str,
    image_url: str | None,
    output_dir: Path,
    summary: dict[str, object],
    summary_json_file: str | None,
    pause_for_login_seconds: float,
    subject_index: int,
    capture_all_subjects: bool,
    max_subjects: int | None,
    keep_open_seconds: float,
) -> object:
    if await _page_ready_for_direct_search(page):
        print(json.dumps({"step": "reuse_current_page_for_search", "url": page.url}, ensure_ascii=False), flush=True)
        await _dump_page(page, output_dir, "01_reuse_current_page")
    else:
        print(json.dumps({"step": "open_home"}, ensure_ascii=False), flush=True)
        await page.goto("https://www.1688.com/", wait_until="domcontentloaded", timeout=30000)
        slider_cleared = await _stabilize_home_until_search_ready(page, output_dir, "home")
        print(json.dumps({"step": "slider_ready", "passed": slider_cleared}, ensure_ascii=False), flush=True)
        await _dump_page(page, output_dir, "01_home")

        if pause_for_login_seconds > 0:
            print(
                json.dumps(
                    {"step": "pause_for_login", "seconds": pause_for_login_seconds},
                    ensure_ascii=False,
                ),
                flush=True,
            )
            await asyncio.sleep(pause_for_login_seconds)
            slider_cleared = await _stabilize_home_until_search_ready(page, output_dir, "after_login_pause")
            print(json.dumps({"step": "slider_ready_after_pause", "passed": slider_cleared}, ensure_ascii=False), flush=True)
            await _dump_page(page, output_dir, "01_after_login_pause")

        if await _slider_still_present(page):
            summary["status"] = "slider_blocking_home"
            summary["final_url"] = page.url
            _write_summary(summary_json_file, summary)
            print(json.dumps({"step": "slider_blocking_home"}, ensure_ascii=False), flush=True)
            return page

    search_term = image_url or keyword
    fill_step = "fill_image_url" if image_url else "fill_keyword"
    max_submit_attempts = 2 if image_url else 1
    for submit_attempt in range(1, max_submit_attempts + 1):
        print(
            json.dumps({"step": fill_step, "value": search_term, "submit_attempt": submit_attempt}, ensure_ascii=False),
            flush=True,
        )
        search_input = await _search_input_locator(page)
        if search_input is None:
            await _dump_page(page, output_dir, "01_search_input_not_found")
            raise RuntimeError("Search input not found after homepage became ready")
        await _set_search_keyword(page, search_input, search_term)
        await asyncio.sleep(2)
        await _dump_page(page, output_dir, "02_search_input_filled")

        if image_url:
            main_button_text = await _read_main_search_button_text(page)
            print(
                json.dumps(
                    {"step": "image_search_submit", "main_button_text": main_button_text, "submit_attempt": submit_attempt},
                    ensure_ascii=False,
                ),
                flush=True,
            )
            search_button = await _search_button_locator(page)
            if search_button is not None:
                await search_button.scroll_into_view_if_needed()
                await asyncio.sleep(0.2)
                await search_button.click(timeout=10000)
            else:
                await search_input.press("Enter")
        else:
            print(json.dumps({"step": "press_enter"}, ensure_ascii=False), flush=True)
            await search_input.press("Enter")
        await asyncio.sleep(8)
        page = await _switch_to_latest_page(context, page, output_dir, "03_after_enter")
        if await _clear_slider_if_present(page, "after_enter"):
            break
        await _dump_page(page, output_dir, "03_after_enter_slider_blocked")
        if "login.taobao.com" in (page.url or "") and submit_attempt < max_submit_attempts:
            print(
                json.dumps(
                    {"step": "retry_after_login_redirect", "submit_attempt": submit_attempt, "url": page.url},
                    ensure_ascii=False,
                ),
                flush=True,
            )
            page = await _recover_to_ali1688_search_page(context, page)
            slider_cleared = await _stabilize_home_until_search_ready(page, output_dir, f"retry_{submit_attempt}")
            print(
                json.dumps(
                    {"step": "retry_home_ready", "submit_attempt": submit_attempt, "passed": slider_cleared},
                    ensure_ascii=False,
                ),
                flush=True,
            )
            continue
        summary["status"] = "slider_blocking_after_enter"
        summary["final_url"] = page.url
        _write_summary(summary_json_file, summary)
        print(json.dumps({"step": "slider_blocking_after_enter"}, ensure_ascii=False), flush=True)
        return page

    subject_state = await _select_subject_region(page, max(subject_index, 0))
    summary["subject_count"] = int(subject_state.get("subject_count") or 0)
    summary["selected_subject_index"] = int(subject_state.get("selected_subject_index") or 0)
    print(json.dumps({"step": "subject_state", **subject_state}, ensure_ascii=False), flush=True)
    if subject_state.get("subject_switched"):
        await _dump_page(page, output_dir, "04_after_subject_switch")

    if capture_all_subjects:
        await _capture_all_subject_runs(page, output_dir, summary, max_subjects=max_subjects)
        summary["ok"] = True
        summary["status"] = "completed"
        summary["final_url"] = page.url
        _write_summary(summary_json_file, summary)
        print(json.dumps({"step": "final", "url": page.url}, ensure_ascii=False), flush=True)
        if keep_open_seconds > 0:
            await asyncio.sleep(keep_open_seconds)
        return page

    print(json.dumps({"step": "try_filters"}, ensure_ascii=False), flush=True)
    for text, name in (("退货包运费", "06_filter_return_shipping"), ("一件代发", "07_filter_dropship")):
        locator = page.locator(f"text={text}").first
        if await locator.count():
            try:
                await locator.scroll_into_view_if_needed()
                await asyncio.sleep(1)
                await locator.click(timeout=8000)
                await asyncio.sleep(6)
                if not await _clear_slider_if_present(page, name):
                    await _dump_page(page, output_dir, f"{name}_slider_blocked")
                    summary["status"] = f"slider_blocking_after_filter:{text}"
                    summary["final_url"] = page.url
                    _write_summary(summary_json_file, summary)
                    print(
                        json.dumps(
                            {"step": "slider_blocking_after_filter", "filter": text},
                            ensure_ascii=False,
                        ),
                        flush=True,
                    )
                    return page
                await _dump_page(page, output_dir, name)
            except Exception as exc:
                print(
                    json.dumps(
                        {"step": "filter_click_error", "filter": text, "error": f"{type(exc).__name__}: {exc}"},
                        ensure_ascii=False,
                    ),
                    flush=True,
                )
                await _dump_page(page, output_dir, f"{name}_error")
        else:
            print(json.dumps({"step": "filter_not_found", "filter": text}, ensure_ascii=False), flush=True)

    for text, name in (("1件代发包邮", "08_filter_dropship_free_shipping"),):
        locator = page.locator(f"text={text}").first
        if await locator.count():
            try:
                await locator.scroll_into_view_if_needed()
                await asyncio.sleep(1)
                await locator.click(timeout=8000)
                await asyncio.sleep(6)
                if not await _clear_slider_if_present(page, name):
                    await _dump_page(page, output_dir, f"{name}_slider_blocked")
                    summary["status"] = f"slider_blocking_after_filter:{text}"
                    summary["final_url"] = page.url
                    _write_summary(summary_json_file, summary)
                    print(
                        json.dumps(
                            {"step": "slider_blocking_after_filter", "filter": text},
                            ensure_ascii=False,
                        ),
                        flush=True,
                    )
                    return page
                await _dump_page(page, output_dir, name)
            except Exception as exc:
                print(
                    json.dumps(
                        {"step": "filter_click_error", "filter": text, "error": f"{type(exc).__name__}: {exc}"},
                        ensure_ascii=False,
                    ),
                    flush=True,
                )
                await _dump_page(page, output_dir, f"{name}_error")
        else:
            print(json.dumps({"step": "filter_not_found", "filter": text}, ensure_ascii=False), flush=True)

    summary["ok"] = True
    summary["status"] = "completed"
    summary["final_url"] = page.url
    _write_summary(summary_json_file, summary)
    print(json.dumps({"step": "final", "url": page.url}, ensure_ascii=False), flush=True)
    if keep_open_seconds > 0:
        await asyncio.sleep(keep_open_seconds)
    return page


async def _run(args) -> None:
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    launch_args = [*default_launch_args(), *args.launch_arg]
    summary: dict[str, object] = {
        "ok": False,
        "status": "starting",
        "keyword": args.keyword,
        "image_url": args.image_url,
        "final_url": "",
        "output_dir": str(output_dir.resolve()),
        "user_data_dir": args.user_data_dir,
        "profile_directory": args.profile_directory,
        "subject_count": 0,
        "selected_subject_index": max(args.subject_index, 0),
        "subject_runs": [],
    }

    async with async_playwright() as playwright:
        if args.user_data_dir:
            persistent_args = list(launch_args)
            if args.profile_directory:
                persistent_args.append(f"--profile-directory={args.profile_directory}")
            context = await playwright.chromium.launch_persistent_context(
                args.user_data_dir,
                channel=args.browser_channel,
                headless=False,
                slow_mo=args.slow_mo_ms,
                args=persistent_args,
                **default_desktop_context_options(),
            )
            owns_browser = False
        else:
            browser = await playwright.chromium.launch(
                channel=args.browser_channel,
                headless=False,
                slow_mo=args.slow_mo_ms,
                args=launch_args,
            )
            context = await browser.new_context(**default_desktop_context_options())
            owns_browser = True

        try:
            page = context.pages[0] if context.pages else await context.new_page()
            await _run_flow_on_page(
                context=context,
                page=page,
                keyword=args.keyword,
                image_url=args.image_url,
                output_dir=output_dir,
                summary=summary,
                summary_json_file=args.summary_json_file,
                pause_for_login_seconds=args.pause_for_login_seconds,
                subject_index=args.subject_index,
                capture_all_subjects=args.capture_all_subjects,
                max_subjects=args.max_subjects,
                keep_open_seconds=args.keep_open_seconds,
            )
        finally:
            if summary["status"] == "starting":
                summary["status"] = "aborted"
                _write_summary(args.summary_json_file, summary)
            await context.close()
            if owns_browser:
                await browser.close()


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run a slow, observable ali1688 browser flow with optional persistent profile reuse."
    )
    parser.add_argument("--keyword", default="升降桌")
    parser.add_argument("--image-url", help="Optional image URL for 1688 image search. When provided, prefer image search over text search.")
    parser.add_argument("--browser-channel", default="chrome")
    parser.add_argument(
        "--user-data-dir",
        default=DEFAULT_ALI1688_USER_DATA_DIR,
        help="Chrome user data dir for a persistent ali1688 session. Defaults to a dedicated project profile.",
    )
    parser.add_argument("--profile-directory", help="Chrome profile directory inside the user data dir, e.g. Default.")
    parser.add_argument("--pause-for-login-seconds", type=float, default=0.0)
    parser.add_argument("--slow-mo-ms", type=int, default=0)
    parser.add_argument("--keep-open-seconds", type=float, default=120.0)
    parser.add_argument("--output-dir", default="./tmp/ali1688_slow_flow")
    parser.add_argument("--summary-json-file", help="Optional path to write a machine-readable run summary.")
    parser.add_argument("--subject-index", type=int, default=0, help="Which visible image-search subject region to use. 0 keeps the default subject.")
    parser.add_argument(
        "--capture-all-subjects",
        action="store_true",
        help="After entering the image-search result page, iterate all visible subject regions in the same page and dump each filtered result page.",
    )
    parser.add_argument("--max-subjects", type=int, default=3, help="Maximum number of image-search subjects to process when capture-all-subjects is enabled.")
    parser.add_argument(
        "--launch-arg",
        action="append",
        default=[],
        help="Extra browser launch arg. Repeatable, e.g. --launch-arg=--start-maximized",
    )
    args = parser.parse_args()
    print(
        json.dumps(
            {
                "step": "session_profile",
                "user_data_dir": args.user_data_dir,
                "profile_directory": args.profile_directory,
            },
            ensure_ascii=False,
        ),
        flush=True,
    )
    asyncio.run(_run(args))
    return 0


if __name__ == "__main__":
    sys.exit(main())
