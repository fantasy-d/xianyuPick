from __future__ import annotations

import asyncio
import re
import threading
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from xianyu_tools.xianyu_adapter.browser_transport import (
    PlaywrightBrowserConfig,
    PlaywrightBrowserTransport,
    default_desktop_context_options,
)


SELLER_TRADE_BASE_URL = "https://seller.goofish.com/?site=COMMONPRO#/seller-trade"
TRADE_ROUTES = {
    "order": f"{SELLER_TRADE_BASE_URL}/order-manage",
    "refund": f"{SELLER_TRADE_BASE_URL}/refund-manage",
    "return_address": f"{SELLER_TRADE_BASE_URL}/refund-address",
    "rate": f"{SELLER_TRADE_BASE_URL}/evaluation-manage",
    "complaint": f"{SELLER_TRADE_BASE_URL}/complaint-manage",
}
ORDER_COUNT_API = "mtop.taobao.idle.merchant.order.count"
ORDER_LIST_API = "mtop.taobao.idle.trade.merchant.sold.get"
REFUND_LIST_API = "mtop.taobao.idle.merchant.refund.list"
RETURN_ADDRESS_LIST_API = "mtop.alibaba.idle.seller.platform.merchant.delivery.address.list.query"
RATE_LIST_API = "mtop.taobao.idle.merchant.rate.list"
COMPLAINT_LIST_API = "mtop.taobao.idle.cco.shop.complain.list"
TRADE_READONLY_APIS = {
    ORDER_COUNT_API,
    ORDER_LIST_API,
    REFUND_LIST_API,
    RETURN_ADDRESS_LIST_API,
    RATE_LIST_API,
    COMPLAINT_LIST_API,
}
API_RE = re.compile(r"/h5/([^/?]+)/")


class SellerWorkbenchTradeAdapterError(RuntimeError):
    pass


@dataclass(slots=True)
class SellerWorkbenchTradeCount:
    query_code: str
    count: int

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class SellerWorkbenchOrderSummary:
    order_id: str = ""
    item_id: str = ""
    title: str = ""
    status: str = ""
    amount_text: str = ""
    created_at: str = ""
    buyer_masked: str = ""
    raw_keys: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class SellerWorkbenchRefundSummary:
    refund_id: str = ""
    order_id: str = ""
    item_id: str = ""
    title: str = ""
    refund_type: str = ""
    refund_status: str = ""
    order_status: str = ""
    reason: str = ""
    refund_fee_text: str = ""
    created_at: str = ""
    buyer_masked: str = ""
    action_labels: list[str] = field(default_factory=list)
    raw_keys: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class SellerWorkbenchReturnAddressSummary:
    contact_id: str = ""
    contact_name_masked: str = ""
    mobile_phone_masked: str = ""
    region_text: str = ""
    default_addr: bool = False
    raw_keys: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class SellerWorkbenchRateSummary:
    order_id: str = ""
    item_id: str = ""
    title: str = ""
    rate_level: str = ""
    rate_content: str = ""
    buyer_masked: str = ""
    raw_keys: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class SellerWorkbenchComplaintSummary:
    complaint_id: str = ""
    order_id: str = ""
    item_id: str = ""
    title: str = ""
    status: str = ""
    amount_text: str = ""
    buyer_masked: str = ""
    raw_keys: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class SellerWorkbenchTradeSnapshot:
    order_counts: list[SellerWorkbenchTradeCount] = field(default_factory=list)
    orders: list[SellerWorkbenchOrderSummary] = field(default_factory=list)
    refunds: list[SellerWorkbenchRefundSummary] = field(default_factory=list)
    return_addresses: list[SellerWorkbenchReturnAddressSummary] = field(default_factory=list)
    rates: list[SellerWorkbenchRateSummary] = field(default_factory=list)
    complaints: list[SellerWorkbenchComplaintSummary] = field(default_factory=list)
    captured_apis: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def extract_api_name(url: str) -> str:
    match = API_RE.search(url)
    return match.group(1).lower() if match else ""


class SellerWorkbenchTradeAdapter:
    """Read-only adapter for the official Goofish seller trade workbench."""

    def __init__(
        self,
        *,
        config: PlaywrightBrowserConfig | None = None,
        timeout_ms: int = 30000,
        settle_ms: int = 7000,
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
    ) -> "SellerWorkbenchTradeAdapter":
        if not Path(state_file).exists():
            raise SellerWorkbenchTradeAdapterError(f"state file not found: {state_file}")
        return cls(
            config=PlaywrightBrowserConfig(
                state_file=state_file,
                headless=headless,
                browser_channel=browser_channel,
                launch_args=list(launch_args or []),
                context_options=default_desktop_context_options(),
            )
        )

    def capture_snapshot(self) -> SellerWorkbenchTradeSnapshot:
        captures = self._run_sync(self._capture_routes(tuple(TRADE_ROUTES)))
        return SellerWorkbenchTradeSnapshot(
            order_counts=parse_order_counts(captures.get(ORDER_COUNT_API)),
            orders=parse_orders(captures.get(ORDER_LIST_API)),
            refunds=parse_refunds(captures.get(REFUND_LIST_API)),
            return_addresses=parse_return_addresses(captures.get(RETURN_ADDRESS_LIST_API)),
            rates=parse_rates(captures.get(RATE_LIST_API)),
            complaints=parse_complaints(captures.get(COMPLAINT_LIST_API)),
            captured_apis=sorted(captures),
        )

    def get_order_counts(self) -> list[SellerWorkbenchTradeCount]:
        captures = self._run_sync(self._capture_routes(("order",), {ORDER_COUNT_API}))
        return parse_order_counts(captures.get(ORDER_COUNT_API))

    def list_orders(self) -> list[SellerWorkbenchOrderSummary]:
        captures = self._run_sync(self._capture_routes(("order",), {ORDER_LIST_API}))
        return parse_orders(captures.get(ORDER_LIST_API))

    def list_refunds(self) -> list[SellerWorkbenchRefundSummary]:
        captures = self._run_sync(self._capture_routes(("refund",), {REFUND_LIST_API}))
        return parse_refunds(captures.get(REFUND_LIST_API))

    def list_return_addresses(self) -> list[SellerWorkbenchReturnAddressSummary]:
        captures = self._run_sync(self._capture_routes(("return_address",), {RETURN_ADDRESS_LIST_API}))
        return parse_return_addresses(captures.get(RETURN_ADDRESS_LIST_API))

    def list_rates(self) -> list[SellerWorkbenchRateSummary]:
        captures = self._run_sync(self._capture_routes(("rate",), {RATE_LIST_API}))
        return parse_rates(captures.get(RATE_LIST_API))

    def list_complaints(self) -> list[SellerWorkbenchComplaintSummary]:
        captures = self._run_sync(self._capture_routes(("complaint",), {COMPLAINT_LIST_API}))
        return parse_complaints(captures.get(COMPLAINT_LIST_API))

    async def _capture_routes(
        self,
        route_keys: tuple[str, ...],
        target_apis: set[str] | None = None,
    ) -> dict[str, dict[str, Any]]:
        target_apis = target_apis or TRADE_READONLY_APIS
        captures: dict[str, dict[str, Any]] = {}
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
                    if api_name not in target_apis or api_name in captures:
                        return
                    try:
                        payload = await asyncio.wait_for(
                            response.json(),
                            timeout=max(self.response_timeout_ms / 1000, 1),
                        )
                    except Exception as exc:
                        captures.setdefault(api_name, {"error": str(exc)})
                        return
                    captures.setdefault(api_name, payload)

                def handle_response(response: Any) -> None:
                    task = asyncio.create_task(capture_response(response))
                    pending_tasks.add(task)
                    task.add_done_callback(pending_tasks.discard)

                page.on("response", handle_response)
                try:
                    for route_key in route_keys:
                        route_url = TRADE_ROUTES.get(route_key)
                        if not route_url:
                            raise SellerWorkbenchTradeAdapterError(f"unknown trade route: {route_key}")
                        await page.goto(route_url, wait_until="domcontentloaded", timeout=self.timeout_ms)
                        await page.wait_for_timeout(self.settle_ms)
                        await self._drain_response_tasks(pending_tasks)
                finally:
                    page.remove_listener("response", handle_response)
                    await self._drain_response_tasks(pending_tasks)
                    await page.close()
                    await context.close()
            finally:
                await browser.close()
        return captures

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


def parse_order_counts(payload: dict[str, Any] | None) -> list[SellerWorkbenchTradeCount]:
    count_items = _as_list(_get_path(payload, "data", "module", "countInfoList"))
    result: list[SellerWorkbenchTradeCount] = []
    for item in count_items:
        if not isinstance(item, dict):
            continue
        result.append(
            SellerWorkbenchTradeCount(
                query_code=str(item.get("queryCode") or ""),
                count=_safe_int(item.get("count")),
            )
        )
    return result


def parse_orders(payload: dict[str, Any] | None) -> list[SellerWorkbenchOrderSummary]:
    items = _as_list(_get_path(payload, "data", "module", "items"))
    result: list[SellerWorkbenchOrderSummary] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        result.append(
            SellerWorkbenchOrderSummary(
                order_id=_first_text(item, ("orderId", "bizOrderId", "tradeId", "id")),
                item_id=_first_text(item, ("itemId", "item_id")),
                title=_first_text(item, ("title", "itemTitle", "itemName", "subject")),
                status=_first_text(item, ("orderStatus", "status", "statusDesc")),
                amount_text=_first_text(item, ("amount", "actualPaidFee", "totalFee", "price")),
                created_at=_first_text(item, ("createTime", "gmtCreate", "payTime")),
                buyer_masked=_mask_text(_first_text(item, ("buyerNick", "buyerName", "userNick"))),
                raw_keys=sorted(str(key) for key in item.keys()),
            )
        )
    return result


def parse_refunds(payload: dict[str, Any] | None) -> list[SellerWorkbenchRefundSummary]:
    items = _as_list(_get_path(payload, "data", "data", "items"))
    result: list[SellerWorkbenchRefundSummary] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        common = item.get("commonData") if isinstance(item.get("commonData"), dict) else {}
        refund = item.get("refundInfoVO") if isinstance(item.get("refundInfoVO"), dict) else {}
        buyer = item.get("buyerInfoVO") if isinstance(item.get("buyerInfoVO"), dict) else {}
        item_info = item.get("itemVO") if isinstance(item.get("itemVO"), dict) else {}
        price = item.get("priceVO") if isinstance(item.get("priceVO"), dict) else {}
        right = item.get("rightVO") if isinstance(item.get("rightVO"), dict) else {}
        result.append(
            SellerWorkbenchRefundSummary(
                refund_id=str(refund.get("refundId") or ""),
                order_id=str(common.get("orderId") or ""),
                item_id=str(common.get("itemId") or ""),
                title=str(item_info.get("title") or ""),
                refund_type=str(refund.get("refundType") or ""),
                refund_status=str(refund.get("refundStatus") or common.get("refundStatus") or ""),
                order_status=str(common.get("orderStatus") or ""),
                reason=str(refund.get("reason") or ""),
                refund_fee_text=_money_text(price.get("refundFee"), price.get("auctionPrice"), price.get("refundFeeView")),
                created_at=str(refund.get("gmtCreate") or common.get("createTime") or ""),
                buyer_masked=_mask_text(str(buyer.get("userNick") or "")),
                action_labels=_extract_action_labels(right.get("btnList")),
                raw_keys=sorted(str(key) for key in item.keys()),
            )
        )
    return result


def parse_return_addresses(payload: dict[str, Any] | None) -> list[SellerWorkbenchReturnAddressSummary]:
    items = _as_list(_get_path(payload, "data", "data"))
    result: list[SellerWorkbenchReturnAddressSummary] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        region_parts = [
            str(item.get("provinceName") or "").strip(),
            str(item.get("cityName") or "").strip(),
            str(item.get("districtName") or "").strip(),
        ]
        result.append(
            SellerWorkbenchReturnAddressSummary(
                contact_id=str(item.get("contactId") or ""),
                contact_name_masked=_mask_text(str(item.get("contactName") or "")),
                mobile_phone_masked=_mask_phone(str(item.get("mobilePhone") or "")),
                region_text=" ".join(part for part in region_parts if part),
                default_addr=bool(item.get("defaultAddr")),
                raw_keys=sorted(str(key) for key in item.keys()),
            )
        )
    return result


def parse_rates(payload: dict[str, Any] | None) -> list[SellerWorkbenchRateSummary]:
    items = _as_list(_get_path(payload, "data", "module", "items"))
    result: list[SellerWorkbenchRateSummary] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        result.append(
            SellerWorkbenchRateSummary(
                order_id=_first_text(item, ("orderId", "bizOrderId", "tradeId")),
                item_id=_first_text(item, ("itemId", "item_id")),
                title=_first_text(item, ("title", "itemTitle", "itemName", "subject")),
                rate_level=_first_text(item, ("rateLevel", "level", "rateType")),
                rate_content=_first_text(item, ("rateContent", "content", "comment")),
                buyer_masked=_mask_text(_first_text(item, ("buyerNick", "buyerName", "userNick"))),
                raw_keys=sorted(str(key) for key in item.keys()),
            )
        )
    return result


def parse_complaints(payload: dict[str, Any] | None) -> list[SellerWorkbenchComplaintSummary]:
    items = _as_list(_get_path(payload, "data", "list"))
    result: list[SellerWorkbenchComplaintSummary] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        result.append(
            SellerWorkbenchComplaintSummary(
                complaint_id=_first_text(item, ("complaintId", "complainId", "id")),
                order_id=_first_text(item, ("orderId", "bizOrderId", "tradeId")),
                item_id=_first_text(item, ("itemId", "item_id")),
                title=_first_text(item, ("title", "itemTitle", "itemName", "subject")),
                status=_first_text(item, ("complaintStatus", "status", "statusDesc")),
                amount_text=_first_text(item, ("amount", "disputeAmount", "price")),
                buyer_masked=_mask_text(_first_text(item, ("buyerNick", "buyerName", "userNick"))),
                raw_keys=sorted(str(key) for key in item.keys()),
            )
        )
    return result


def _get_path(value: Any, *keys: str) -> Any:
    current = value
    for key in keys:
        if not isinstance(current, dict):
            return None
        current = current.get(key)
    return current


def _as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _first_text(value: Any, keys: tuple[str, ...]) -> str:
    found = _first_value(value, keys)
    return str(found).strip() if found is not None else ""


def _first_value(value: Any, keys: tuple[str, ...]) -> Any:
    if isinstance(value, dict):
        for key in keys:
            found = value.get(key)
            if found not in (None, ""):
                return found
        for child in value.values():
            found = _first_value(child, keys)
            if found not in (None, ""):
                return found
    elif isinstance(value, list):
        for child in value:
            found = _first_value(child, keys)
            if found not in (None, ""):
                return found
    return None


def _safe_int(value: Any) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def _money_text(*values: Any) -> str:
    for value in values:
        text = str(value or "").strip()
        if not text or "://" in text:
            continue
        if re.search(r"\d", text):
            return text if "¥" in text else f"¥{text}"
    return ""


def _mask_text(value: str) -> str:
    text = value.strip()
    if not text:
        return ""
    if len(text) <= 2:
        return text[:1] + "*"
    return text[:1] + "*" * max(len(text) - 2, 1) + text[-1:]


def _mask_phone(value: str) -> str:
    digits = "".join(ch for ch in value if ch.isdigit())
    if len(digits) < 7:
        return _mask_text(value)
    return f"{digits[:3]}****{digits[-4:]}"


def _extract_action_labels(value: Any) -> list[str]:
    labels: list[str] = []
    for item in _as_list(value):
        if not isinstance(item, dict):
            continue
        label = _first_text(item, ("text", "title", "name", "label", "btnText"))
        if label and label not in labels:
            labels.append(label)
    return labels
