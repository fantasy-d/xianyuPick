from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from xianyu_tools.xianyu_adapter.browser_transport import PlaywrightBrowserTransport, PlaywrightBrowserConfig


def inspect_state_file(path: str | Path) -> dict[str, Any]:
    state_path = Path(path)
    if not state_path.exists():
        return {
            "path": str(state_path),
            "exists": False,
            "is_playwright_storage_state": False,
            "cookie_count": 0,
            "origin_count": 0,
            "has_headers": False,
            "has_env": False,
            "context_overrides": {},
            "header_keys": [],
            "is_usable": False,
            "issues": ["state_file_missing"],
        }
    transport = PlaywrightBrowserTransport(config=PlaywrightBrowserConfig(state_file=str(state_path)))
    payload = transport._load_json(state_path)
    storage_state = transport._extract_storage_state(payload)
    overrides = transport._build_context_overrides(payload)
    headers = transport._build_extra_headers(payload.get("headers"))
    issues: list[str] = []
    cookie_count = len(storage_state["cookies"]) if storage_state else 0
    origin_count = len(storage_state["origins"]) if storage_state else 0
    has_env = isinstance(payload.get("env"), dict)
    has_headers = bool(headers)
    if cookie_count == 0:
        issues.append("missing_cookies")
    if not has_env:
        issues.append("missing_env")
    if not has_headers:
        issues.append("missing_headers")
    return {
        "path": str(state_path),
        "exists": True,
        "is_playwright_storage_state": transport._is_playwright_storage_state(payload),
        "cookie_count": cookie_count,
        "origin_count": origin_count,
        "has_headers": has_headers,
        "has_env": has_env,
        "context_overrides": overrides,
        "header_keys": sorted(headers.keys()),
        "is_usable": cookie_count > 0,
        "issues": issues,
    }


def inspect_state_file_json(path: str | Path) -> str:
    return json.dumps(inspect_state_file(path), ensure_ascii=False, indent=2)
