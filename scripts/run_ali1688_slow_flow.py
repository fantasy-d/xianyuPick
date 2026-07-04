#!/usr/bin/env python3
import argparse, asyncio, json, html, random, re, sys, logging, time
from pathlib import Path
from playwright.async_api import async_playwright
from typing import Any

# --- 导入统一日志工具 ---
BASE_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BASE_DIR / "src"))
from xianyu_tools.config import settings
from xianyu_tools.channel_search_filters import (
    get_ali1688_channel_search_filter_keys,
    get_ali1688_channel_search_filter_meta,
)
from xianyu_tools.logging_util import get_unified_logger
from xianyu_tools.source_adapter import Ali1688SourceAdapter
from xianyu_tools.source_adapter.ali1688 import (
    apply_ali1688_query_filters_to_url,
    build_ali1688_query_filter_expectation,
    get_ali1688_query_mapped_filter_keys,
    verify_ali1688_query_filters_from_url,
)
from xianyu_tools.xianyu_adapter.browser_transport import (
    default_desktop_context_options, default_launch_args
)

try:
    import pyautogui
except ImportError:
    pyautogui = None


def _sanitize_filename(name: str) -> str:
    name = html.unescape(name).replace(">", "-").replace("&", "and")
    return re.sub(r'[\\/:*?"<>|]', '_', name).strip()[:60]

DEFAULT_ALI1688_STATE_FILE = "state/source_channels/ali1688/ali1688-account-1/storage_state.json"
DEFAULT_ALI1688_USER_DATA_DIR = str(
    (Path(__file__).resolve().parents[1] / "profiles" / "source_channels" / "ali1688" / "ali1688-account-1" / "chrome_profile").resolve()
)
DEFAULT_ALI1688_EXTENSION_DIR = "tmp/1688-extension"


def _load_active_ali1688_runtime_defaults() -> tuple[str, str, str | None]:
    try:
        runtime_cfg = settings.get_active_ali1688_runtime_config()
    except Exception:
        runtime_cfg = {}

    state_file = runtime_cfg.get("state_file") or DEFAULT_ALI1688_STATE_FILE
    user_data_dir = runtime_cfg.get("user_data_dir") or DEFAULT_ALI1688_USER_DATA_DIR
    profile_directory = runtime_cfg.get("profile_directory") or None
    return str(state_file), str(user_data_dir), profile_directory


def _append_extension_launch_args(args: list[str], extension_dir: str) -> list[str]:
    new_args = [a for a in args if a != "--disable-extensions"]
    ext_path = str(Path(extension_dir).resolve())
    if f"--disable-extensions-except={ext_path}" not in new_args:
        new_args.append(f"--disable-extensions-except={ext_path}")
    if f"--load-extension={ext_path}" not in new_args:
        new_args.append(f"--load-extension={ext_path}")
    return new_args


def _resolve_browser_channel(channel: str, extension_dir: str) -> str | None:
    if extension_dir:
        if channel == "chrome":
            return None
    return channel


def _resolve_runtime_user_data_dir(original_user_data_dir: str, channel: str | None, extension_dir: str, output_dir: Path) -> str:
    if channel is None and extension_dir:
        return str((output_dir / "_runtime_chromium_profile").resolve())
    return original_user_data_dir


def _sanitize_storage_state_cookies(cookies: list[dict]) -> list[dict]:
    allowed_fields = {"name", "value", "domain", "path", "expires", "httpOnly", "secure", "sameSite"}
    clean_list = []
    for c in cookies:
        item = {k: v for k, v in c.items() if k in allowed_fields}
        if "sameSite" in item and item["sameSite"] not in ["Strict", "Lax", "None"]:
            del item["sameSite"]
        clean_list.append(item)
    return clean_list


def _prepare_managed_state_file(source_state: str, managed_state_file: str) -> tuple[str | None, bool]:
    source_path = Path(source_state)
    target_path = Path(managed_state_file)
    
    if not source_path.exists():
        if source_state != managed_state_file:
            raise FileNotFoundError(f"state file not found at {source_state}")
        return None, False
        
    try:
        target_path.parent.mkdir(parents=True, exist_ok=True)
        target_path.write_text(source_path.read_text(encoding="utf-8"), encoding="utf-8")
        return str(target_path.resolve()), True
    except Exception:
        return None, False


async def _apply_state_file_cookies(context, state_file: str | Path) -> None:
    state_path = Path(state_file)
    if state_path.exists():
        try:
            state = json.loads(state_path.read_text(encoding="utf-8"))
            cookies = state.get("cookies", [])
            clean_cookies = _sanitize_storage_state_cookies(cookies)
            await context.add_cookies(clean_cookies)
        except Exception:
            pass


async def _export_context_state(context, state_file: str | Path) -> None:
    state_path = Path(state_file)
    try:
        state_path.parent.mkdir(parents=True, exist_ok=True)
        state = await context.storage_state()
        if "cookies" in state:
            state["cookies"] = _sanitize_storage_state_cookies(state["cookies"])
        state_path.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception:
        pass


def _overlay_close_click_point(rect: dict) -> tuple[float, float]:
    x = rect.get("x", 0.0)
    y = rect.get("y", 0.0)
    w = rect.get("width", 0.0)
    h = rect.get("height", 0.0)
    return x + w - 22.0, y + 20.0


def _plugin_toolbar_selectors() -> list[str]:
    return [
        "#market-mate-for-1688",
        "#market-mate-for-1688-od",
        ".goods-operation-panel-media",
        ".goods-operation-hover.copy-sku",
        "text=复制sku",
    ]


async def _plugin_toolbar_ready(page) -> bool:
    selectors = _plugin_toolbar_selectors()
    for sel in selectors:
        try:
            loc = page.locator(sel).first
            if await loc.count() > 0 and await loc.is_visible():
                return True
        except Exception:
            pass
    return False


async def _copy_sku_drawer_opened(page) -> bool:
    try:
        drawer = page.locator("#consign-sku-fullscreen-drawer").first
        iframe = page.locator("#fullscreen-drawer-iframe").first
        if await drawer.count() > 0 and await drawer.is_visible():
            src = await iframe.get_attribute("src")
            if src and "#hidden" not in src:
                return True
    except Exception:
        pass
    return False


async def _copy_sku_drawer_state(page) -> dict:
    try:
        drawer = page.locator("#consign-sku-fullscreen-drawer").first
        iframe = page.locator("#fullscreen-drawer-iframe").first
        drawer_present = await drawer.count() > 0
        drawer_visible = await drawer.is_visible() if drawer_present else False
        drawer_style = await drawer.get_attribute("style") if drawer_present else None
        iframe_present = await iframe.count() > 0
        iframe_src = await iframe.get_attribute("src") if iframe_present else None
        iframe_hidden = "#hidden" in iframe_src if iframe_src else True
        opened = drawer_visible and not iframe_hidden
    except Exception:
        drawer_present = drawer_visible = iframe_present = False
        drawer_style = iframe_src = None
        iframe_hidden = opened = False
    return {
        "drawer_present": drawer_present,
        "drawer_visible": drawer_visible,
        "drawer_style": drawer_style,
        "iframe_present": iframe_present,
        "iframe_src": iframe_src,
        "iframe_hidden": iframe_hidden,
        "opened": opened,
    }


async def _overlay_state(page) -> dict:
    try:
        overlay_loc = page.locator(".J_MIDDLEWARE_FRAME_WIDGET:visible")
        overlay_count = await overlay_loc.count()
        ack_loc = page.get_by_text("我知道了", exact=True)
        ack_visible = False
        if await ack_loc.count() > 0:
            ack_visible = await ack_loc.first.is_visible()
        toolbar_ready = await _plugin_toolbar_ready(page)
    except Exception:
        overlay_count = 0
        ack_visible = toolbar_ready = False
    return {
        "overlay_count": overlay_count,
        "ack_visible": ack_visible,
        "toolbar_ready": toolbar_ready,
    }


async def _clear_extension_onboarding_state(context) -> None:
    for sw in context.service_workers:
        try:
            await asyncio.wait_for(sw.evaluate("""
                () => {
                    if (typeof chrome !== 'undefined' && chrome.storage && chrome.storage.local) {
                        chrome.storage.local.set({
                            '_1688_EXTENSION_ONBOARDING_FEATURE': 'done',
                            '_1688_EXTENSION_SHOW_GUIDANCE_REASON': 'none'
                        }, () => {
                            console.log('Onboarding state cleared');
                        });
                    }
                }
            """), timeout=2.0)
        except Exception:
            pass


def _parse_dispatch_count(val_str: str) -> int:
    if not val_str:
        return 0
    val_str = val_str.strip()
    
    match = re.match(r'^([\d\.]+)\s*([万kK]?)$', val_str)
    if not match:
        num_match = re.search(r'([\d\.]+)', val_str)
        if not num_match:
            return 0
        num = float(num_match.group(1))
        unit = ""
        if "万" in val_str:
            unit = "万"
        elif "k" in val_str or "K" in val_str:
            unit = "k"
    else:
        num = float(match.group(1))
        unit = match.group(2)
        
    if unit == "万":
        return int(num * 10000)
    elif unit in ["k", "K"]:
        return int(num * 1000)
    return int(num)


def _normalize_metric_text(text: str) -> str:
    if not text:
        return ""
    normalized = re.sub(r"<[^>]+>", " ", text)
    normalized = html.unescape(normalized)
    normalized = normalized.replace("\xa0", " ")
    normalized = re.sub(r"\s+", " ", normalized)
    return normalized.strip()


def _load_channel_filter_snapshot(snapshot_file: str | None) -> dict:
    if not snapshot_file:
        return {}
    try:
        path = Path(snapshot_file)
        if not path.exists():
            return {}
        raw = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    if not isinstance(raw, dict):
        return {}
    return settings.normalize_channel_search_filter_snapshot(raw)


def _build_runtime_filter_snapshot(configured_snapshot: dict | None) -> dict:
    configured_snapshot = configured_snapshot or {}
    configured_filters = configured_snapshot.get("filters")
    if not isinstance(configured_filters, dict):
        configured_filters = {}
    configured_filters = {str(key): bool(val) for key, val in configured_filters.items()}
    enabled_filter_keys = [key for key, enabled in configured_filters.items() if enabled]
    applied_filters: dict[str, bool] = {}
    applied_filter_keys: list[str] = []
    unapplied_filter_keys = list(enabled_filter_keys)
    unapplied_reason_map = {
        key: "runtime_mapping_not_implemented_yet"
        for key in unapplied_filter_keys
    }
    filter_status_map = {
        key: {
            "configured": True,
            "status": "unapplied",
            "reason": unapplied_reason_map.get(key, ""),
            "verification_detail": (
                build_ali1688_query_filter_expectation(key)
                if key in get_ali1688_query_mapped_filter_keys()
                else {}
            ),
        }
        for key in enabled_filter_keys
    }
    return settings.normalize_channel_search_filter_snapshot({
        "channel_id": str(configured_snapshot.get("channel_id") or ""),
        "channel_type": str(configured_snapshot.get("channel_type") or ""),
        "filters": dict(configured_filters),
        "supported_filter_keys": list(configured_snapshot.get("supported_filter_keys") or configured_filters.keys()),
        "configured_filters": configured_filters,
        "configured_enabled_filter_keys": enabled_filter_keys,
        "query_injected_filter_keys": [],
        "query_injected_query_params": {},
        "query_verification_details": {},
        "applied_filters": applied_filters,
        "applied_filter_keys": applied_filter_keys,
        "unapplied_filters": {key: True for key in unapplied_filter_keys},
        "unapplied_filter_keys": unapplied_filter_keys,
        "unapplied_reason_map": unapplied_reason_map,
        "filter_status_map": filter_status_map,
        "mapping_stage": "snapshot_only",
        "mapping_notes": "当前仅记录配置快照，尚未将筛选项真实映射到 1688 搜索行为。",
    })


def _write_runtime_filter_snapshot_audit(
    output_dir: Path,
    runtime_snapshot: dict,
    *,
    stage: str,
    logger=None,
    extra: dict | None = None,
) -> dict:
    """Persist the latest runtime filter evidence even when later parsing fails."""
    audit_stage = str(stage or "unknown")
    normalized_snapshot = settings.normalize_channel_search_filter_snapshot({
        **dict(runtime_snapshot or {}),
        "runtime_audit_stage": audit_stage,
        "runtime_audit_source": "_channel_filter_runtime_snapshot.json",
    })
    audit_generated_at_epoch = time.time()
    audit_run_id = (
        f"{int(audit_generated_at_epoch)}-"
        f"{normalized_snapshot.get('channel_id') or 'unknown-channel'}-"
        f"{audit_stage}"
    )
    payload = {
        "stage": audit_stage,
        "audit_generated_at_epoch": audit_generated_at_epoch,
        "audit_run_id": audit_run_id,
        "channel_id": normalized_snapshot.get("channel_id") or "",
        "channel_type": normalized_snapshot.get("channel_type") or "",
        "configured_enabled_filter_keys": normalized_snapshot.get("configured_enabled_filter_keys") or [],
        "query_injected_filter_keys": normalized_snapshot.get("query_injected_filter_keys") or [],
        "applied_filter_keys": normalized_snapshot.get("applied_filter_keys") or [],
        "unapplied_filter_keys": normalized_snapshot.get("unapplied_filter_keys") or [],
        "mapping_stage": normalized_snapshot.get("mapping_stage") or "",
        "filter_status_map": normalized_snapshot.get("filter_status_map") or {},
        "query_verification_details": normalized_snapshot.get("query_verification_details") or {},
        "snapshot": normalized_snapshot,
    }
    if isinstance(extra, dict) and extra:
        payload["extra"] = dict(extra)

    try:
        output_dir.mkdir(parents=True, exist_ok=True)
        audit_path = output_dir / "_channel_filter_runtime_snapshot.json"
        audit_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        event_path = output_dir / "_channel_filter_runtime_events.jsonl"
        with event_path.open("a", encoding="utf-8") as fp:
            fp.write(json.dumps(payload, ensure_ascii=False) + "\n")
        if logger:
            logger.info(
                "[Search] Channel filter runtime snapshot persisted: %s",
                {
                    "stage": payload["stage"],
                    "audit_path": str(audit_path),
                    "configured_enabled_filter_keys": payload["configured_enabled_filter_keys"],
                    "applied_filter_keys": payload["applied_filter_keys"],
                    "unapplied_filter_keys": payload["unapplied_filter_keys"],
                },
            )
    except Exception as audit_err:
        if logger:
            logger.warning(f"[Search] Failed to persist channel filter runtime snapshot: {audit_err}")
    return normalized_snapshot


def _mark_runtime_filter_snapshot_navigation_blocked(
    runtime_snapshot: dict,
    *,
    stage: str,
    url: str | None = None,
    reason: str = "navigation_blocked_by_verification",
) -> dict:
    filter_status_map = {
        str(key): dict(value or {})
        for key, value in dict(runtime_snapshot.get("filter_status_map") or {}).items()
    }
    for key, meta in filter_status_map.items():
        if meta.get("status") in {"applied", "query_injected_pending_verification"}:
            continue
        verification_detail = dict(meta.get("verification_detail") or {})
        if url:
            verification_detail["blocked_url"] = str(url)
        verification_detail["blocked_stage"] = str(stage or "")
        meta["status"] = "blocked"
        meta["reason"] = reason
        meta["mapping_stage"] = "navigation_blocked"
        meta["verification_detail"] = verification_detail
        filter_status_map[key] = meta
    return settings.normalize_channel_search_filter_snapshot({
        **dict(runtime_snapshot or {}),
        "filter_status_map": filter_status_map,
        "mapping_stage": "navigation_blocked",
        "mapping_notes": "1688 页面进入验证码/登录验证，筛选项尚未进入真实搜索页动作阶段。",
    })


def _normalize_probe_text(text: str | None) -> str:
    normalized = html.unescape(str(text or ""))
    normalized = re.sub(r"<[^>]+>", " ", normalized)
    normalized = normalized.replace("\xa0", " ")
    normalized = re.sub(r"\s+", "", normalized)
    return normalized


def _mark_runtime_snapshot_non_query_probe(
    runtime_snapshot: dict,
    *,
    observed_page_text: str | None,
    result_url: str | None = None,
) -> dict:
    configured_filters = dict(runtime_snapshot.get("configured_filters") or {})
    configured_enabled_filter_keys = list(runtime_snapshot.get("configured_enabled_filter_keys") or [])
    filter_status_map = {
        str(key): dict(value or {})
        for key, value in dict(runtime_snapshot.get("filter_status_map") or {}).items()
    }
    query_keys = set(get_ali1688_query_mapped_filter_keys())
    normalized_text = _normalize_probe_text(observed_page_text)
    if not configured_enabled_filter_keys or not normalized_text:
        return settings.normalize_channel_search_filter_snapshot({
            **runtime_snapshot,
            "filter_status_map": filter_status_map,
        })

    for key in configured_enabled_filter_keys:
        if key in query_keys:
            continue
        current_meta = dict(filter_status_map.get(key) or {})
        verification_detail = dict(current_meta.get("verification_detail") or {})
        shared_meta = get_ali1688_channel_search_filter_meta(key)
        probe_terms = [
            str(item).strip()
            for item in shared_meta.get("probe_terms") or []
            if str(item).strip()
        ]
        matched_terms = [term for term in probe_terms if _normalize_probe_text(term) and _normalize_probe_text(term) in normalized_text]
        verification_detail.update({
            "probe_mode": "html_text_scan",
            "observation_scope": str(shared_meta.get("observation_scope") or "result_page_text").strip() or "result_page_text",
            "probe_terms": probe_terms,
            "matched_terms": matched_terms,
            "text_visible": bool(matched_terms),
        })
        if result_url:
            verification_detail["result_url"] = str(result_url)
        semantic_dependencies = [
            str(item).strip()
            for item in current_meta.get("semantic_dependencies") or shared_meta.get("semantic_dependencies") or []
            if str(item).strip()
        ]
        if semantic_dependencies:
            verification_detail["semantic_dependencies"] = list(semantic_dependencies)
            dependencies_enabled = all(bool(configured_filters.get(dep, False)) for dep in semantic_dependencies)
            verification_detail["dependencies_enabled"] = dependencies_enabled
            verification_detail["semantic_verification_stage"] = (
                "dependency_pair_enabled"
                if dependencies_enabled
                else "dependency_pair_incomplete"
            )
            if (
                current_meta.get("status") == "unapplied"
                and matched_terms
                and dependencies_enabled
            ):
                current_meta["reason"] = "snapshot_only_until_semantics_confirmed"
                current_meta["mapping_stage"] = "mixed"
        if (
            current_meta.get("mapping_type") == "special_panel_candidate"
            and current_meta.get("status") == "unapplied"
            and matched_terms
        ):
            verification_detail["entry_signal_detected"] = True
            verification_detail["entry_signal_type"] = str(shared_meta.get("entry_signal_type") or "text_term").strip() or "text_term"
            verification_detail["next_required_action"] = str(shared_meta.get("next_required_action") or "panel_open_and_toggle").strip() or "panel_open_and_toggle"
            current_meta["reason"] = "special_panel_entry_detected_unmapped"
            current_meta["mapping_stage"] = "mixed"
        current_meta["verification_detail"] = verification_detail
        filter_status_map[key] = current_meta

    return settings.normalize_channel_search_filter_snapshot({
        **runtime_snapshot,
        "filter_status_map": filter_status_map,
    })


def _mark_runtime_snapshot_semantic_dependency_combos(runtime_snapshot: dict) -> dict:
    """Close semantic combo filters when their query dependencies have strong URL evidence."""
    configured_enabled_filter_keys = list(runtime_snapshot.get("configured_enabled_filter_keys") or [])
    if not configured_enabled_filter_keys:
        return runtime_snapshot

    filter_status_map = {
        str(key): dict(value or {})
        for key, value in dict(runtime_snapshot.get("filter_status_map") or {}).items()
    }
    changed = False
    for key in configured_enabled_filter_keys:
        current_meta = dict(filter_status_map.get(key) or {})
        if str(current_meta.get("mapping_type") or "").strip() != "semantic_combo_candidate":
            continue
        shared_meta = get_ali1688_channel_search_filter_meta(key)
        dependencies = [
            str(item).strip()
            for item in current_meta.get("semantic_dependencies") or shared_meta.get("semantic_dependencies") or []
            if str(item).strip()
        ]
        if not dependencies:
            continue

        dependency_status_map: dict[str, dict] = {}
        dependencies_strong = True
        for dep in dependencies:
            dep_meta = dict(filter_status_map.get(dep) or {})
            dep_detail = dict(dep_meta.get("verification_detail") or {})
            dep_strong = (
                dep_meta.get("status") == "applied"
                and dep_detail.get("verification_mode") == "post_navigation_url"
                and bool(dep_detail.get("matched_values"))
            )
            dependency_status_map[dep] = {
                "status": dep_meta.get("status") or "",
                "mapping_stage": dep_meta.get("mapping_stage") or "",
                "verification_mode": dep_detail.get("verification_mode") or "",
                "matched_values": list(dep_detail.get("matched_values") or []),
                "strong_url_evidence": dep_strong,
            }
            dependencies_strong = dependencies_strong and dep_strong
        if not dependencies_strong:
            continue

        verification_detail = dict(current_meta.get("verification_detail") or {})
        verification_detail.update({
            "verification_mode": "semantic_dependency_pair",
            "semantic_dependencies": dependencies,
            "semantic_verification_stage": "dependency_pair_strong_verified",
            "semantic_conclusion": "dependency_pair_strong_verified",
            "dependency_status_map": dependency_status_map,
        })
        current_meta.update({
            "status": "applied",
            "reason": "",
            "mapping_stage": "semantic_combo",
            "verification_detail": verification_detail,
        })
        filter_status_map[key] = current_meta
        changed = True

    if not changed:
        return runtime_snapshot

    return settings.normalize_channel_search_filter_snapshot({
        **runtime_snapshot,
        "filter_status_map": filter_status_map,
        "mapping_stage": "mixed",
        "mapping_notes": "组合语义筛选项已通过其依赖 query 筛选项的真实 URL 强证据完成闭环。",
    })


async def _refresh_runtime_snapshot_on_current_page(
    page,
    runtime_snapshot: dict,
    *,
    observed_page_text: str | None,
    result_url: str | None,
    logger=None,
) -> dict:
    runtime_snapshot = _mark_runtime_snapshot_non_query_probe(
        runtime_snapshot,
        observed_page_text=observed_page_text,
        result_url=result_url,
    )
    runtime_snapshot = _mark_runtime_snapshot_semantic_dependency_combos(runtime_snapshot)
    runtime_snapshot = await _apply_visible_filter_toggle_runtime(
        page,
        runtime_snapshot,
        logger=logger,
    )
    runtime_snapshot = _mark_runtime_snapshot_semantic_dependency_combos(runtime_snapshot)
    runtime_snapshot = await _apply_special_panel_candidate_runtime(
        page,
        runtime_snapshot,
        logger=logger,
    )
    return _mark_runtime_snapshot_semantic_dependency_combos(runtime_snapshot)


async def _locator_is_actionable(locator) -> bool:
    try:
        return await locator.count() > 0 and await locator.is_visible()
    except Exception:
        return False


async def _find_first_visible_text_locator(root, text_candidates: list[str]) -> tuple[Any | None, str]:
    for text in text_candidates:
        normalized = str(text or "").strip()
        if not normalized:
            continue
        try:
            locator = root.get_by_text(normalized, exact=False).first
            if await _locator_is_actionable(locator):
                return locator, normalized
        except Exception:
            continue
    return None, ""


async def _detect_ali1688_filter_layout(page) -> str:
    layout_selectors = [
        ("image_result_filter_bar", "[class*='configFilter--'], [class*='filterBottomOptions--'], [class*='bottomFilterOption--']"),
        ("standard_search_filter_bar", ".search-filt-item, .sn-row, .sn-select-wrap"),
    ]
    for layout_name, selector in layout_selectors:
        try:
            locator = page.locator(selector).first
            if await _locator_is_actionable(locator):
                return layout_name
        except Exception:
            continue
    return "unknown"


async def _find_filter_entry_locator(page, term: str, *, layout_name: str = "") -> tuple[Any | None, str, dict[str, Any]]:
    normalized_term = str(term or "").strip()
    if not normalized_term:
        return None, "", {
            "selector_candidates_tried": [],
            "text_fallback_considered": False,
            "resolution_mode": "empty_term",
        }

    selector_candidates: list[tuple[str, str]] = []
    if layout_name == "image_result_filter_bar":
        selector_candidates = [
            ("image_config_filter", f"[class*='configFilter--']:has-text('{normalized_term}')"),
            ("image_config_label", f"[class*='configLabel--']:has-text('{normalized_term}')"),
            ("image_bottom_filter_option", f"[class*='bottomFilterOption--']:has-text('{normalized_term}')"),
            ("image_bottom_option_label", f"[class*='optionLabel--']:has-text('{normalized_term}')"),
        ]
    elif layout_name == "standard_search_filter_bar":
        selector_candidates = [
            ("standard_search_filter_item", f".search-filt-item:has-text('{normalized_term}')"),
            ("standard_select_item", f".select-item:has-text('{normalized_term}')"),
            ("standard_col_item", f".sn-col-item:has-text('{normalized_term}')"),
        ]

    selector_candidates_tried: list[dict[str, Any]] = []
    for strategy, selector in selector_candidates:
        try:
            locator = page.locator(selector).first
            actionable = await _locator_is_actionable(locator)
            selector_candidates_tried.append(
                {
                    "strategy": strategy,
                    "selector": selector,
                    "actionable": bool(actionable),
                }
            )
            if actionable:
                return locator, strategy, {
                    "selector_candidates_tried": selector_candidates_tried,
                    "text_fallback_considered": False,
                    "resolution_mode": "selector_candidate",
                }
        except Exception:
            selector_candidates_tried.append(
                {
                    "strategy": strategy,
                    "selector": selector,
                    "actionable": False,
                    "error": "locator_probe_failed",
                }
            )
            continue

    text_locator, _ = await _find_first_visible_text_locator(page, [normalized_term])
    if text_locator is not None:
        return text_locator, "text_fallback", {
            "selector_candidates_tried": selector_candidates_tried,
            "text_fallback_considered": True,
            "resolution_mode": "text_fallback",
        }
    return None, "", {
        "selector_candidates_tried": selector_candidates_tried,
        "text_fallback_considered": True,
        "resolution_mode": "not_found",
    }


async def _click_locator_best_effort(locator) -> bool:
    try:
        await locator.click(timeout=2000)
        return True
    except Exception:
        pass
    try:
        await locator.click(timeout=2000, force=True)
        return True
    except Exception:
        pass
    try:
        handle = await locator.element_handle()
        if handle is None:
            return False
        await handle.evaluate(
            """
            (node) => {
              try {
                node.scrollIntoView({block: 'center', inline: 'center'});
              } catch (e) {}
              try {
                node.click();
              } catch (e) {
                const evt = new MouseEvent('click', {bubbles: true, cancelable: true});
                node.dispatchEvent(evt);
              }
            }
            """
        )
        return True
    except Exception:
        return False


async def _read_special_panel_term_state(page, term: str) -> dict[str, Any]:
    script = """
    ({ term }) => {
      const normalize = (value) =>
        String(value || '')
          .replace(/\\u00a0/g, ' ')
          .replace(/\\s+/g, ' ')
          .trim();

      const textIncludes = (node) => normalize(node?.innerText || node?.textContent || '').includes(term);
      const activeConditionTextIncludes = (node) => {
        const text = normalize(node?.innerText || node?.textContent || '');
        return text.includes(`${term}：`) || text.includes(`${term}:`);
      };
      const isVisible = (node) => {
        if (!node || !(node instanceof Element)) return false;
        const style = window.getComputedStyle(node);
        const rect = node.getBoundingClientRect();
        return style.display !== 'none'
          && style.visibility !== 'hidden'
          && style.opacity !== '0'
          && rect.width > 0
          && rect.height > 0;
      };

      const activeConditionElements = Array.from(document.querySelectorAll('label, span, div, button, a, li, p')).filter((node) => {
        if (!activeConditionTextIncludes(node)) return false;
        if (!isVisible(node)) return false;
        const children = Array.from(node.children || []);
        return !children.some((child) => activeConditionTextIncludes(child) && isVisible(child));
      });

      const elements = Array.from(document.querySelectorAll('label, span, div, button, a, li, p')).filter((node) => {
        if (!textIncludes(node)) return false;
        if (!isVisible(node)) return false;
        const children = Array.from(node.children || []);
        return !children.some((child) => textIncludes(child) && isVisible(child));
      });

      const inspectSelected = (start) => {
        let current = start;
        for (let depth = 0; current && depth < 6; depth += 1, current = current.parentElement) {
          const ariaChecked = current.getAttribute?.('aria-checked');
          if (ariaChecked === 'true') return true;
          const dataChecked = current.getAttribute?.('data-checked');
          if (dataChecked === 'true') return true;
          const className = String(current.className || '');
          if (/checked|selected|active|is-checked|is-selected/i.test(className)) return true;
          const input = current.querySelector?.('input[type="checkbox"], input[type="radio"]');
          if (input && input.checked) return true;
        }
        return false;
      };

      const describe = (node) => {
        let clickable = node;
        for (let depth = 0; clickable && depth < 6; depth += 1, clickable = clickable.parentElement) {
          const tag = (clickable.tagName || '').toLowerCase();
          const role = clickable.getAttribute?.('role') || '';
          if (['button', 'label', 'input', 'a'].includes(tag)) {
            return { selected: inspectSelected(node), selected_via: '', tag, role, text: normalize(node.innerText || node.textContent || '') };
          }
          if (role === 'button' || role === 'checkbox' || role === 'radio') {
            return { selected: inspectSelected(node), selected_via: '', tag, role, text: normalize(node.innerText || node.textContent || '') };
          }
        }
        return {
          selected: inspectSelected(node),
          tag: (node.tagName || '').toLowerCase(),
          role: node.getAttribute?.('role') || '',
          selected_via: '',
          text: normalize(node.innerText || node.textContent || ''),
        };
      };

      if (activeConditionElements.length) {
        return {
          visible: true,
          selected: true,
          selected_via: 'active_condition_text',
          tag: (activeConditionElements[0].tagName || '').toLowerCase(),
          role: activeConditionElements[0].getAttribute?.('role') || '',
          text: normalize(activeConditionElements[0].innerText || activeConditionElements[0].textContent || ''),
        };
      }
      if (!elements.length) {
        return { visible: false, selected: false, selected_via: '', text: '', tag: '', role: '' };
      }
      return {
        visible: true,
        ...describe(elements[0]),
      };
    }
    """
    try:
        result = await page.evaluate(script, {"term": str(term or "").strip()})
    except Exception:
        result = {}
    if not isinstance(result, dict):
        result = {}
    return {
        "visible": bool(result.get("visible")),
        "selected": bool(result.get("selected")),
        "selected_via": str(result.get("selected_via") or "").strip(),
        "text": str(result.get("text") or "").strip(),
        "tag": str(result.get("tag") or "").strip(),
        "role": str(result.get("role") or "").strip(),
    }


async def _capture_result_signature(page) -> dict[str, Any]:
    script = """
    () => {
      const normalize = (value) => String(value || '').replace(/\\s+/g, ' ').trim();
      const seen = new Set();
      const entries = [];

      const candidateNodes = Array.from(
        document.querySelectorAll(
          [
            '[data-offerid]',
            '[data-item-id]',
            '[data-id]',
            '[data-article-id]',
            'a[href*="/offer/"]',
            'a[href*="detail.1688.com/offer/"]',
            '[class*="offerItem"]',
            '[class*="offer-item"]',
            '[class*="result-item"]',
            '[class*="list-item"]',
            '[data-result-item]'
          ].join(',')
        )
      );

      const buildEntry = (node) => {
        if (!(node instanceof Element)) return null;
        const offerId =
          node.getAttribute('data-offerid')
          || node.getAttribute('data-item-id')
          || node.getAttribute('data-id')
          || node.getAttribute('data-article-id')
          || '';
        const href = node.getAttribute('href') || node.querySelector?.('a[href]')?.getAttribute('href') || '';
        const hrefOfferMatch = String(href).match(/offer\\/(\\d+)\\.html/i);
        const title =
          normalize(node.getAttribute('title'))
          || normalize(node.querySelector?.('[title]')?.getAttribute('title'))
          || normalize(node.querySelector?.('img[alt]')?.getAttribute('alt'))
          || normalize(node.querySelector?.('a')?.innerText)
          || normalize(node.innerText).slice(0, 120);
        const key = normalize(offerId || (hrefOfferMatch ? hrefOfferMatch[1] : '') || title);
        if (!key) return null;
        return {
          key,
          title,
          offerId: normalize(offerId || (hrefOfferMatch ? hrefOfferMatch[1] : '')),
          href: normalize(href),
        };
      };

      candidateNodes.forEach((node) => {
        const entry = buildEntry(node);
        if (!entry) return;
        if (seen.has(entry.key)) return;
        seen.add(entry.key);
        entries.push(entry);
      });

      const topEntries = entries.slice(0, 5);
      return {
        result_url: location.href,
        item_count: entries.length,
        top_keys: topEntries.map((item) => item.key),
        top_titles: topEntries.map((item) => item.title).filter(Boolean),
        signature: topEntries.map((item) => item.key).join('|'),
      };
    }
    """
    try:
        result = await page.evaluate(script)
    except Exception:
        result = {}
    if not isinstance(result, dict):
        result = {}
    return {
        "result_url": str(result.get("result_url") or "").strip(),
        "item_count": int(result.get("item_count") or 0),
        "top_keys": [
            str(item).strip()
            for item in list(result.get("top_keys") or [])
            if str(item).strip()
        ],
        "top_titles": [
            str(item).strip()
            for item in list(result.get("top_titles") or [])
            if str(item).strip()
        ],
        "signature": str(result.get("signature") or "").strip(),
    }


def _result_url_changed(pre_signature: dict[str, Any], post_signature: dict[str, Any]) -> bool:
    pre_url = str(dict(pre_signature or {}).get("result_url") or "").strip()
    post_url = str(dict(post_signature or {}).get("result_url") or "").strip()
    return bool(pre_url and post_url and pre_url != post_url)


async def _open_special_filter_panel(page, filter_term: str, *, layout_name: str = "") -> dict[str, Any]:
    trigger_texts = ["配置筛选", "高级筛选", "更多筛选", "筛选"]
    if layout_name == "image_result_filter_bar":
        trigger_texts = ["更多", "筛选", *trigger_texts]
    trigger_locator, trigger_text = await _find_first_visible_text_locator(page, trigger_texts)
    result: dict[str, Any] = {
        "trigger_candidates": list(trigger_texts),
        "trigger_found": bool(trigger_locator),
        "trigger_text": trigger_text,
        "trigger_clicked": False,
        "panel_visible": False,
        "panel_visible_via": "",
    }
    if trigger_locator is None:
        return result

    result["trigger_clicked"] = await _click_locator_best_effort(trigger_locator)
    if not result["trigger_clicked"]:
        return result

    panel_selectors = [
        "[role='dialog']",
        ".ant-modal",
        ".ant-drawer",
        ".ant-popover",
        ".next-dialog",
        ".next-overlay-wrapper",
        "[class*='drawer']",
        "[class*='dialog']",
        "[class*='popover']",
    ]
    for _ in range(10):
        state = await _read_special_panel_term_state(page, filter_term)
        if state.get("visible"):
            result["panel_visible"] = True
            result["panel_visible_via"] = "term_visible"
            return result
        for selector in panel_selectors:
            try:
                locator = page.locator(selector).first
                if await _locator_is_actionable(locator):
                    result["panel_visible"] = True
                    result["panel_visible_via"] = selector
                    return result
            except Exception:
                continue
        await asyncio.sleep(0.2)
    return result


async def _apply_visible_filter_toggle_runtime(
    page,
    runtime_snapshot: dict,
    *,
    logger=None,
) -> dict:
    configured_enabled_filter_keys = list(runtime_snapshot.get("configured_enabled_filter_keys") or [])
    if not configured_enabled_filter_keys:
        return runtime_snapshot

    filter_status_map = {
        str(key): dict(value or {})
        for key, value in dict(runtime_snapshot.get("filter_status_map") or {}).items()
    }
    changed = False
    top_level_mapping_stage = str(runtime_snapshot.get("mapping_stage") or "").strip() or "snapshot_only"
    layout_name = await _detect_ali1688_filter_layout(page)

    for key in configured_enabled_filter_keys:
        current_meta = dict(filter_status_map.get(key) or {})
        mapping_type = str(current_meta.get("mapping_type") or "").strip()
        if mapping_type not in {"ui_checkbox_candidate", "semantic_combo_candidate"}:
            continue

        shared_meta = get_ali1688_channel_search_filter_meta(key)
        probe_terms = [
            str(item).strip()
            for item in shared_meta.get("probe_terms") or []
            if str(item).strip()
        ]
        if not probe_terms:
            continue

        term = probe_terms[0]
        verification_detail = dict(current_meta.get("verification_detail") or {})
        verification_detail["probe_mode"] = str(verification_detail.get("probe_mode") or "dom_toggle_action")
        verification_detail["observation_scope"] = str(
            shared_meta.get("observation_scope")
            or verification_detail.get("observation_scope")
            or "result_page_text"
        ).strip() or "result_page_text"
        verification_detail["page_filter_layout"] = layout_name
        pre_state = await _read_special_panel_term_state(page, term)
        pre_signature = await _capture_result_signature(page)
        if mapping_type == "semantic_combo_candidate":
            verification_detail["independent_ui_entry_observed"] = bool(pre_state.get("visible"))
        verification_detail["panel_term_visible_before_action"] = bool(pre_state.get("visible"))
        verification_detail["panel_term_selected_before_action"] = bool(pre_state.get("selected"))
        if pre_state.get("selected_via"):
            verification_detail["panel_term_selected_via_before_action"] = pre_state.get("selected_via")
        verification_detail["result_signature_before_action"] = pre_signature

        if not pre_state.get("visible"):
            current_meta["verification_detail"] = verification_detail
            filter_status_map[key] = current_meta
            continue

        click_attempted = False
        click_succeeded = False
        entry_locator, entry_selector_strategy, locator_resolution = await _find_filter_entry_locator(page, term, layout_name=layout_name)
        verification_detail["selector_candidates_tried"] = list(locator_resolution.get("selector_candidates_tried") or [])
        verification_detail["selector_resolution_mode"] = str(locator_resolution.get("resolution_mode") or "").strip()
        verification_detail["text_fallback_considered"] = bool(locator_resolution.get("text_fallback_considered"))
        if entry_locator is not None and not pre_state.get("selected"):
            click_attempted = True
            click_succeeded = await _click_locator_best_effort(entry_locator)
            verification_detail["entry_click_attempted"] = True
            verification_detail["entry_click_succeeded"] = bool(click_succeeded)
            verification_detail["entry_selector_strategy"] = entry_selector_strategy
            if click_succeeded:
                await asyncio.sleep(0.3)

        post_state = await _read_special_panel_term_state(page, term)
        post_signature = await _capture_result_signature(page)
        verification_detail["panel_term_visible_after_action"] = bool(post_state.get("visible"))
        verification_detail["panel_term_selected_after_action"] = bool(post_state.get("selected"))
        if post_state.get("selected_via"):
            verification_detail["panel_term_selected_via_after_action"] = post_state.get("selected_via")
        verification_detail["result_signature_after_action"] = post_signature
        verification_detail["result_signature_changed"] = bool(
            pre_signature.get("signature")
            and post_signature.get("signature")
            and pre_signature.get("signature") != post_signature.get("signature")
        ) or (
            int(pre_signature.get("item_count") or 0) != int(post_signature.get("item_count") or 0)
        )
        verification_detail["result_url_changed"] = _result_url_changed(pre_signature, post_signature)
        result_effect_observed = bool(
            verification_detail["result_signature_changed"]
            or verification_detail["result_url_changed"]
        )
        if mapping_type == "semantic_combo_candidate":
            verification_detail["semantic_verification_stage"] = (
                "direct_entry_result_shift_observed"
                if result_effect_observed
                else "direct_entry_result_shift_not_observed"
            )

        if post_state.get("selected") or (click_succeeded and result_effect_observed):
            current_meta["status"] = "applied"
            current_meta["reason"] = ""
            current_meta["mapping_stage"] = "ui_automation"
            verification_detail["verification_mode"] = "dom_toggle_action"
            top_level_mapping_stage = "mixed" if top_level_mapping_stage in {"mixed", "query_mapped", "query_candidate"} else "ui_automation"
            changed = True
        elif click_attempted:
            current_meta["status"] = "unapplied"
            current_meta["reason"] = "ui_apply_not_observed"
            current_meta["mapping_stage"] = "mixed"
            verification_detail["verification_mode"] = "dom_toggle_action"
            top_level_mapping_stage = "mixed"
            changed = True

        current_meta["verification_detail"] = verification_detail
        filter_status_map[key] = current_meta
        if logger and click_attempted:
            logger.info(
                "[Search] Visible filter toggle action result: %s",
                {
                    "filter_key": key,
                    "mapping_type": mapping_type,
                    "layout_name": layout_name,
                    "selected_before": bool(pre_state.get("selected")),
                    "selected_after": bool(post_state.get("selected")),
                    "entry_selector_strategy": entry_selector_strategy,
                    "entry_click_succeeded": bool(click_succeeded),
                    "final_reason": current_meta.get("reason") or "",
                },
            )

    if not changed:
        return settings.normalize_channel_search_filter_snapshot({
            **runtime_snapshot,
            "filter_status_map": filter_status_map,
        })

    return settings.normalize_channel_search_filter_snapshot({
        **runtime_snapshot,
        "filter_status_map": filter_status_map,
        "mapping_stage": top_level_mapping_stage,
        "mapping_notes": "已对结果页可见筛选项执行点击/选中态探测，并按实际结果回写状态。",
    })


async def _apply_special_panel_candidate_runtime(
    page,
    runtime_snapshot: dict,
    *,
    logger=None,
) -> dict:
    configured_enabled_filter_keys = list(runtime_snapshot.get("configured_enabled_filter_keys") or [])
    if not configured_enabled_filter_keys:
        return runtime_snapshot

    filter_status_map = {
        str(key): dict(value or {})
        for key, value in dict(runtime_snapshot.get("filter_status_map") or {}).items()
    }
    changed = False
    top_level_mapping_stage = str(runtime_snapshot.get("mapping_stage") or "").strip() or "snapshot_only"
    layout_name = await _detect_ali1688_filter_layout(page)

    for key in configured_enabled_filter_keys:
        current_meta = dict(filter_status_map.get(key) or {})
        if current_meta.get("mapping_type") != "special_panel_candidate":
            continue
        shared_meta = get_ali1688_channel_search_filter_meta(key)
        probe_terms = [
            str(item).strip()
            for item in shared_meta.get("probe_terms") or []
            if str(item).strip()
        ]
        if not probe_terms:
            continue

        term = probe_terms[0]
        verification_detail = dict(current_meta.get("verification_detail") or {})
        verification_detail["probe_mode"] = str(verification_detail.get("probe_mode") or "dom_panel_action")
        verification_detail["observation_scope"] = str(shared_meta.get("observation_scope") or verification_detail.get("observation_scope") or "result_page_text").strip() or "result_page_text"
        verification_detail["page_filter_layout"] = layout_name

        pre_state = await _read_special_panel_term_state(page, term)
        pre_signature = await _capture_result_signature(page)
        verification_detail["panel_term_visible_before_action"] = bool(pre_state.get("visible"))
        verification_detail["panel_term_selected_before_action"] = bool(pre_state.get("selected"))
        if pre_state.get("selected_via"):
            verification_detail["panel_term_selected_via_before_action"] = pre_state.get("selected_via")
        verification_detail["result_signature_before_action"] = pre_signature
        if pre_state.get("tag"):
            verification_detail["panel_term_tag"] = pre_state.get("tag")
        if pre_state.get("role"):
            verification_detail["panel_term_role"] = pre_state.get("role")

        opened_panel = {
            "trigger_found": False,
            "trigger_text": "",
            "trigger_clicked": False,
            "panel_visible": False,
        }
        click_attempted = False
        click_succeeded = False

        if not pre_state.get("selected"):
            if not pre_state.get("visible"):
                opened_panel = await _open_special_filter_panel(page, term, layout_name=layout_name)
                verification_detail["panel_trigger_candidates"] = list(opened_panel.get("trigger_candidates") or [])
                verification_detail["panel_trigger_found"] = bool(opened_panel.get("trigger_found"))
                verification_detail["panel_trigger_text"] = str(opened_panel.get("trigger_text") or "").strip()
                verification_detail["panel_trigger_clicked"] = bool(opened_panel.get("trigger_clicked"))
                verification_detail["panel_opened"] = bool(opened_panel.get("panel_visible"))
                verification_detail["panel_visible_via"] = str(opened_panel.get("panel_visible_via") or "").strip()

            term_locator, entry_selector_strategy, locator_resolution = await _find_filter_entry_locator(page, term, layout_name=layout_name)
            verification_detail["selector_candidates_tried"] = list(locator_resolution.get("selector_candidates_tried") or [])
            verification_detail["selector_resolution_mode"] = str(locator_resolution.get("resolution_mode") or "").strip()
            verification_detail["text_fallback_considered"] = bool(locator_resolution.get("text_fallback_considered"))
            if term_locator is not None:
                click_attempted = True
                click_succeeded = await _click_locator_best_effort(term_locator)
                verification_detail["entry_click_attempted"] = True
                verification_detail["entry_click_succeeded"] = bool(click_succeeded)
                verification_detail["entry_selector_strategy"] = entry_selector_strategy
                if click_succeeded:
                    await asyncio.sleep(0.3)

        post_state = await _read_special_panel_term_state(page, term)
        post_signature = await _capture_result_signature(page)
        verification_detail["panel_term_visible_after_action"] = bool(post_state.get("visible"))
        verification_detail["panel_term_selected_after_action"] = bool(post_state.get("selected"))
        if post_state.get("selected_via"):
            verification_detail["panel_term_selected_via_after_action"] = post_state.get("selected_via")
        verification_detail["result_signature_after_action"] = post_signature
        verification_detail["result_signature_changed"] = bool(
            pre_signature.get("signature")
            and post_signature.get("signature")
            and pre_signature.get("signature") != post_signature.get("signature")
        ) or (
            int(pre_signature.get("item_count") or 0) != int(post_signature.get("item_count") or 0)
        )
        verification_detail["result_url_changed"] = _result_url_changed(pre_signature, post_signature)
        result_effect_observed = bool(
            verification_detail["result_signature_changed"]
            or verification_detail["result_url_changed"]
        )

        if post_state.get("selected") or (click_succeeded and result_effect_observed):
            current_meta["status"] = "applied"
            current_meta["reason"] = ""
            current_meta["mapping_stage"] = "ui_automation"
            verification_detail["verification_mode"] = "dom_panel_action"
            verification_detail["entry_signal_detected"] = True
            verification_detail["entry_signal_type"] = str(shared_meta.get("entry_signal_type") or "text_term").strip() or "text_term"
            verification_detail["next_required_action"] = ""
            top_level_mapping_stage = "mixed" if top_level_mapping_stage in {"mixed", "query_mapped", "query_candidate"} else "ui_automation"
            changed = True
        elif click_attempted or opened_panel.get("trigger_clicked"):
            current_meta["status"] = "unapplied"
            current_meta["reason"] = "special_panel_open_failed"
            current_meta["mapping_stage"] = "mixed"
            verification_detail["verification_mode"] = "dom_panel_action"
            verification_detail["entry_signal_detected"] = bool(
                pre_state.get("visible")
                or post_state.get("visible")
                or opened_panel.get("trigger_found")
            )
            verification_detail["entry_signal_type"] = str(shared_meta.get("entry_signal_type") or "text_term").strip() or "text_term"
            verification_detail["next_required_action"] = str(shared_meta.get("next_required_action") or "panel_open_and_toggle").strip() or "panel_open_and_toggle"
            top_level_mapping_stage = "mixed"
            changed = True

        current_meta["verification_detail"] = verification_detail
        filter_status_map[key] = current_meta
        if logger and (click_attempted or opened_panel.get("trigger_clicked")):
            logger.info(
                "[Search] Special panel candidate action result: %s",
                {
                    "filter_key": key,
                    "selected_before": bool(pre_state.get("selected")),
                    "selected_after": bool(post_state.get("selected")),
                    "trigger_text": str(opened_panel.get("trigger_text") or "").strip(),
                    "trigger_clicked": bool(opened_panel.get("trigger_clicked")),
                    "entry_click_succeeded": bool(click_succeeded),
                    "final_reason": current_meta.get("reason") or "",
                },
            )

    if not changed:
        return runtime_snapshot

    return settings.normalize_channel_search_filter_snapshot({
        **runtime_snapshot,
        "filter_status_map": filter_status_map,
        "mapping_stage": top_level_mapping_stage,
        "mapping_notes": "已对特殊入口候选项执行面板打开/勾选探测，并按实际结果回写状态。",
    })


def _mark_runtime_snapshot_query_injected(
    runtime_snapshot: dict,
    *,
    injected_filter_keys: list[str],
    verified_filter_keys: list[str] | None = None,
    applied_query_params: dict[str, str] | None,
    verification_details: dict[str, dict] | None = None,
    verification_mode: str | None = None,
    result_url: str | None = None,
) -> dict:
    configured_filters = dict(runtime_snapshot.get("configured_filters") or {})
    configured_enabled_filter_keys = list(runtime_snapshot.get("configured_enabled_filter_keys") or [])
    query_injected_filter_keys = [
        key for key in injected_filter_keys
        if key in configured_enabled_filter_keys
    ]
    verified_filter_keys = [
        key for key in (verified_filter_keys or [])
        if key in query_injected_filter_keys
    ]
    unapplied_filter_keys = [
        key for key in configured_enabled_filter_keys
        if key not in verified_filter_keys
    ]
    query_mapped_keys = set(get_ali1688_query_mapped_filter_keys())
    unapplied_reason_map = {}
    for key in unapplied_filter_keys:
        if key in query_injected_filter_keys and key not in verified_filter_keys:
            unapplied_reason_map[key] = "query_filter_injected_pending_verification"
        elif key in query_mapped_keys:
            unapplied_reason_map[key] = "query_filter_not_applied_in_runtime"
        else:
            unapplied_reason_map[key] = "runtime_mapping_not_implemented_yet"
    filter_status_map: dict[str, dict] = {}
    for key in configured_enabled_filter_keys:
        base_detail = (
            build_ali1688_query_filter_expectation(key)
            if key in query_mapped_keys
            else {}
        )
        detail = {
            **base_detail,
            **dict((verification_details or {}).get(key) or {}),
        }
        if key in query_injected_filter_keys:
            if verification_mode:
                detail["verification_mode"] = str(verification_mode)
            if result_url:
                detail["result_url"] = str(result_url)
        if key in verified_filter_keys:
            filter_status_map[key] = {
                "configured": True,
                "mapping_stage": "query_mapped",
                "status": "applied",
                "reason": "",
                "verification_detail": detail,
            }
        elif key in query_injected_filter_keys:
            filter_status_map[key] = {
                "configured": True,
                "mapping_stage": "query_candidate",
                "status": "query_injected_pending_verification",
                "reason": unapplied_reason_map.get(key, ""),
                "verification_detail": detail,
            }
        else:
            filter_status_map[key] = {
                "configured": True,
                "status": "unapplied",
                "reason": unapplied_reason_map.get(key, ""),
                "verification_detail": detail,
            }
    if verified_filter_keys and len(verified_filter_keys) == len(query_injected_filter_keys):
        mapping_stage = "query_mapped"
        mapping_notes = "query 候选项已注入结果页 URL，并在最终结果 URL 中观察到对应筛选参数。"
    elif query_injected_filter_keys:
        mapping_stage = "mixed"
        if verified_filter_keys:
            mapping_notes = "部分 query 候选项已在最终结果 URL 中得到验证，其余项仍处于已注入待验证状态。"
        else:
            mapping_notes = "部分 query 候选项已拼入结果页 URL，但尚未完成结果级验证，暂不标记为已生效。"
    else:
        mapping_stage = "snapshot_only"
        mapping_notes = "当前仅记录配置快照，尚未将筛选项真实映射到 1688 搜索行为。"
    return settings.normalize_channel_search_filter_snapshot({
        **runtime_snapshot,
        "filters": dict(configured_filters),
        "query_injected_filter_keys": list(query_injected_filter_keys),
        "query_injected_query_params": dict(applied_query_params or {}),
        "query_verification_details": dict(verification_details or {}),
        "applied_filters": {key: True for key in verified_filter_keys},
        "applied_filter_keys": list(verified_filter_keys),
        "unapplied_filters": {key: True for key in unapplied_filter_keys},
        "unapplied_filter_keys": unapplied_filter_keys,
        "unapplied_reason_map": unapplied_reason_map,
        "filter_status_map": filter_status_map,
        "mapping_stage": mapping_stage,
        "mapping_notes": mapping_notes,
        "applied_query_params": dict(applied_query_params or {}),
    })


def _mark_runtime_snapshot_query_navigation_failed(
    runtime_snapshot: dict,
    *,
    attempted_filter_keys: list[str],
    attempted_query_params: dict[str, str] | None,
    attempted_result_url: str | None,
) -> dict:
    configured_filters = dict(runtime_snapshot.get("configured_filters") or {})
    configured_enabled_filter_keys = list(runtime_snapshot.get("configured_enabled_filter_keys") or [])
    attempted_filter_keys = [
        key for key in attempted_filter_keys
        if key in configured_enabled_filter_keys
    ]
    query_mapped_keys = set(get_ali1688_query_mapped_filter_keys())
    unapplied_filter_keys = list(configured_enabled_filter_keys)
    unapplied_reason_map: dict[str, str] = {}
    filter_status_map: dict[str, dict] = {}
    for key in configured_enabled_filter_keys:
        base_detail = (
            build_ali1688_query_filter_expectation(key)
            if key in query_mapped_keys
            else {}
        )
        detail = dict(base_detail)
        if key in attempted_filter_keys:
            detail["verification_mode"] = "navigation_failed"
            if attempted_result_url:
                detail["attempted_result_url"] = str(attempted_result_url)
            if attempted_query_params:
                detail["attempted_query_params"] = dict(attempted_query_params)
            reason = "query_filter_navigation_failed"
            per_filter_stage = "query_candidate"
        elif key in query_mapped_keys:
            reason = "query_filter_not_applied_in_runtime"
            per_filter_stage = "snapshot_only"
        else:
            reason = "runtime_mapping_not_implemented_yet"
            per_filter_stage = "snapshot_only"
        unapplied_reason_map[key] = reason
        filter_status_map[key] = {
            "configured": True,
            "mapping_stage": per_filter_stage,
            "status": "unapplied",
            "reason": reason,
            "verification_detail": detail,
        }
    mapping_stage = "mixed" if attempted_filter_keys else "snapshot_only"
    mapping_notes = (
        "已尝试将 query 候选项注入结果页 URL，但跳转失败，暂未进入结果级验证。"
        if attempted_filter_keys
        else "当前仅记录配置快照，尚未将筛选项真实映射到 1688 搜索行为。"
    )
    return settings.normalize_channel_search_filter_snapshot({
        **runtime_snapshot,
        "filters": dict(configured_filters),
        "query_injected_filter_keys": [],
        "query_injected_query_params": dict(attempted_query_params or {}),
        "query_verification_details": {},
        "applied_filters": {},
        "applied_filter_keys": [],
        "unapplied_filters": {key: True for key in unapplied_filter_keys},
        "unapplied_filter_keys": list(unapplied_filter_keys),
        "unapplied_reason_map": dict(unapplied_reason_map),
        "filter_status_map": filter_status_map,
        "mapping_stage": mapping_stage,
        "mapping_notes": mapping_notes,
        "applied_query_params": dict(attempted_query_params or {}),
    })


def _verify_and_mark_runtime_query_snapshot(
    runtime_snapshot: dict,
    *,
    result_url: str,
    injected_filter_keys: list[str],
    applied_query_params: dict[str, str] | None,
    logger=None,
    verification_mode: str | None = None,
) -> tuple[dict, list[str], dict[str, str], dict[str, dict]]:
    verified_query_filter_keys, verified_query_params, query_verification_details = verify_ali1688_query_filters_from_url(
        result_url,
        injected_filter_keys,
    )
    if logger:
        logger.info(
            "[Search] Query filter verification result: %s",
            {
                "verified_filter_keys": verified_query_filter_keys,
                "verification_details": query_verification_details,
                "observed_query_params": verified_query_params,
                "result_url": result_url,
            },
        )
    next_snapshot = _mark_runtime_snapshot_query_injected(
        runtime_snapshot,
        injected_filter_keys=injected_filter_keys,
        verified_filter_keys=verified_query_filter_keys,
        applied_query_params=verified_query_params or applied_query_params,
        verification_details=query_verification_details,
        verification_mode=verification_mode,
        result_url=result_url,
    )
    return next_snapshot, verified_query_filter_keys, verified_query_params, query_verification_details


def _extract_metric_text(text: str, patterns: list[str]) -> str:
    if not text:
        return ""
    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            return re.sub(r"\s+", "", match.group(1).strip())
    return ""


def _format_percent_metric(prefix: str, raw_value: str) -> str:
    if not raw_value:
        return ""
    try:
        number = float(str(raw_value).replace("%", "").strip())
        value = str(int(number)) if number.is_integer() else str(number).rstrip("0").rstrip(".")
        return f"{prefix}{value}%"
    except Exception:
        return f"{prefix}{str(raw_value).strip()}"


def _extract_dispatch_metrics_from_text(text: str) -> dict:
    normalized = _normalize_metric_text(text)
    seven_day = 0
    month = 0
    listing_count = 0
    distributor_count = 0
    pickup_48h_text = _extract_metric_text(normalized, [r"(48\s*h\s*揽收(?:率)?\s*[\d\.]+%)"])
    pickup_24h_text = _extract_metric_text(normalized, [r"(24\s*h\s*揽收(?:率)?\s*[\d\.]+%)"])
    pickup_48h_detail = re.search(r"48\s*h\s*揽收(?:率)?\s*([\d\.]+%)", normalized, re.IGNORECASE)
    if pickup_48h_detail:
        pickup_48h_text = _format_percent_metric("48H揽收", pickup_48h_detail.group(1))
    pickup_24h_detail = re.search(r"24\s*h\s*揽收(?:率)?\s*([\d\.]+%)", normalized, re.IGNORECASE)
    if pickup_24h_detail:
        pickup_24h_text = _format_percent_metric("24H揽收", pickup_24h_detail.group(1))
    count_value_pattern = r"[\d\.]+(?:万|k|K)?(?:\+|以内|内)?"
    month_dispatch_text = _extract_metric_text(normalized, [rf"((?:月代发|月成交|月代发量|月\s*代发|近30天代发数量)\s*{count_value_pattern})"])
    if month_dispatch_text.startswith("近30天代发数量"):
        month_dispatch_text = "月代发" + month_dispatch_text.replace("近30天代发数量", "", 1)
    seven_day_dispatch_text = _extract_metric_text(normalized, [rf"((?:7天|近7天)代发(?:数量)?\s*{count_value_pattern})"])
    if seven_day_dispatch_text.startswith("近7天代发数量"):
        seven_day_dispatch_text = "7天代发" + seven_day_dispatch_text.replace("近7天代发数量", "", 1)
    listing_count_text = _extract_metric_text(normalized, [rf"(铺货数\s*{count_value_pattern})"])
    distributor_count_text = _extract_metric_text(normalized, [rf"((?:分销商数|铺货分销商数)\s*{count_value_pattern})"])
    if distributor_count_text.startswith("铺货分销商数"):
        distributor_count_text = "分销商数" + distributor_count_text.replace("铺货分销商数", "", 1)
    waybill_support_text = _extract_metric_text(normalized, [r"(面单支持|不支持面单)"])
    settled_years_text = _extract_metric_text(normalized, [r"(入驻\s*\d+\s*年)"])
    company_name = ""
    if normalized:
        company_match = re.search(
            r"入驻\s*\d+\s*年\s*([^\s]{2,48}?(?:公司|商行|经营部|科技|电子商务|贸易|工厂|厂|企业|中心|合作社|工作室))",
            normalized,
            re.IGNORECASE,
        )
        if company_match:
            company_name = company_match.group(1).strip()

        match_7 = re.search(r'(?:7天|近7天)代发(?:数量)?\s*([\d\.]+(?:万|k|K)?(?:\+|以内|内)?)', normalized)
        if match_7:
            seven_day = _parse_dispatch_count(match_7.group(1))
        match_m = re.search(r'(?:月代发|月成交|月代发量|月\s*代发|近30天代发数量)\s*([\d\.]+(?:万|k|K)?(?:\+|以内|内)?)', normalized)
        if match_m:
            month = _parse_dispatch_count(match_m.group(1))
        match_listing = re.search(r'铺货数\s*([\d\.]+(?:万|k|K)?(?:\+|以内|内)?)', normalized)
        if match_listing:
            listing_count = _parse_dispatch_count(match_listing.group(1))
        match_distributor = re.search(r'(?:分销商数|铺货分销商数)\s*([\d\.]+(?:万|k|K)?(?:\+|以内|内)?)', normalized)
        if match_distributor:
            distributor_count = _parse_dispatch_count(match_distributor.group(1))
    return {
        "pickup_48h_text": pickup_48h_text,
        "pickup_24h_text": pickup_24h_text,
        "month_dispatch_text": month_dispatch_text,
        "seven_day_dispatch_text": seven_day_dispatch_text,
        "listing_count_text": listing_count_text,
        "distributor_count_text": distributor_count_text,
        "waybill_support_text": waybill_support_text,
        "settled_years_text": settled_years_text,
        "company_name": company_name,
        "seven_day_dispatch_count": seven_day,
        "month_dispatch_count": month,
        "listing_count": listing_count,
        "distributor_count": distributor_count,
    }


def _normalize_image_search_url(url: str) -> str | None:
    if not url or not isinstance(url, str):
        return None
    url_lower = url.lower()
    if not (url_lower.startswith("http://") or url_lower.startswith("https://")):
        return None
    parsed_path = url.split("?")[0]
    if parsed_path.lower().endswith(".heic") or parsed_path.lower().endswith(".gif"):
        return None
    return url


def _top_dispatch_candidates(rows: list, limit: int) -> list:
    valid_rows = [r for r in rows if r.get("item_url")]
    valid_rows.sort(key=lambda r: (int(r.get("page_original_index") or 10**9), str(r.get("offer_id") or "")))
    return valid_rows[:limit]


def _normalize_match_text(value: str) -> str:
    return re.sub(r"\s+", "", str(value or "")).lower()


def _build_visual_offer_order_map(candidates: list, visual_rows: list[dict]) -> dict[str, int]:
    order_map: dict[str, int] = {}
    candidate_titles = {
        _normalize_match_text(getattr(candidate, "title", "")): str(getattr(candidate, "source_item_id", "") or "")
        for candidate in candidates
        if getattr(candidate, "title", "") and getattr(candidate, "source_item_id", "")
    }

    for index, row in enumerate(visual_rows or [], start=1):
        offer_id = str((row or {}).get("offerId") or "")
        if offer_id:
            order_map.setdefault(offer_id, index)
            continue

        row_title = _normalize_match_text((row or {}).get("title") or "")
        if not row_title:
            continue
        for candidate_title, candidate_offer_id in candidate_titles.items():
            if row_title in candidate_title or candidate_title in row_title:
                order_map.setdefault(candidate_offer_id, index)
                break
    return order_map


async def _extract_visual_offer_rows(page, offer_ids: set[str], logger=None) -> list[dict]:
    script = """
    (expectedIds) => {
      const expected = new Set((expectedIds || []).map(String));
      const normalize = (value) => String(value || '').replace(/\\s+/g, ' ').trim();
      const isVisible = (el) => {
        if (!el || !(el instanceof Element)) return false;
        const style = window.getComputedStyle(el);
        if (style.display === 'none' || style.visibility === 'hidden' || Number(style.opacity) === 0) return false;
        const rect = el.getBoundingClientRect();
        return rect.width >= 80 && rect.height >= 80 && rect.bottom >= 0 && rect.right >= 0;
      };
      const offerIdFromText = (value) => {
        const text = String(value || '');
        const patterns = [
          /\\/offer\\/(\\d+)\\.html/,
          /offerId["']?\\s*[:=]\\s*["']?(\\d+)/,
          /offer_id["']?\\s*[:=]\\s*["']?(\\d+)/,
          /data-offer-id=["']?(\\d+)/
        ];
        for (const pattern of patterns) {
          const match = text.match(pattern);
          if (match) return match[1];
        }
        return '';
      };
      const offerIdFromElement = (el) => {
        for (const attr of ['data-offer-id', 'data-offerid', 'offer-id', 'offerid']) {
          const value = el.getAttribute && el.getAttribute(attr);
          if (value && /^\\d+$/.test(value)) return value;
        }
        const anchor = el.querySelector && el.querySelector('a[href*="/offer/"]');
        const fromHref = anchor ? offerIdFromText(anchor.href) : '';
        if (fromHref) return fromHref;
        return offerIdFromText((el.outerHTML || '').slice(0, 12000));
      };
      const isMetricLine = (line) =>
        /[¥￥]|48H|24H|月代发|7天代发|铺货数|分销商|入驻|起批|包邮|页面原始|ID[:：]/.test(line);
      const isMerchantLine = (line) =>
        /公司|商贸|电子商务|贸易|工厂|旗舰店|专营店|经营部|个体工商户/.test(line) &&
        !/洗发水|沐浴露|套装|便携|旅行|正品|批发|瓶|袋|装/.test(line);
      const isUsableTitle = (line) => line && line.length >= 8 && !isMetricLine(line) && !isMerchantLine(line);
      const titleFromElement = (el) => {
        const offerAnchors = Array.from((el.querySelectorAll && el.querySelectorAll('a[href*="/offer/"]')) || []);
        for (const anchor of offerAnchors) {
          const candidates = [
            normalize(anchor.getAttribute('title')),
            normalize(anchor.innerText),
            normalize(anchor.textContent),
          ];
          const matched = candidates.find(isUsableTitle);
          if (matched) return matched;
        }
        const titleNodes = Array.from((el.querySelectorAll && el.querySelectorAll('[class*="title"], [class*="Title"]')) || []);
        for (const titleNode of titleNodes) {
          const candidates = [
            normalize(titleNode.getAttribute('title')),
            normalize(titleNode.innerText),
            normalize(titleNode.textContent),
          ];
          const matched = candidates.find(isUsableTitle);
          if (matched) return matched;
        }
        const lines = String(el.innerText || '')
          .split(/\\n+/)
          .map(normalize)
          .filter(Boolean);
        return lines.find(isUsableTitle) || lines[0] || '';
      };
      const selectors = [
        '[class*="searchOfferWrapper"]',
        '[class*="SearchOffer"]',
        '[class*="offer-card"]',
        '[class*="OfferCard"]',
        '[class*="common-offer"]',
        '[class*="ocms-fusion"]',
        '[data-offer-id]',
        '[data-offerid]'
      ];
      let cards = [];
      for (const selector of selectors) {
        cards = cards.concat(Array.from(document.querySelectorAll(selector)));
      }
      if (!cards.length) {
        cards = Array.from(document.querySelectorAll('div, li')).filter((el) => {
          const text = normalize(el.innerText);
          return text.length >= 40 && /[¥￥]|48H|24H|月代发|7天代发|铺货数|分销商|入驻|起批/.test(text);
        });
      }

      const byKey = new Map();
      for (const card of cards) {
        if (!isVisible(card)) continue;
        const text = normalize(card.innerText);
        if (text.length < 20) continue;
        const offerId = offerIdFromElement(card);
        if (expected.size && offerId && !expected.has(offerId)) continue;
        const title = titleFromElement(card);
        const rect = card.getBoundingClientRect();
        const key = offerId || title;
        if (!key) continue;
        const row = {
          offerId,
          title,
          text: text.slice(0, 500),
          top: Math.round(rect.top + window.scrollY),
          left: Math.round(rect.left + window.scrollX),
          width: Math.round(rect.width),
          height: Math.round(rect.height),
          area: Math.round(rect.width * rect.height),
        };
        const previous = byKey.get(key);
        if (!previous || row.top < previous.top || (row.top === previous.top && row.left < previous.left)) {
          byKey.set(key, row);
        }
      }
      return Array.from(byKey.values())
        .sort((a, b) => a.top - b.top || a.left - b.left)
        .slice(0, 80);
    }
    """
    try:
        rows = await page.evaluate(script, sorted(offer_ids or set()))
    except Exception as exc:
        if logger:
            logger.warning(f"[Search] Failed to extract visible offer rows from DOM: {exc}")
        return []
    return rows or []


async def _extract_selected_filter_chip_texts(page, logger=None) -> list[str]:
    script = """
    () => {
      const normalize = (value) => String(value || '').replace(/\\s+/g, ' ').trim();
      const knownTerms = [
        '极速开票',
        '分销严选',
        '一件代发',
        '7天无理由',
        '1件代发包邮',
        '包邮',
        '退货包运费',
        '真实工厂认证',
        '实力认证',
        '官方物流',
        '密文面单',
        '抖音面单',
      ];
      const chips = [];
      for (const el of Array.from(document.querySelectorAll('div, span, button, label'))) {
        const text = normalize(el.innerText || el.textContent || '');
        if (!text || text.length > 80) continue;
        const matched = knownTerms.filter((term) => text.includes(term));
        if (!matched.length) continue;
        if (!/[×xX]|close|已选|指定|筛选|条件|面单/.test(text) && matched.length === 1) continue;
        chips.push(text);
      }
      return Array.from(new Set(chips)).slice(0, 30);
    }
    """
    try:
        return await page.evaluate(script) or []
    except Exception as exc:
        if logger:
            logger.warning(f"[Search] Failed to extract selected filter chips: {exc}")
        return []


def _unexpected_selected_filter_chips(selected_filter_chips: list[str], runtime_filter_snapshot: dict | None) -> list[str]:
    configured_keys = set((runtime_filter_snapshot or {}).get("configured_enabled_filter_keys") or [])
    configured_labels = {
        get_ali1688_channel_search_filter_meta(key).get("label")
        for key in configured_keys
    }
    configured_labels = {str(label) for label in configured_labels if label}
    known_labels = {
        str(get_ali1688_channel_search_filter_meta(key).get("label") or "")
        for key in get_ali1688_channel_search_filter_keys()
    }
    known_labels.update({"抖音面单"})
    known_labels.discard("")

    unexpected = []
    for chip in selected_filter_chips or []:
        chip_text = str(chip or "").strip()
        if not chip_text:
            continue
        matched = [label for label in known_labels if label and label in chip_text]
        if any(label not in configured_labels for label in matched):
            unexpected.append(chip_text)
    return list(dict.fromkeys(unexpected))


def _write_search_result_snapshots(
    output_dir: Path,
    html_content: str,
    candidates: list,
    visual_order_map: dict[str, int],
    visual_rows: list[dict] | None = None,
    result_url: str = "",
    runtime_filter_snapshot: dict | None = None,
    selected_filter_chips: list[str] | None = None,
    unexpected_selected_filter_chips: list[str] | None = None,
    visible_snapshot_file: str = "",
    logger=None,
) -> None:
    try:
        raw_html_file = output_dir / "search_result_page.html"
        raw_html_file.write_text(html_content, encoding="utf-8")
    except Exception as exc:
        if logger:
            logger.warning(f"[Search] Failed to save raw search HTML: {exc}")

    rows = []
    for adapter_index, candidate in enumerate(candidates, start=1):
        offer_id = str(candidate.source_item_id or "")
        rows.append({
            "visual_index": visual_order_map.get(offer_id),
            "adapter_index": adapter_index,
            "offer_id": offer_id,
            "title": candidate.title or "",
            "price": candidate.price,
            "shop_name": candidate.shop_name or "",
            "item_url": candidate.item_url or "",
        })
    rows.sort(key=lambda row: (row["visual_index"] or row["adapter_index"], row["adapter_index"]))

    try:
        json_file = output_dir / "search_result_order_snapshot.json"
        snapshot_context = {
            "result_url": result_url,
            "visible_snapshot_file": visible_snapshot_file,
            "runtime_filter_stage": (runtime_filter_snapshot or {}).get("stage"),
            "configured_enabled_filter_keys": (runtime_filter_snapshot or {}).get("configured_enabled_filter_keys") or [],
            "applied_filter_keys": (runtime_filter_snapshot or {}).get("applied_filter_keys") or [],
            "unapplied_filter_keys": (runtime_filter_snapshot or {}).get("unapplied_filter_keys") or [],
            "selected_filter_chips": selected_filter_chips or [],
            "unexpected_selected_filter_chips": unexpected_selected_filter_chips or [],
        }
        snapshot_payload = {
            "context": snapshot_context,
            "live_rows": visual_rows or [],
            "rows": rows,
        }
        json_file.write_text(json.dumps(snapshot_payload, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception as exc:
        if logger:
            logger.warning(f"[Search] Failed to save search order JSON snapshot: {exc}")

    try:
        live_table_rows = "\n".join(
            "<tr>"
            f"<td>{index}</td>"
            f"<td>{html.escape(str((row or {}).get('offerId') or ''))}</td>"
            f"<td>{html.escape(str((row or {}).get('title') or ''))}</td>"
            f"<td>{html.escape(str((row or {}).get('text') or ''))}</td>"
            "</tr>"
            for index, row in enumerate(visual_rows or [], start=1)
        )
        table_rows = "\n".join(
            "<tr>"
            f"<td>{html.escape(str(row['visual_index'] or ''))}</td>"
            f"<td>{html.escape(str(row['adapter_index']))}</td>"
            f"<td>{html.escape(row['offer_id'])}</td>"
            f"<td><a href=\"{html.escape(row['item_url'])}\" target=\"_blank\">{html.escape(row['title'])}</a></td>"
            f"<td>{html.escape(str(row['price'] or ''))}</td>"
            f"<td>{html.escape(row['shop_name'])}</td>"
            "</tr>"
            for row in rows
        )
        filter_context = runtime_filter_snapshot or {}
        context_rows = "\n".join(
            "<tr>"
            f"<th>{html.escape(label)}</th>"
            f"<td>{html.escape(str(value or ''))}</td>"
            "</tr>"
            for label, value in [
                ("结果 URL", result_url),
                ("可视截图", visible_snapshot_file),
                ("筛选阶段", filter_context.get("stage")),
                ("配置筛选项", ", ".join(filter_context.get("configured_enabled_filter_keys") or [])),
                ("已应用筛选项", ", ".join(filter_context.get("applied_filter_keys") or [])),
                ("未应用筛选项", ", ".join(filter_context.get("unapplied_filter_keys") or [])),
                ("页面选中筛选 Chip", " | ".join(selected_filter_chips or [])),
                ("异常选中筛选 Chip", " | ".join(unexpected_selected_filter_chips or [])),
            ]
        )
        snapshot_html = f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <title>1688 搜索结果解析快照</title>
  <style>
    body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; margin: 24px; color: #1f2937; }}
    table {{ border-collapse: collapse; width: 100%; }}
    th, td {{ border: 1px solid #d8dee9; padding: 8px 10px; text-align: left; vertical-align: top; }}
    th {{ background: #f3f4f6; }}
    tr:nth-child(even) {{ background: #fafafa; }}
    a {{ color: #b83212; text-decoration: none; }}
    .note {{ color: #6b7280; margin-bottom: 16px; }}
    .context {{ margin-bottom: 24px; }}
    .context th {{ width: 160px; }}
  </style>
</head>
<body>
  <h1>1688 搜索结果解析快照</h1>
  <p class="note">这是系统从搜索页 HTML/DOM 中解析出的商品顺序。原始 HTML 保存在 search_result_page.html；实时可见 DOM 行用于校验浏览器当时的真实展示顺序。</p>
  <h2>抓取上下文</h2>
  <table class="context">
    <tbody>{context_rows}</tbody>
  </table>
  <h2>实时可见 DOM 顺序</h2>
  <table>
    <thead>
      <tr>
        <th>实时 index</th>
        <th>Offer ID</th>
        <th>标题</th>
        <th>可见文本摘要</th>
      </tr>
    </thead>
    <tbody>{live_table_rows}</tbody>
  </table>
  <h2>适配器解析结果</h2>
  <table>
    <thead>
      <tr>
        <th>视觉 index</th>
        <th>适配器 index</th>
        <th>Offer ID</th>
        <th>标题</th>
        <th>价格</th>
        <th>商家</th>
      </tr>
    </thead>
    <tbody>{table_rows}</tbody>
  </table>
</body>
</html>
"""
        snapshot_file = output_dir / "search_result_order_snapshot.html"
        snapshot_file.write_text(snapshot_html, encoding="utf-8")
        if logger:
            logger.info(f"[Search] Saved search result snapshots to {output_dir}")
    except Exception as exc:
        if logger:
            logger.warning(f"[Search] Failed to save search order HTML snapshot: {exc}")


def _detail_offer_id_from_url(url: str) -> str:
    if not url:
        return ""
    match = re.search(r'/offer/(\d+)\.html', url)
    if match:
        return match.group(1)
    return ""


def _find_key_recursive(obj, target_key):
    if isinstance(obj, dict):
        if target_key in obj: return obj[target_key]
        for v in obj.values():
            res = _find_key_recursive(v, target_key)
            if res: return res
    elif isinstance(obj, list):
        for item in obj:
            res = _find_key_recursive(item, target_key)
            if res: return res
    return None

def _clean_image_url(url: str) -> str:
    """
    1688 高清大图清洗逻辑：
    1. 过滤掉所有视频文件和视频帧、封面图片资源（包含video、.mp4等特征）
    2. 允许任何合法的阿里 CDN 图片或常见图像后缀直接通过
    3. 使用正则过滤掉缩略图的裁剪尺寸并还原为原始大图
    4. 过滤掉所有不以合法图片后缀结尾的非图资源链接
    """
    if not url or not isinstance(url, str): return ""
    
    # 补全协议
    if url.startswith("//"): url = "https:" + url
    elif not url.startswith("http"): url = "https://" + url

    url_lower = url.lower()
    # 视频过滤：包含 video 关键字或视频文件类型，直接丢弃
    video_keywords = ["video", ".mp4", ".avi", ".mov", ".flv", "/video"]
    if any(kw in url_lower for kw in video_keywords):
        return ""

    # 基础过滤：必须为阿里 CDN 图片或常见的图片后缀
    if "alicdn.com" not in url_lower and not any(ext in url_lower for ext in [".jpg", ".jpeg", ".png"]):
        return ""

    # 清除 1688 / 淘宝 CDN 常见的缩略图和压缩后缀
    # 比如：.jpg_300x300.jpg -> .jpg
    #      .png_.webp -> .png
    #      .jpeg_q90.jpg -> .jpeg
    url = re.sub(r'\.([a-zA-Z]+)_[^/\\]+$', r'.\1', url)
    
    # 最终验证：必须是以常见的图片扩展名结尾
    if not any(url.lower().endswith(ext) for ext in [".jpg", ".jpeg", ".png"]):
        return ""
        
    return url

def _sanitize_cookies(cookies):
    """清洗 Cookie 字段，防止 Playwright 报错"""
    allowed_fields = {"name", "value", "url", "domain", "path", "expires", "httpOnly", "secure", "sameSite"}
    clean_list = []
    for c in cookies:
        item = {k: v for k, v in c.items() if k in allowed_fields}
        if "sameSite" in item and item["sameSite"] not in ["Strict", "Lax", "None"]:
            del item["sameSite"]
        clean_list.append(item)
    return clean_list

def is_relevant(source_title, search_keyword):
    if not source_title: return False, "标题为空"
    s_title, t_kw = str(source_title).lower(), str(search_keyword).lower()
    clean_keyword = re.sub(r'\s+', '', t_kw)
    if clean_keyword in s_title: return True, ""
    core_parts = [clean_keyword[:2], clean_keyword[-2:], clean_keyword[1:3]]
    for part in core_parts:
        if len(part) >= 2 and part in s_title: return True, ""
    return False, f"不含关键词 '{clean_keyword}'"


def _clean_html_span(text: str) -> str:
    if not text: return ""
    text = re.sub(r'<span[^>]*?>.*?</span>', '', text, flags=re.IGNORECASE | re.DOTALL)
    text = re.sub(r'<[^>]+>', '', text)
    parts = [p.strip() for p in text.split(";") if p.strip()]
    return ";".join(parts)


def _parse_captured_api_data(captured_responses: list[dict], logger):
    parsed_result = {"sku_details": [], "images": []}
    for resp in captured_responses:
        data = resp.get("data", {})
        # SKU
        for key in ["skuInfoMap", "skuProps"]:
            info_map = _find_key_recursive(data, key)
            if info_map and not parsed_result["sku_details"] and isinstance(info_map, dict):
                for attr_name, info in info_map.items():
                    parsed_result["sku_details"].append({
                        "attributes": _clean_html_span(html.unescape(str(attr_name))).replace(">", " - "),
                        "price": info.get("discountPrice") or info.get("price"),
                        "stock": info.get("canBookCount"),
                        "spec_id": info.get("specId")
                    })
        # Images
        for key in ["imageList", "images", "mainImages"]:
            image_list = _find_key_recursive(data, key)
            if image_list and isinstance(image_list, list) and not parsed_result["images"]:
                for img in image_list:
                    u = None
                    if isinstance(img, str): u = img
                    elif isinstance(img, dict): u = img.get("fullPathImageURI") or img.get("originalImageUri") or img.get("url")
                    if u:
                        cleaned = _clean_image_url(str(u))
                        if cleaned: parsed_result["images"].append(cleaned)
                if parsed_result["images"]: break
    return parsed_result

async def _clean_page_overlays(page, logger):
    for i in range(5):
        try:
            # 尝试主动查找并关闭常见的新手引导/确认弹窗按钮
            for btn_text in ["我知道了", "我知道啦", "跳过", "下一步", "关闭"]:
                try:
                    btn = page.get_by_text(btn_text).first
                    if await btn.count() > 0 and await btn.is_visible():
                        logger.info(f"    [Overlay] Clicking onboarding guide button: {btn_text}")
                        await btn.click()
                        await asyncio.sleep(1)
                except Exception:
                    pass

            state = await _overlay_state(page)
            if state["overlay_count"] == 0 and not state["ack_visible"]:
                # 再通过注入JS移除任何残留的新手指引蒙层
                try:
                    await page.evaluate("""
                        () => {
                            const selectors = ['.next-guide-mask', '.guide-mask', '[class*="guide-mask"]', '[class*="next-guide"]', '.introjs-overlay', '.introjs-helperLayer'];
                            selectors.forEach(sel => {
                                document.querySelectorAll(sel).forEach(el => el.remove());
                            });
                        }
                    """)
                except Exception:
                    pass
                break
            
            logger.info(f"    [Overlay] Found {state['overlay_count']} overlays, ack_visible: {state['ack_visible']}. Cleaning...")
            
            if state["ack_visible"]:
                ack_btn = page.get_by_text("我知道了", exact=True).first
                if await ack_btn.is_visible():
                    await ack_btn.click()
                    await asyncio.sleep(1)
                    continue
                    
            overlay_loc = page.locator(".J_MIDDLEWARE_FRAME_WIDGET:visible").first
            if await overlay_loc.count() > 0:
                rect = await overlay_loc.bounding_box()
                if rect:
                    cx, cy = _overlay_close_click_point(rect)
                    await page.mouse.click(cx, cy)
                    await asyncio.sleep(1)
                    continue
        except Exception as oe:
            logger.warning(f"    [Overlay] Clean error: {oe}")
            break


def _log_slider_step(logger, payload: dict):
    if logger:
        logger.info(f"    [Slider] {payload.get('step')}: {json.dumps(payload, ensure_ascii=False)}")
    else:
        print(json.dumps(payload, ensure_ascii=False), flush=True)


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


async def _drag_slider_system_mouse(page, frame, locator, logger=None) -> bool:
    if pyautogui is None:
        _log_slider_step(logger, {"step": "pyautogui_not_available"})
        return False
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
        eased = progress * progress
        target_x = start_x + total_distance * eased
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


def _looks_like_login_url(url: str) -> bool:
    """检查 URL 是否是登录页（同步函数，不可用 async，否则调用处不加 await 会变成 truthy coroutine）"""
    lowered = url.lower()
    return any(token in lowered for token in ["login.taobao.com", "login.1688.com", "member/modify_evolve"])


def _looks_like_captcha_page(url: str, title: str) -> bool:
    """检查当前页是否为验证码拦截页"""
    url_l = url.lower()
    captcha_url_tokens = ["_____tmd_____/punish", "punish", "sec.taobao.com", "login.taobao.com", "login.1688.com"]
    captcha_title_tokens = ["验证码", "安全验证", "访问被拒绝", "拦截"]
    if any(t in url_l for t in captcha_url_tokens):
        return True
    if any(t in title for t in captcha_title_tokens):
        return True
    return False


async def _wait_for_search_or_slider(page, timeout_seconds: float = 8.0) -> str:
    """等待页面进入搜索框、滑块或登录页状态之一。
    注意：_looks_like_login_url 必须是同步调用，不能 await。"""
    deadline = asyncio.get_running_loop().time() + timeout_seconds
    while asyncio.get_running_loop().time() < deadline:
        cur_url = page.url
        if _looks_like_login_url(cur_url):
            return "login"
        if await _slider_still_present(page):
            return "slider"
        if await _search_input_locator(page) is not None:
            return "search"
        await asyncio.sleep(0.2)
    return "unknown"


async def _clear_home_slider(page, stage: str = "home", logger=None) -> bool:
    for attempt in range(1, 2):
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
                    _log_slider_step(logger, {"step": "slider_retry_click", "attempt": attempt, "frame_url": frame.url})
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
                        _log_slider_step(logger, {
                            "step": "slider_pre_reset",
                            "attempt": attempt,
                            "frame_url": frame.url,
                            "handle_x": handle_x,
                            "track_x": track_x,
                        })
                        await asyncio.sleep(0.5)
                        slider = await _find_slider_control(frame)
                        if slider is None:
                            continue
                        slider_identity = await slider.evaluate("node => node.className || node.id || node.tagName")
                        geometry = await _read_slider_geometry(slider, frame, page)

                drag_success = False
                if pyautogui is not None:
                    drag_success = await _drag_slider_system_mouse(page, frame, slider, logger=logger)
                
                if not drag_success:
                    _log_slider_step(logger, {"step": "falling_back_to_playwright_drag"})
                    drag_success = await _drag_slider_track(slider)

                if drag_success:
                    _log_slider_step(logger, {
                        "step": "slider_dragged",
                        "attempt": attempt,
                        "mode": "system_mouse" if drag_success and pyautogui is not None else "playwright_track",
                        "selector": slider_identity,
                        "frame_url": frame.url,
                    })
                    await asyncio.sleep(0.8)
                    hidden_state = await _read_slider_hidden_state(page)
                    visual_state = await _read_slider_visual_state(page)
                    _log_slider_step(logger, {"step": "slider_hidden_state", "attempt": attempt, "state": hidden_state})
                    _log_slider_step(logger, {"step": "slider_visual_state", "attempt": attempt, "state": visual_state})
                    passed = await _slider_verification_passed(page)
                    _log_slider_step(logger, {"step": "slider_verify", "attempt": attempt, "passed": passed})
                    if passed:
                        return True
                    if frame_box is not None:
                        await _click_slider_frame(frame_box)
                        _log_slider_step(logger, {"step": "slider_retry_click", "attempt": attempt, "frame_url": frame.url})
                        await asyncio.sleep(0.4)
            except Exception as exc:
                _log_slider_step(logger, {
                    "step": "slider_drag_error",
                    "attempt": attempt,
                    "frame_url": frame.url,
                    "error": f"{type(exc).__name__}: {exc}",
                })
        await asyncio.sleep(0.8)
    return False


async def _clear_slider_if_present(page, stage: str, logger=None) -> bool:
    """检测并清除滑块验证。对于验证码拦截页，直接尝试解滑块而不是立即放弃。"""
    state = await _wait_for_search_or_slider(page)
    _log_slider_step(logger, {"step": "slider_stage_state", "stage": stage, "state": state})
    if state == "search":
        _log_slider_step(logger, {"step": "slider_not_present", "stage": stage})
        return True
    if state == "login":
        # 真正的登录页（URL 含 login.taobao.com 等），无法自动处理
        _log_slider_step(logger, {"step": "login_redirect_detected", "stage": stage, "url": page.url})
        return False
    # state == "slider" 或 "unknown"：尝试清除滑块
    passed = await _clear_home_slider(page, stage=stage, logger=logger)
    _log_slider_step(logger, {"step": "slider_stage_ready", "stage": stage, "passed": passed})
    return passed


async def _wait_for_manual_verification(page, logger, *, timeout_seconds: int) -> bool:
    deadline = asyncio.get_running_loop().time() + max(0, int(timeout_seconds))
    while asyncio.get_running_loop().time() < deadline:
        try:
            cur_url = page.url
            cur_title = await page.title() or ""
        except Exception as page_state_err:
            error_text = str(page_state_err)
            if "Execution context was destroyed" in error_text:
                await asyncio.sleep(2)
                continue
            logger.error(f"    [Session] Page unavailable while waiting for manual verification: {page_state_err}")
            return False
        if not _looks_like_captcha_page(cur_url, cur_title):
            logger.info("    [Session] Manual verification completed.")
            return True
        await asyncio.sleep(2)
    logger.error("    [Session] Timeout waiting for manual verification.")
    return False


async def _ensure_page_navigated_safe(
    page,
    url: str,
    logger,
    timeout: int = 30000,
    *,
    manual_verification_wait_seconds: int = 0,
) -> bool:
    logger.info(f"    [Session] Navigating to: {url}")
    try:
        await page.goto(url, wait_until="domcontentloaded", timeout=timeout)
        await asyncio.sleep(2)
    except Exception as e:
        logger.warning(f"    [Session] Initial navigation warning: {e}")

    for attempt in range(1):  # 一次自动验证窗口，避免验证码循环长期占用资源
        try:
            cur_url = page.url
            cur_title = await page.title() or ""
        except Exception as page_state_err:
            logger.error(f"    [Session] Page unavailable while checking navigation state: {page_state_err}")
            return False
        
        is_blocked = _looks_like_captcha_page(cur_url, cur_title)
        
        if not is_blocked:
            return True
            
        logger.warning(f"    [Session] [Blocked] Captcha or login redirect detected! URL: {cur_url}, Title: {cur_title}")

        if manual_verification_wait_seconds > 0:
            logger.warning(
                "    [Action Required] Please complete captcha/login in the visible browser window."
            )
            return await _wait_for_manual_verification(
                page,
                logger,
                timeout_seconds=manual_verification_wait_seconds,
            )
        
        # 先清理采购助手欢迎页/新手引导弹窗，它们可能遮住验证码滑块
        try:
            logger.info("    [Session] Dismissing any procurement assistant welcome popups before slider detection...")
            await _clean_page_overlays(page, logger)
            await asyncio.sleep(0.5)
        except Exception as pe:
            logger.warning(f"    [Session] Popup dismiss error (non-fatal): {pe}")

        # 尝试自动滑动解锁（先检测当前页是否有滑块）
        try:
            slider_present = await _slider_still_present(page)
            if slider_present:
                logger.info("    [Session] Slider detected on captcha page. Attempting to drag...")
                passed = await _clear_home_slider(page, stage="navigation", logger=logger)
                if passed:
                    logger.info("    [Session] Slider cleared! Waiting for redirect...")
                    await asyncio.sleep(3)
                    continue
                else:
                    logger.warning("    [Session] Slider drag failed. Will wait for manual resolve...")
            else:
                logger.warning("    [Session] No slider detected on captcha page. Waiting for manual resolve...")
        except Exception as se:
            logger.error(f"    [Session] Auto slider clearing encountered error: {se}")

        logger.warning("    [Action Required] Please solve the captcha or scan code to log in manually in the browser window!")
        await asyncio.sleep(2)
        
    logger.error("    [Session] Timeout waiting for verification bypass.")
    return False



async def _export_sku_from_detail_page(
    context,
    item: dict,
    output_dir: Path,
    index: int,
    logger,
    *,
    manual_verification_wait_seconds: int = 0,
):
    safe_title = _sanitize_filename(item.get("title") or "item")
    offer_id = item.get("offer_id")
    
    captured = []
    async def on_resp(res):
        try:
            if "mtop" in res.url.lower():
                text = await res.text()
                if "(" in text: text = re.search(r"\((.*)\)", text, re.DOTALL).group(1)
                captured.append({"url": res.url, "data": json.loads(text)})
        except: pass

    page = await context.new_page()
    page.on("response", on_resp)
    
    physical_success = False
    
    try:
        url = f"https://detail.1688.com/offer/{offer_id}.html"
        logger.info(f"    [Step 2/4] Navigating to detail page: {url}")
            
        success = await _ensure_page_navigated_safe(
            page,
            url,
            logger,
            timeout=60000,
            manual_verification_wait_seconds=manual_verification_wait_seconds,
        )
        if not success:
            logger.error(f"    [Session] Detail page navigation failed Rank {index}")
            return {"status": "failed", "images": []}

        # 等待页面渲染（JS 执行、图片懒加载触发）
        await page.evaluate("window.scrollTo(0, 400)")
        await asyncio.sleep(3)

        # 清除可能弹出的新手引导/欢迎弹窗
        await _clean_page_overlays(page, logger)

        # ── 核心：直接取完整渲染后的 HTML，用 Scrapling 解析 ──
        logger.info("    [HTML] Fetching rendered page HTML for Scrapling parsing...")
        html_content = await page.content()

        # 保存原始 HTML 到本地 detail_{offer_id}.html
        html_file = output_dir / f"detail_{offer_id}.html"
        try:
            html_file.write_text(html_content, encoding="utf-8")
            logger.info(f"    [HTML] Saved raw page HTML to {html_file}")
        except Exception as html_err:
            logger.warning(f"    [HTML] Failed to save raw HTML (non-fatal): {html_err}")

        parsed_html = Ali1688SourceAdapter.extract_detail_sku_and_images(html_content)
        logger.info(f"    [HTML] Scrapling parsed: {len(parsed_html['sku_details'])} SKU entries, {len(parsed_html['images'])} images")
        detail_metrics = _extract_dispatch_metrics_from_text(html_content)

        # ── 补充：从 JS 运行时直接读取 SKU（比 HTML 正则更可靠）──
        js_sku: list = []
        js_images: list = []
        try:
            js_data = await page.evaluate("""
                () => {
                    const result = {sku: [], images: []};
                    // 1. 尝试各种全局变量
                    const candidates = [
                        window.__INIT_DATA__,
                        window.detailData,
                        window.__GLOBAL_DATA__,
                        window.context?.result?.data,
                    ];
                    for (const root of candidates) {
                        if (!root || typeof root !== 'object') continue;
                        // 递归搜索 skuInfoMap
                        function findKey(obj, key, depth) {
                            if (depth > 8 || !obj || typeof obj !== 'object') return null;
                            if (obj[key] !== undefined) return obj[key];
                            for (const v of Object.values(obj)) {
                                const found = findKey(v, key, depth + 1);
                                if (found !== null && found !== undefined) return found;
                            }
                            return null;
                        }
                        
                        function cleanSpan(valStr) {
                            if (!valStr || typeof valStr !== 'string') return valStr;
                            let temp = valStr.replace(/<span[^>]*?>.*?<\/span>/gi, '');
                            temp = temp.replace(/<[^>]+>/g, '');
                            const parts = temp.split(';').map(p => p.trim()).filter(Boolean);
                            return parts.join(';');
                        }
                        
                        // 提取规格属性图片映射
                        const skuProps = findKey(root, 'skuProps', 0);
                        const propImages = {};
                        if (Array.isArray(skuProps)) {
                            for (const prop of skuProps) {
                                if (Array.isArray(prop.value)) {
                                    for (const val of prop.value) {
                                        if (val.name && val.imageUrl) {
                                            const cleanedValName = cleanSpan(val.name);
                                            propImages[cleanedValName] = val.imageUrl;
                                        }
                                    }
                                }
                            }
                        }
                        
                        function matchImage(attributes) {
                            if (!attributes) return null;
                            const cleanedAttrs = cleanSpan(attributes);
                            const attrParts = cleanedAttrs.split(';');
                            for (const part of attrParts) {
                                const valName = part.includes(':') ? part.split(':')[1] : part;
                                if (propImages[valName.trim()]) return propImages[valName.trim()];
                            }
                            return null;
                        }

                        // SKU map
                        const skuMap = findKey(root, 'skuInfoMap', 0);
                        if (skuMap && typeof skuMap === 'object' && Object.keys(skuMap).length > 0) {
                            for (const [name, info] of Object.entries(skuMap)) {
                                result.sku.push({
                                    attributes: cleanSpan(name),
                                    price: info.discountPrice || info.price || null,
                                    stock: info.canBookCount || null,
                                    spec_id: info.specId || null,
                                    image: matchImage(name),
                                    source: 'js_runtime_skuInfoMap'
                                });
                            }
                            break;
                        }
                        // skuList / skuInfos
                        const skuList = findKey(root, 'skuInfos', 0) || findKey(root, 'skuList', 0);
                        if (Array.isArray(skuList) && skuList.length > 0) {
                            for (const sku of skuList) {
                                const attrs = sku.attributes || sku.specName || sku.skuName || '';
                                result.sku.push({
                                    attributes: cleanSpan(attrs),
                                    price: sku.discountPrice || sku.price || null,
                                    stock: sku.canBookCount || sku.stock || null,
                                    spec_id: sku.specId || sku.skuId || null,
                                    image: matchImage(attrs),
                                    source: 'js_runtime_skuList'
                                });
                            }
                            break;
                        }
                        // 图片
                        const imgList = findKey(root, 'imageList', 0);
                        if (Array.isArray(imgList)) {
                            for (const img of imgList) {
                                const u = (typeof img === 'string') ? img
                                    : img.fullPathImageURI || img.originalImageUri || img.url || '';
                                if (u && u.includes('alicdn.com')) result.images.push(u);
                            }
                        }
                    }
                    return result;
                }
            """)
            js_sku = js_data.get("sku", [])
            js_images = js_data.get("images", [])
            logger.info(f"    [JS] Runtime extracted: {len(js_sku)} SKU entries, {len(js_images)} images")
        except Exception as je:
            logger.warning(f"    [JS] Runtime eval error (non-fatal): {je}")

        # mtop API 拦截数据作为兜底补充
        parsed_api = _parse_captured_api_data(captured, logger)

        # 合并 SKU：优先 JS 运行时 > HTML 解析 > API 拦截
        sku_details = js_sku or parsed_html["sku_details"] or parsed_api["sku_details"]

        # 合并图片：DOM 求值 + HTML 解析 + JS 运行时 + API 拦截（四层）
        dom_images: list = []
        try:
            dom_images = await page.evaluate("""
                () => {
                    const list = [];
                    const gallery = document.querySelector(
                        '.module-od-picture-gallery, .detail-gallery, .od-gallery-list-wapper'
                    );
                    if (gallery) {
                        gallery.querySelectorAll('img').forEach(img => {
                            let src = img.getAttribute('data-lazyload-src') || img.getAttribute('src') || img.src;
                            if (src && src.includes('alicdn.com')) list.push(src);
                        });
                    }
                    return [...new Set(list)];
                }
            """)
        except Exception as de:
            logger.warning(f"    [HTML] DOM image eval error (non-fatal): {de}")

        all_images = dom_images + parsed_html["images"] + js_images + parsed_api["images"]
        clean_final = list(dict.fromkeys([_clean_image_url(u) for u in all_images if u]))
        clean_final = list(filter(None, clean_final))[:9]

        # 清洗 SKU 规格属性
        if sku_details:
            for sku in sku_details:
                if sku.get("attributes"):
                    sku["attributes"] = _clean_html_span(sku["attributes"])

        if sku_details or clean_final:
            logger.info(f"    [Step 4/4] Success! Extracted SKUs: {len(sku_details)}, Images: {len(clean_final)}")
            return {"status": "success", "images": clean_final, "sku_details": sku_details, **detail_metrics}
            
    except Exception as e:
        logger.error(f"    [Browser Error] Rank {index}: {e}")
    finally:
        await page.close()
        
    return {"status": "failed", "images": [], "sku_details": []}


async def _run(args):
    manual_verification_wait_seconds = max(
        0,
        int(getattr(args, "manual_verification_wait_seconds", 0) or 0),
    )
    configured_filter_snapshot = _load_channel_filter_snapshot(
        getattr(args, "channel_filter_snapshot_file", None)
    )
    runtime_filter_snapshot = _build_runtime_filter_snapshot(configured_filter_snapshot)
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    logger = get_unified_logger("1688Worker", log_file=args.log_file)
    runtime_filter_snapshot = _write_runtime_filter_snapshot_audit(
        output_dir,
        runtime_filter_snapshot,
        stage="initialized",
        logger=logger,
    )
    
    input_state = args.state_file
    managed_state = DEFAULT_ALI1688_STATE_FILE
    effective_state_path, synced = _prepare_managed_state_file(input_state, managed_state)
    if synced:
        logger.info(f"[Auth] Synced input state {input_state} to managed state {effective_state_path}")
    else:
        logger.info(f"[Auth] Using managed state {managed_state} (synced=False)")

    state_file_to_save = effective_state_path or managed_state

    async with async_playwright() as pw:
        options = default_desktop_context_options()
        options["user_agent"] = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"

        # 已去掉浏览器扩展依赖（SKU 改用 JS 运行时提取），默认 headless；需要人工验证码时可用 --headed。
        headless_args = [
            *default_launch_args(),
            "--disable-blink-features=AutomationControlled",
            "--no-sandbox",
        ]
        logger.info(
            "[Browser] Launching %s Chromium (no extension required)",
            "headed" if getattr(args, "headed", False) else "headless",
        )
        browser = await pw.chromium.launch(
            headless=not bool(getattr(args, "headed", False)),
            args=headless_args,
        )
        context = await browser.new_context(**options)

        await context.add_init_script("Object.defineProperty(navigator, 'webdriver', { get: () => undefined })")

        # 注入全局新手引导弹窗自动关闭脚本（MutationObserver 持续监听）
        await context.add_init_script("""
        (function() {
            const GUIDE_CLOSE_TEXTS = ['我知道了', '我知道啦', '跳过', '关闭', '跳过引导', '跳过新手引导', '完成'];
            const GUIDE_SELECTORS = [
                '.next-guide-mask', '.guide-mask', '[class*="guide-mask"]',
                '[class*="next-guide"]', '.introjs-overlay', '.introjs-helperLayer',
                '.introjs-tooltipReferenceLayer',
            ];

            function tryDismissGuide() {
                // 1. 点击关闭按钮
                for (const text of GUIDE_CLOSE_TEXTS) {
                    const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
                    let node;
                    while ((node = walker.nextNode())) {
                        if (node.nodeValue && node.nodeValue.trim() === text) {
                            const el = node.parentElement;
                            if (el && el.offsetParent !== null) {
                                try { el.click(); } catch(e) {}
                                break;
                            }
                        }
                    }
                }
                // 2. 移除残留蒙层 DOM
                for (const sel of GUIDE_SELECTORS) {
                    document.querySelectorAll(sel).forEach(el => {
                        try { el.remove(); } catch(e) {}
                    });
                }
            }

            // 首次执行
            if (document.readyState === 'loading') {
                document.addEventListener('DOMContentLoaded', tryDismissGuide);
            } else {
                tryDismissGuide();
            }

            // 持续监听 DOM 变化
            const observer = new MutationObserver(() => { tryDismissGuide(); });
            observer.observe(document.documentElement, { childList: true, subtree: true });
        })();
        """)

        if state_file_to_save and Path(state_file_to_save).exists():
            await _apply_state_file_cookies(context, state_file_to_save)
            logger.info(f"[Auth] Injected cookies from {state_file_to_save}")
        await _clear_extension_onboarding_state(context)

        # 1. 下载远程图片到本地临时目录
        import urllib.request
        temp_img_path = output_dir / "temp_search.jpg"
        logger.info(f"[Search] Downloading remote image for physical upload: {args.image_url}")
        try:
            req = urllib.request.Request(
                args.image_url, 
                headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"}
            )
            with urllib.request.urlopen(req, timeout=15) as response:
                temp_img_path.write_bytes(response.read())
            logger.info(f"[Search] Remote image successfully downloaded to {temp_img_path}")
        except Exception as dl_err:
            logger.error(f"[Search] Image download failed: {dl_err}")
            runtime_filter_snapshot = _write_runtime_filter_snapshot_audit(
                output_dir,
                runtime_filter_snapshot,
                stage="image_download_failed",
                logger=logger,
                extra={"error": str(dl_err)},
            )
            await context.close()
            return

        # 2. 导航至 1688 主页进行全域安全会话激活
        logger.info("[Search] Pre-warming browser context by visiting 1688 homepage...")
        page = await context.new_page()
        success = await _ensure_page_navigated_safe(
            page,
            "https://www.1688.com",
            logger,
            timeout=60000,
            manual_verification_wait_seconds=manual_verification_wait_seconds,
        )
        if not success:
            logger.error("[Search] Failed to pre-warm on 1688 homepage.")
            runtime_filter_snapshot = _mark_runtime_filter_snapshot_navigation_blocked(
                runtime_filter_snapshot,
                stage="prewarm_failed",
                url=page.url,
            )
            runtime_filter_snapshot = _write_runtime_filter_snapshot_audit(
                output_dir,
                runtime_filter_snapshot,
                stage="prewarm_failed",
                logger=logger,
            )
            await context.close()
            return
        await asyncio.sleep(4)

        # 3. 导航至以图搜主页（空参数，有 Referer 且已同步 cookie，安全）
        search_home_url = "https://s.1688.com/youyuan/index.htm"
        success = await _ensure_page_navigated_safe(
            page,
            search_home_url,
            logger,
            timeout=60000,
            manual_verification_wait_seconds=manual_verification_wait_seconds,
        )
        if not success:
            logger.error("[Search] Failed to open image search home page.")
            runtime_filter_snapshot = _mark_runtime_filter_snapshot_navigation_blocked(
                runtime_filter_snapshot,
                stage="image_search_home_failed",
                url=page.url,
            )
            runtime_filter_snapshot = _write_runtime_filter_snapshot_audit(
                output_dir,
                runtime_filter_snapshot,
                stage="image_search_home_failed",
                logger=logger,
            )
            await context.close()
            return
        await asyncio.sleep(3)

        # 3. 定位文件输入框并模拟上传
        upload_success = False
        try:
            logger.info("[Search] Locating file input elements...")
            # 匹配 input type="file" 或 accept 包含 image 的节点
            input_loc = page.locator('input[type="file"], input[accept*="image"], .upload-btn input').first
            if await input_loc.count() > 0:
                await input_loc.set_input_files(str(temp_img_path))
                logger.info("[Search] File selected and uploaded physically. Waiting for auto-redirection...")
                # 等待 URL 发生改变，跳转到结果页面
                await page.wait_for_url(lambda url: "imageAddress=" in url or "tab=imageSearch" in url, timeout=25000)
                logger.info(f"[Search] Successfully redirected to results page: {page.url}")
                await asyncio.sleep(5)
                upload_success = True
            else:
                logger.warning("[Search] No upload input element found on the home page.")
        except Exception as upload_err:
            logger.error(f"[Search] Physical upload failed or redirection timeout: {upload_err}")
            if "Target page, context or browser has been closed" in str(upload_err):
                runtime_filter_snapshot = _write_runtime_filter_snapshot_audit(
                    output_dir,
                    runtime_filter_snapshot,
                    stage="image_upload_page_closed",
                    logger=logger,
                    extra={"error": str(upload_err)},
                )
                try:
                    await context.close()
                except Exception:
                    pass
                return

        # 4. 兜底方案：如果物理上传失败，则直连以图搜 URL
        if not upload_success:
            from urllib.parse import quote
            search_url = f"https://s.1688.com/youyuan/index.htm?tab=imageSearch&imageAddress={quote(args.image_url)}"
            logger.warning(f"[Search] Falling back to direct URL visit: {search_url}")
            success = await _ensure_page_navigated_safe(
                page,
                search_url,
                logger,
                timeout=60000,
                manual_verification_wait_seconds=manual_verification_wait_seconds,
            )
            if not success:
                logger.error("[Search] Direct URL fallback failed. Captcha unsolved.")
                runtime_filter_snapshot = _mark_runtime_filter_snapshot_navigation_blocked(
                    runtime_filter_snapshot,
                    stage="direct_url_fallback_failed",
                    url=page.url,
                )
                runtime_filter_snapshot = _write_runtime_filter_snapshot_audit(
                    output_dir,
                    runtime_filter_snapshot,
                    stage="direct_url_fallback_failed",
                    logger=logger,
                    extra={"attempted_url": search_url},
                )
                await context.close()
                return
            await asyncio.sleep(8)

        configured_filters = runtime_filter_snapshot.get("configured_filters") or {}
        filtered_result_url, applied_query_params, query_applied_filter_keys = apply_ali1688_query_filters_to_url(
            page.url,
            configured_filters,
        )
        if query_applied_filter_keys:
            if filtered_result_url != page.url:
                logger.info(
                    "[Search] Applying channel query filters to result URL: %s",
                    {
                        "applied_filter_keys": query_applied_filter_keys,
                        "filtered_result_url": filtered_result_url,
                    },
                )
                filter_nav_success = await _ensure_page_navigated_safe(
                    page,
                    filtered_result_url,
                    logger,
                    timeout=45000,
                    manual_verification_wait_seconds=manual_verification_wait_seconds,
                )
                if filter_nav_success:
                    await asyncio.sleep(5)
                    runtime_filter_snapshot, _, _, _ = _verify_and_mark_runtime_query_snapshot(
                        runtime_filter_snapshot,
                        result_url=page.url,
                        injected_filter_keys=query_applied_filter_keys,
                        applied_query_params=applied_query_params,
                        logger=logger,
                        verification_mode="post_navigation_url",
                    )
                    runtime_filter_snapshot = _write_runtime_filter_snapshot_audit(
                        output_dir,
                        runtime_filter_snapshot,
                        stage="query_filter_post_navigation_verified",
                        logger=logger,
                        extra={"result_url": page.url},
                    )
                else:
                    logger.warning(
                        "[Search] Failed to navigate to filtered result URL; marking attempted query filters as unapplied."
                    )
                    runtime_filter_snapshot = _mark_runtime_snapshot_query_navigation_failed(
                        runtime_filter_snapshot,
                        attempted_filter_keys=query_applied_filter_keys,
                        attempted_query_params=applied_query_params,
                        attempted_result_url=filtered_result_url,
                    )
                    runtime_filter_snapshot = _write_runtime_filter_snapshot_audit(
                        output_dir,
                        runtime_filter_snapshot,
                        stage="query_filter_navigation_failed",
                        logger=logger,
                        extra={"attempted_result_url": filtered_result_url},
                    )
            else:
                logger.info(
                    "[Search] Current result URL already contains requested query filters; verifying in-place.",
                    extra={
                        "applied_filter_keys": query_applied_filter_keys,
                        "result_url": page.url,
                    },
                )
                runtime_filter_snapshot, _, _, _ = _verify_and_mark_runtime_query_snapshot(
                    runtime_filter_snapshot,
                    result_url=page.url,
                    injected_filter_keys=query_applied_filter_keys,
                    applied_query_params=applied_query_params,
                    logger=logger,
                    verification_mode="in_place_url",
                )
                runtime_filter_snapshot = _mark_runtime_snapshot_semantic_dependency_combos(runtime_filter_snapshot)
                runtime_filter_snapshot = _write_runtime_filter_snapshot_audit(
                    output_dir,
                    runtime_filter_snapshot,
                    stage="query_filter_in_place_verified",
                    logger=logger,
                    extra={"result_url": page.url},
                )

        runtime_filter_snapshot = _mark_runtime_snapshot_semantic_dependency_combos(runtime_filter_snapshot)
        runtime_filter_snapshot = await _apply_visible_filter_toggle_runtime(
            page,
            runtime_filter_snapshot,
            logger=logger,
        )
        runtime_filter_snapshot = _mark_runtime_snapshot_semantic_dependency_combos(runtime_filter_snapshot)
        runtime_filter_snapshot = _write_runtime_filter_snapshot_audit(
            output_dir,
            runtime_filter_snapshot,
            stage="visible_filter_toggle_checked",
            logger=logger,
            extra={"result_url": page.url},
        )

        runtime_filter_snapshot = await _apply_special_panel_candidate_runtime(
            page,
            runtime_filter_snapshot,
            logger=logger,
        )
        runtime_filter_snapshot = _mark_runtime_snapshot_semantic_dependency_combos(runtime_filter_snapshot)
        runtime_filter_snapshot = _write_runtime_filter_snapshot_audit(
            output_dir,
            runtime_filter_snapshot,
            stage="special_panel_candidate_checked",
            logger=logger,
            extra={"result_url": page.url},
        )

        from xianyu_tools.source_adapter.ali1688 import Ali1688CaptchaError, Ali1688PayloadError
        adapter = Ali1688SourceAdapter()
        candidates = []
        parse_success = False
        
        for attempt in range(1, 4):  # 最多尝试 3 次
            html_content = await page.content()
            runtime_filter_snapshot = await _refresh_runtime_snapshot_on_current_page(
                page,
                runtime_filter_snapshot,
                observed_page_text=html_content,
                result_url=page.url,
                logger=logger,
            )
            runtime_filter_snapshot = _write_runtime_filter_snapshot_audit(
                output_dir,
                runtime_filter_snapshot,
                stage=f"html_text_probe_attempt_{attempt}",
                logger=logger,
                extra={"result_url": page.url},
            )
            html_content = await page.content()
            try:
                # 判断是否是验证码页面或惩罚页面
                if adapter._is_captcha_page(html_content) or "哎呦喂" in html_content or "空空如也" in html_content:
                    raise Ali1688CaptchaError("Captcha or soft-block (empty page) detected in HTML content")
                
                candidates = adapter.search_from_html(html_content, limit=60)
                if not candidates:
                    raise Ali1688PayloadError("Search result set is empty")
                
                parse_success = True
                break
            except Exception as e:
                logger.warning(f"[Search] Attempt {attempt} failed to parse search results: {e}")
                if attempt == 3:
                    err_file = output_dir / "search_page_error.html"
                    try:
                        err_file.write_text(html_content, encoding="utf-8")
                        logger.error(f"[Search] Dumped failed page to {err_file}")
                    except Exception as dump_err:
                        logger.error(f"[Search] Failed to dump: {dump_err}")
                    runtime_filter_snapshot = _write_runtime_filter_snapshot_audit(
                        output_dir,
                        runtime_filter_snapshot,
                        stage="parse_failed_final",
                        logger=logger,
                        extra={"error": str(e), "result_url": page.url},
                    )
                    raise e
                
                logger.warning("[Search] Possible bot detection. Attempting recovery and safety pre-warm...")
                # 重新导航，并阻塞等待用户滑块自愈
                nav_success = await _ensure_page_navigated_safe(page, search_url, logger, timeout=45000)
                if not nav_success:
                    logger.error(f"[Search] Recovery navigation failed in attempt {attempt}")
                await asyncio.sleep(5)
                
        candidate_offer_ids = {str(c.source_item_id) for c in candidates if c.source_item_id}
        visual_rows = await _extract_visual_offer_rows(page, candidate_offer_ids, logger=logger)
        selected_filter_chips = await _extract_selected_filter_chip_texts(page, logger=logger)
        unexpected_filter_chips = _unexpected_selected_filter_chips(selected_filter_chips, runtime_filter_snapshot)
        visual_order_map = _build_visual_offer_order_map(candidates, visual_rows)
        if visual_order_map:
            logger.info(f"[Search] Extracted visual DOM order for {len(visual_order_map)} offers")
        else:
            logger.warning("[Search] Visual DOM order is unavailable; falling back to adapter candidate order")
        visible_snapshot_file = ""
        try:
            visible_snapshot_path = output_dir / "search_result_visible_snapshot.png"
            await page.screenshot(path=str(visible_snapshot_path), full_page=True)
            visible_snapshot_file = visible_snapshot_path.name
        except Exception as exc:
            logger.warning(f"[Search] Failed to save visible search screenshot: {exc}")
        _write_search_result_snapshots(
            output_dir,
            html_content,
            candidates,
            visual_order_map,
            visual_rows=visual_rows,
            result_url=page.url,
            runtime_filter_snapshot=runtime_filter_snapshot,
            selected_filter_chips=selected_filter_chips,
            unexpected_selected_filter_chips=unexpected_filter_chips,
            visible_snapshot_file=visible_snapshot_file,
            logger=logger,
        )
        if unexpected_filter_chips:
            await page.close()
            raise Ali1688PayloadError(
                "Unexpected selected 1688 filter chips detected: "
                + " | ".join(unexpected_filter_chips)
            )

        await page.close()
        
        import html as py_html
        parsed_candidates = []
        for fallback_index, c in enumerate(candidates, start=1):
            dispatch_text = ""
            offer_id = c.source_item_id
            if offer_id:
                pos = html_content.find(offer_id)
                if pos != -1:
                    chunk = html_content[max(0, pos - 500): min(len(html_content), pos + 2500)]
                    dispatch_text = py_html.unescape(chunk)
            
            metrics = _extract_dispatch_metrics_from_text(dispatch_text)
            parsed_candidates.append({
                "page_original_index": visual_order_map.get(str(offer_id), fallback_index),
                "offer_id": offer_id,
                "title": c.title,
                "item_url": c.item_url,
                "price": c.price,
                "search_card_price": c.price,
                "search_card_image_url": (getattr(c, "images", None) or [None])[0],
                "pickup_48h_text": metrics["pickup_48h_text"],
                "pickup_24h_text": metrics["pickup_24h_text"],
                "month_dispatch_text": metrics["month_dispatch_text"],
                "seven_day_dispatch_text": metrics["seven_day_dispatch_text"],
                "listing_count_text": metrics["listing_count_text"],
                "distributor_count_text": metrics["distributor_count_text"],
                "waybill_support_text": metrics["waybill_support_text"],
                "settled_years_text": metrics["settled_years_text"],
                "company_name": metrics["company_name"] or c.shop_name or "",
                "seven_day_dispatch_count": metrics["seven_day_dispatch_count"],
                "month_dispatch_count": metrics["month_dispatch_count"],
                "listing_count": metrics["listing_count"],
                "distributor_count": metrics["distributor_count"],
            })
            
        top_candidates = _top_dispatch_candidates(parsed_candidates, args.detail_top_n)
        logger.info(f"[Search] Found {len(candidates)} candidates, sorted & filtered to Top {len(top_candidates)}")

        sku_results = []
        for i, c in enumerate(top_candidates, start=1):
            if i > 1:
                inter_wait = random.uniform(5.0, 10.0)
                logger.info(f"    [Cooling] Safety pause for {inter_wait:.1f}s before Rank {i}...")
                await asyncio.sleep(inter_wait)

            item_data = {
                "offer_id": c["offer_id"],
                "title": c["title"],
                "item_url": c["item_url"],
                "min_price": c["price"],
                "search_card_price": c.get("search_card_price"),
                "search_card_image_url": c.get("search_card_image_url"),
                "pickup_48h_text": c.get("pickup_48h_text", ""),
                "pickup_24h_text": c.get("pickup_24h_text", ""),
                "month_dispatch_text": c.get("month_dispatch_text", ""),
                "seven_day_dispatch_text": c.get("seven_day_dispatch_text", ""),
                "listing_count_text": c.get("listing_count_text", ""),
                "distributor_count_text": c.get("distributor_count_text", ""),
                "waybill_support_text": c.get("waybill_support_text", ""),
                "settled_years_text": c.get("settled_years_text", ""),
                "company_name": c.get("company_name", ""),
                "page_original_index": c.get("page_original_index", 0),
                "seven_day_dispatch_count": c.get("seven_day_dispatch_count", 0),
                "month_dispatch_count": c.get("month_dispatch_count", 0),
                "listing_count": c.get("listing_count", 0),
                "distributor_count": c.get("distributor_count", 0),
                "sku_count": 0,
                "status": "pending",
                "drop_reason": None,
                "images": [],
                "source_filter_snapshot": runtime_filter_snapshot,
            }

            res = await _export_sku_from_detail_page(
                context,
                item_data,
                output_dir,
                i,
                logger,
                manual_verification_wait_seconds=manual_verification_wait_seconds,
            )
            item_data["status"] = res["status"]
            item_data["images"] = res.get("images", [])
            item_data["sku_items"] = res.get("sku_details", [])
            item_data["sku_count"] = len(res.get("sku_details", []))
            for metric_key in (
                "pickup_48h_text",
                "pickup_24h_text",
                "month_dispatch_text",
                "seven_day_dispatch_text",
                "listing_count_text",
                "distributor_count_text",
                "waybill_support_text",
                "settled_years_text",
                "company_name",
                "seven_day_dispatch_count",
                "month_dispatch_count",
                "listing_count",
                "distributor_count",
            ):
                if not item_data.get(metric_key) and res.get(metric_key):
                    item_data[metric_key] = res.get(metric_key)
            sku_results.append(item_data)
            
        (output_dir / "summary.json").write_text(json.dumps(sku_results, ensure_ascii=False, indent=2))
        runtime_filter_snapshot = _write_runtime_filter_snapshot_audit(
            output_dir,
            runtime_filter_snapshot,
            stage="summary_written",
            logger=logger,
            extra={"source_count": len(sku_results)},
        )
        
        if state_file_to_save:
            await _export_context_state(context, state_file_to_save)
            logger.info(f"[Auth] Context state exported to {state_file_to_save}")
            
        await context.close()


def main():
    default_state_file, _, _ = _load_active_ali1688_runtime_defaults()
    parser = argparse.ArgumentParser()
    parser.add_argument("--image-url", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--state-file", default=default_state_file)
    parser.add_argument("--detail-top-n", type=int, default=10)
    parser.add_argument("--target-keyword", required=False)
    parser.add_argument("--log-file", required=False)
    parser.add_argument("--channel-filter-snapshot-file", required=False)
    parser.add_argument("--headed", action="store_true")
    parser.add_argument("--manual-verification-wait-seconds", type=int, default=0)
    args = parser.parse_args()
    asyncio.run(_run(args))


if __name__ == "__main__":
    main()
