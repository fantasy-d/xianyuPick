from __future__ import annotations

import asyncio
import re
from dataclasses import dataclass, field
from typing import Any
from urllib.parse import unquote

from xianyu_tools.xianyu_adapter.browser_transport import default_desktop_context_options, default_launch_args


@dataclass(slots=True)
class Ali1688SessionConfig:
    user_data_dir: str
    browser_channel: str = "chrome"
    profile_directory: str | None = None
    launch_args: list[str] = field(default_factory=list)
    slow_mo_ms: int = 0
    headless: bool = True


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


def looks_like_authenticated_member_page(url: str, title: str | None = None) -> bool:
    lowered_url = (url or "").lower()
    lowered_title = (title or "").lower()
    if looks_like_login_url(lowered_url):
        return False
    if "member.1688.com/member/" not in lowered_url:
        return False
    if any(token in lowered_title for token in ["会员管理", "我的阿里", "阿里巴巴"]):
        return True
    return lowered_url.endswith("/member/myalibaba.htm")


def looks_like_navigation_timeout(error: Any) -> bool:
    message = str(error or "")
    lowered = message.lower()
    return "timeout" in lowered and "goto" in lowered


GENERIC_ACCOUNT_TEXTS = {
    "商家工作台",
    "我的阿里",
    "阿里首页",
    "会员管理",
    "尊贵的1688买家",
    "发布询价单",
    "我的进货单",
    "立即登录",
    "重新登录",
    "检测状态",
}

GENERIC_ACCOUNT_PATTERNS = [
    r"^发布.+单$",
    r"^我的.+单$",
    r"^去.+$",
    r"^立即.+$",
    r"^重新.+$",
    r"^账号[名信息：:\s].*$",
]


def normalize_account_name(raw_value: Any) -> str:
    text = str(raw_value or "").strip()
    if not text:
        return ""
    text = unquote(text)
    text = re.sub(r"\s+", " ", text).strip()
    text = text.strip("，,。:：;；|/\\")
    return text


def looks_like_real_account_name(raw_value: Any) -> bool:
    text = normalize_account_name(raw_value)
    if not text:
        return False
    lowered = text.lower()
    if lowered in {"true", "false", "null", "undefined", "nouserid"}:
        return False
    if text in GENERIC_ACCOUNT_TEXTS:
        return False
    if "尊贵的1688买家" in text:
        return False
    for pattern in GENERIC_ACCOUNT_PATTERNS:
        if re.fullmatch(pattern, text):
            return False
    if len(text) <= 1:
        return False
    if len(text) > 64:
        return False
    if re.fullmatch(r"[0-9\-_:]+", text):
        return False
    return True


async def extract_ali1688_account_name(page, context) -> dict[str, Any]:
    runtime_cookies = {}
    try:
        for item in await context.cookies(page.url):
            name = str(item.get("name") or "")
            if name in {"__cn_logon_id__", "tracknick", "_w_tb_nick", "loginId", "cn", "lgc", "_nk_"}:
                runtime_cookies[name] = item.get("value") or ""
    except Exception:
        runtime_cookies = {}

    page_snapshot = await page.evaluate(
        """() => {
            const selectors = [
              '[data-testid*="nick"]',
              '[class*="nick"]',
              '[class*="account"]',
              '[class*="member"]',
              '[class*="user-name"]',
              '[class*="userName"]',
              '[class*="company-name"]',
              'a[href*="work.1688.com"]',
              'a[href*="myalibaba"]',
              'a[href*="member.1688.com"]',
              '.company-name',
              '.member-nick',
              '.account-name',
            ];
            const selectorHits = [];
            for (const selector of selectors) {
              const nodes = Array.from(document.querySelectorAll(selector)).slice(0, 12);
              for (const node of nodes) {
                const text = (node.textContent || '').replace(/\\s+/g, ' ').trim();
                if (text) selectorHits.push({ selector, text });
              }
            }

            const cookieMap = {};
            for (const pair of (document.cookie || '').split(/;\\s*/)) {
              if (!pair) continue;
              const [rawKey, ...rest] = pair.split('=');
              const key = (rawKey || '').trim();
              if (!key) continue;
              cookieMap[key] = rest.join('=');
            }

            const runtimeCandidates = [];
            const knownPairs = [
              ['__INIT_DATA__', window.__INIT_DATA__],
              ['__PRELOADED_STATE__', window.__PRELOADED_STATE__],
              ['__NUXT__', window.__NUXT__],
              ['userInfo', window.userInfo],
              ['memberInfo', window.memberInfo],
              ['__GLOBAL_DATA__', window.__GLOBAL_DATA__],
            ];

            const pushCandidate = (source, value) => {
              const text = (value ?? '').toString().replace(/\\s+/g, ' ').trim();
              if (text) runtimeCandidates.push({ source, text });
            };

            for (const [rootName, rootValue] of knownPairs) {
              if (!rootValue || typeof rootValue !== 'object') continue;
              const queue = [{ path: rootName, value: rootValue, depth: 0 }];
              const seen = new WeakSet();
              while (queue.length) {
                const current = queue.shift();
                if (!current || !current.value || typeof current.value !== 'object') continue;
                if (seen.has(current.value)) continue;
                seen.add(current.value);
                for (const [key, value] of Object.entries(current.value).slice(0, 60)) {
                  const nextPath = `${current.path}.${key}`;
                  const lowered = key.toLowerCase();
                  if (typeof value === 'string' && /(nick|name|member|loginid|login_id|account)/i.test(lowered)) {
                    pushCandidate(nextPath, value);
                  } else if (value && typeof value === 'object' && current.depth < 2) {
                    queue.push({ path: nextPath, value, depth: current.depth + 1 });
                  }
                }
              }
            }

            return {
              selectorHits,
              runtimeCandidates,
              runtimeCookies: cookieMap,
            };
        }"""
    )

    candidates: list[tuple[str, str, float]] = []
    for hit in page_snapshot.get("selectorHits") or []:
        text = normalize_account_name(hit.get("text"))
        if looks_like_real_account_name(text):
            score = 0.98 if "nick" in (hit.get("selector") or "") or "account" in (hit.get("selector") or "") else 0.92
            candidates.append((text, f"dom:{hit.get('selector')}", score))

    for item in page_snapshot.get("runtimeCandidates") or []:
        text = normalize_account_name(item.get("text"))
        if looks_like_real_account_name(text):
            candidates.append((text, f"runtime:{item.get('source')}", 0.88))

    merged_cookie_map = dict(page_snapshot.get("runtimeCookies") or {})
    merged_cookie_map.update({k: v for k, v in runtime_cookies.items() if v})
    for cookie_name in ("__cn_logon_id__", "tracknick", "_w_tb_nick", "loginId", "cn", "lgc", "_nk_"):
        text = normalize_account_name(merged_cookie_map.get(cookie_name))
        if looks_like_real_account_name(text):
            score = 0.995 if cookie_name == "__cn_logon_id__" else 0.96
            candidates.append((text, f"runtime_cookie:{cookie_name}", score))

    if not candidates:
        return {
            "account_name": "",
            "source": "",
            "confidence": 0.0,
            "debug_meta": {
                "selector_hit_count": len(page_snapshot.get("selectorHits") or []),
                "runtime_candidate_count": len(page_snapshot.get("runtimeCandidates") or []),
                "runtime_cookie_keys": sorted([k for k, v in merged_cookie_map.items() if v]),
            },
        }

    deduped: list[tuple[str, str, float]] = []
    seen_names = set()
    for name, source, confidence in sorted(candidates, key=lambda item: item[2], reverse=True):
        if name in seen_names:
            continue
        seen_names.add(name)
        deduped.append((name, source, confidence))

    account_name, source, confidence = deduped[0]
    return {
        "account_name": account_name,
        "source": source,
        "confidence": confidence,
        "debug_meta": {
            "top_candidates": [
                {"account_name": item[0], "source": item[1], "confidence": item[2]}
                for item in deduped[:5]
            ],
            "runtime_cookie_keys": sorted([k for k, v in merged_cookie_map.items() if v]),
        },
    }


async def inspect_ali1688_session(config: Ali1688SessionConfig) -> dict[str, Any]:
    from playwright.async_api import TimeoutError as PlaywrightTimeoutError, async_playwright
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
                headless=config.headless,
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
            visited_pages: list[dict[str, str]] = []
            navigation_warnings: list[dict[str, str]] = []
            account_name_result = {
                "account_name": "",
                "source": "",
                "confidence": 0.0,
                "debug_meta": {},
            }
            state = "unknown"
            title = ""

            for target_url in (
                "https://www.1688.com/",
                "https://member.1688.com/member/myalibaba.htm",
            ):
                navigation_timed_out = False
                navigation_error_message = ""
                try:
                    await page.goto(target_url, wait_until="commit", timeout=12000)
                    try:
                        await page.wait_for_load_state("domcontentloaded", timeout=6000)
                    except PlaywrightTimeoutError as exc:
                        navigation_timed_out = True
                        navigation_error_message = str(exc)
                except PlaywrightTimeoutError as exc:
                    navigation_timed_out = True
                    navigation_error_message = str(exc)
                except PlaywrightError as exc:
                    navigation_error_message = str(exc)
                    if looks_like_navigation_timeout(exc):
                        navigation_timed_out = True
                    else:
                        navigation_warnings.append(
                            {
                                "requested_url": target_url,
                                "error": navigation_error_message,
                            }
                        )
                        continue

                if navigation_error_message:
                    navigation_warnings.append(
                        {
                            "requested_url": target_url,
                            "error": navigation_error_message,
                        }
                    )

                current_state = await wait_for_search_or_slider(
                    page,
                    timeout_seconds=4.0 if navigation_timed_out else 8.0,
                )
                try:
                    current_title = await page.title()
                except Exception:
                    current_title = ""
                candidate = None
                if current_state in {"search", "unknown"}:
                    try:
                        candidate = await extract_ali1688_account_name(page, context)
                    except Exception as exc:
                        account_name_result["debug_meta"] = {
                            **dict(account_name_result.get("debug_meta") or {}),
                            "extract_error": str(exc),
                        }
                if current_state == "unknown" and (
                    (candidate and candidate.get("account_name"))
                    or looks_like_authenticated_member_page(page.url, current_title)
                ):
                    current_state = "member"
                visited_pages.append(
                    {
                        "requested_url": target_url,
                        "url": page.url,
                        "title": current_title,
                        "state": current_state,
                        "navigation_timed_out": "true" if navigation_timed_out else "false",
                    }
                )
                state = current_state
                title = current_title
                if current_state in {"search", "member"}:
                    if candidate and candidate.get("account_name"):
                        account_name_result = candidate
                    break
                elif current_state in {"login", "slider"}:
                    break

            if state == "unknown" and navigation_warnings and all(
                looks_like_navigation_timeout(item.get("error")) for item in navigation_warnings
            ):
                state = "timeout"
            return {
                "state": state,
                "url": page.url,
                "title": title,
                "user_data_dir": config.user_data_dir,
                "profile_directory": config.profile_directory,
                "account_name": account_name_result.get("account_name") or "",
                "account_name_source": account_name_result.get("source") or "",
                "account_name_confidence": account_name_result.get("confidence") or 0.0,
                "account_name_debug": account_name_result.get("debug_meta") or {},
                "visited_pages": visited_pages,
                "navigation_warnings": navigation_warnings,
                "error": (
                    "1688 页面访问超时，已尝试回退检测但未识别到可用登录态。"
                    if state == "timeout"
                    else ""
                ),
            }
        finally:
            await context.close()
