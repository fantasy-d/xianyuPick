from __future__ import annotations

import json
from datetime import date, datetime
from decimal import Decimal
from typing import Any

try:
    from mcp.server.fastmcp import FastMCP
except ImportError as exc:  # pragma: no cover - import guard for runtime setup
    raise SystemExit(
        "Missing dependency: mcp. Install project dependencies first, for example: "
        "pip install -e ."
    ) from exc

from web_api import main as web_api


mcp = FastMCP("xianyu-tools")


def _jsonable(value: Any) -> Any:
    """Normalize DB/API values into MCP JSON-serializable payloads."""
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, dict):
        return {str(key): _jsonable(val) for key, val in value.items()}
    if isinstance(value, list):
        return [_jsonable(item) for item in value]
    if isinstance(value, tuple):
        return [_jsonable(item) for item in value]
    return value


def _limit_items(items: list[Any], limit: int) -> list[Any]:
    safe_limit = max(1, min(int(limit or 20), 100))
    return items[:safe_limit]


@mcp.tool()
def xianyu_system_status() -> dict[str, Any]:
    """Return current system status, including active workers and source login status."""
    return _jsonable(web_api.system_status())


@mcp.tool()
def xianyu_list_tasks(
    limit: int = 20,
    status: str = "",
    keyword: str = "",
) -> dict[str, Any]:
    """List scan tasks with optional status/keyword filters."""
    tasks = web_api.list_tasks()
    if not isinstance(tasks, list):
        return {"status": "failed", "items": [], "total": 0, "msg": "任务列表读取失败"}

    normalized_status = str(status or "").strip()
    normalized_keyword = str(keyword or "").strip().lower()
    filtered = []
    for task in tasks:
        if normalized_status and str(task.get("status") or "") != normalized_status:
            continue
        if normalized_keyword and normalized_keyword not in str(task.get("keyword") or "").lower():
            continue
        filtered.append(task)

    return {
        "status": "success",
        "total": len(filtered),
        "items": _jsonable(_limit_items(filtered, limit)),
    }


@mcp.tool()
def xianyu_get_task_detail(task_id: str) -> dict[str, Any]:
    """Return detail data for a scan task, including Xianyu items and source candidates."""
    task_id = str(task_id or "").strip()
    if not task_id:
        return {"status": "failed", "msg": "task_id is required"}
    result = web_api.get_task_details(task_id)
    if isinstance(result, dict) and result.get("error"):
        return {"status": "failed", "msg": result.get("error")}
    return {"status": "success", "data": _jsonable(result)}


@mcp.tool()
def xianyu_start_scan_task(
    keyword: str,
    crawl_config: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """
    Start a scan task.

    Optional crawl_config only applies to this task and does not update system defaults.
    Supported fields follow the Web task snapshot:
    source_limit_1688, gross_profit_rate, source_filter_models,
    source_channel_selection_mode, enabled_source_channels, channel_search_filters.
    """
    keyword = str(keyword or "").strip()
    if not keyword:
        return {"status": "failed", "msg": "keyword is required"}

    raw_config = crawl_config if isinstance(crawl_config, dict) else None
    snapshot = web_api.build_task_crawl_config_snapshot(raw_config)
    task_id = web_api.Task.add(keyword, snapshot)
    if not task_id:
        return {"status": "failed", "msg": "扫描任务创建失败"}

    return {
        "status": "success",
        "task_id": task_id,
        "task_status": "排队中",
        "keyword": keyword,
        "crawl_config_snapshot": _jsonable(snapshot),
    }


@mcp.tool()
def xianyu_list_selection_items(
    page: int = 1,
    limit: int = 10,
    keyword: str = "",
    publish_status: str = "",
) -> dict[str, Any]:
    """List selected/published product candidates from the selection manager."""
    result = web_api.get_xianyu_products(
        page=max(1, int(page or 1)),
        limit=max(1, min(int(limit or 10), 100)),
        keyword=str(keyword or ""),
        publish_status=str(publish_status or ""),
    )
    return {"status": "success", "data": _jsonable(result)}


@mcp.tool()
def xianyu_list_orders(
    page: int = 1,
    limit: int = 20,
    order_status: str = "",
    account_id: str = "",
) -> dict[str, Any]:
    """List orders from XianGuanJia OpenAPI."""
    result = web_api.get_openapi_orders(
        page=max(1, int(page or 1)),
        limit=max(1, min(int(limit or 20), 100)),
        order_status=str(order_status or ""),
        account_id=str(account_id or ""),
    )
    return _jsonable(result)


@mcp.tool()
def xianyu_get_order_detail(order_no: str, account_id: str = "") -> dict[str, Any]:
    """Return one order detail from XianGuanJia OpenAPI."""
    order_no = str(order_no or "").strip()
    if not order_no:
        return {"status": "failed", "msg": "order_no is required"}
    return _jsonable(web_api.get_openapi_order_detail(order_no, account_id=str(account_id or "")))


@mcp.tool()
def xianyu_token_stats(recent_limit: int = 20) -> dict[str, Any]:
    """Return LLM token usage summary and recent logs."""
    result = web_api.get_token_stats()
    if not isinstance(result, dict) or result.get("status") != "success":
        return _jsonable(result)
    safe_limit = max(1, min(int(recent_limit or 20), 100))
    result = dict(result)
    result["recent_logs"] = list(result.get("recent_logs") or [])[:safe_limit]
    return _jsonable(result)


def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()
