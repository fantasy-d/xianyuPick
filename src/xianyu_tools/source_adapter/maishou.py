from __future__ import annotations

import json
import os
import re
import time
from dataclasses import dataclass
from typing import Any, Callable
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from xianyu_tools.models import RawSourceItem

MAISHOU_SEARCH_URL = "https://appapi.maishou88.com/api/v1/homepage/searchList"
MAISHOU_DETAIL_URL = "https://appapi.maishou88.com/api/v3/goods/detail"
MAISHOU_TARGET_URL = "https://msapi.maishou88.com/api/v1/share/getTargetUrl"


class MaishouError(RuntimeError):
    pass


class MaishouHTTPError(MaishouError):
    pass


class MaishouNetworkError(MaishouError):
    pass


class MaishouPayloadError(MaishouError):
    pass


Transport = Callable[[Request], dict[str, Any]]


@dataclass(slots=True)
class MaishouConfig:
    invite_code: str = os.getenv("MAISHOU_INVITE_CODE", "6110440")
    openid: str = os.getenv("MAISHOU_OPENID", "564bdce0fa408fc9e1d5d42fd022ef0b")
    version: str = os.getenv("MAISHOU_APP_VERSION", "3.7.7.2")
    timeout: float = float(os.getenv("MAISHOU_TIMEOUT", "20"))
    max_retries: int = int(os.getenv("MAISHOU_MAX_RETRIES", "2"))
    retry_delay_seconds: float = float(os.getenv("MAISHOU_RETRY_DELAY_SECONDS", "1"))


class MaishouAdapter:
    SOURCE_LABELS = {
        0: "all",
        1: "taobao",
        2: "jd",
        3: "pinduoduo",
        4: "suning",
        5: "vip",
        6: "kaola",
        7: "douyin",
        8: "kuaishou",
        10: "1688",
    }

    def __init__(
        self,
        *,
        config: MaishouConfig | None = None,
        transport: Transport | None = None,
    ) -> None:
        self.config = config or MaishouConfig()
        self.transport = transport or self._send

    def search(
        self,
        keyword: str,
        *,
        limit: int = 20,
        source: int = 0,
        page: int = 1,
    ) -> list[RawSourceItem]:
        payload = {
            "isCoupon": 0,
            "keyword": str(keyword),
            "openid": self.config.openid,
            "order": "desc",
            "page": page,
            "pddListId": "",
            "sort": "",
            "sourceType": str(source),
            "user_id": "",
        }
        headers = {
            "Accept": "application/json",
            "Referer": "https://hnbc018.kuaizhan.com/",
            "User-Agent": "MaiShouApp/3.7.7 (iPhone; iOS 26.3; Scale/3.00)",
            "openid": self.config.openid,
            "version": self.config.version,
        }
        data = self._post_form(MAISHOU_SEARCH_URL, payload, headers=headers)
        rows = data.get("data")
        if rows is None:
            rows = []
        if not isinstance(rows, list):
            raise MaishouPayloadError(f"Unexpected search payload: {data!r}")
        return [self._parse_search_row(row) for row in rows[:limit]]

    def detail(self, item_id_or_url: str, *, source: int = 1) -> RawSourceItem:
        item_id = item_id_or_url.rsplit("/", maxsplit=1)[-1]
        params = {
            "goodsId": str(item_id),
            "sourceType": str(source),
            "inviteCode": self.config.invite_code,
            "supplierCode": "",
            "activityId": "",
            "isShare": "1",
            "token": "",
        }
        detail_data = self._post_json(
            MAISHOU_DETAIL_URL,
            {**params, "keyword": "", "usageScene": 5},
        )
        detail = detail_data.get("data")
        if detail is None:
            detail = {}
        if not isinstance(detail, dict):
            raise MaishouPayloadError(f"Unexpected detail payload: {detail_data!r}")

        target_data = self._post_json(
            MAISHOU_TARGET_URL,
            {**params, "isDirectDetail": 0},
        )
        target = target_data.get("data")
        if target is None:
            target = {}
        if not isinstance(target, dict):
            raise MaishouPayloadError(f"Unexpected target payload: {target_data!r}")

        images = detail.get("images") or detail.get("imageList") or []
        if isinstance(images, str):
            images = [images]

        shipping_fee = self._to_float(
            detail.get("postFee")
            or detail.get("expressFee")
            or detail.get("freight")
            or 0
        )
        return RawSourceItem(
            source_platform=self._platform_name(detail, fallback_source=source),
            source_item_id=str(detail.get("goodsId") or item_id),
            title=detail.get("title") or "",
            price=self._to_float(detail.get("actualPrice") or detail.get("price")),
            original_price=self._to_float_or_none(detail.get("originalPrice")),
            item_url=target.get("appUrl") or target.get("schemaUrl") or "",
            images=[str(url) for url in images if url],
            specs=self._extract_specs(detail),
            shop_name=detail.get("shopName") or detail.get("sellerNick"),
            sales=self._to_int_or_none(detail.get("monthSales") or detail.get("sales")),
            shipping_fee=shipping_fee,
            metadata={
                "provider": "maishou",
                "source_type": source,
                "coupon_price": self._to_float_or_none(detail.get("couponPrice")),
                "commission": self._to_float_or_none(detail.get("commission")),
                "copy_code": target.get("kl"),
                "detail_payload": detail,
                "target_payload": target,
            },
        )

    def _parse_search_row(self, row: dict[str, Any]) -> RawSourceItem:
        source = self._to_int(row.get("sourceType"), default=0)
        return RawSourceItem(
            source_platform=self._platform_name(row, fallback_source=source),
            source_item_id=str(row.get("goodsId") or ""),
            title=row.get("title") or "",
            price=self._to_float(row.get("actualPrice")),
            original_price=self._to_float_or_none(row.get("originalPrice")),
            item_url="",
            images=[row["picUrl"]] if row.get("picUrl") else [],
            shop_name=row.get("shopName"),
            sales=self._to_int_or_none(row.get("monthSales")),
            shipping_fee=0.0,
            metadata={
                "provider": "maishou",
                "source_type": source,
                "coupon_price": self._to_float_or_none(row.get("couponPrice")),
                "commission": self._to_float_or_none(row.get("commission")),
                "search_payload": row,
            },
        )

    def _extract_specs(self, detail: dict[str, Any]) -> dict[str, str]:
        fields = {
            "品牌": detail.get("brandName") or detail.get("brand"),
            "类目": detail.get("dtitle") or detail.get("categoryName"),
        }
        return {key: str(value) for key, value in fields.items() if value}

    def _platform_name(self, payload: dict[str, Any], *, fallback_source: int) -> str:
        raw_name = payload.get("platformName") or payload.get("sourceTypeName")
        if isinstance(raw_name, str):
            normalized = raw_name.strip().lower()
            aliases = {
                "淘宝": "taobao",
                "天猫": "tmall",
                "京东": "jd",
                "拼多多": "pinduoduo",
                "抖音": "douyin",
                "快手": "kuaishou",
                "1688": "1688",
                "taobao": "taobao",
                "tmall": "tmall",
                "jd": "jd",
                "pinduoduo": "pinduoduo",
            }
            if normalized in aliases:
                return aliases[normalized]
        return self.SOURCE_LABELS.get(fallback_source, str(fallback_source))

    def _post_form(
        self,
        url: str,
        payload: dict[str, Any],
        *,
        headers: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        request_headers = {
            "Content-Type": "application/x-www-form-urlencoded; charset=utf-8",
            **(headers or {}),
        }
        body = urlencode(payload).encode("utf-8")
        return self.transport(Request(url=url, data=body, headers=request_headers, method="POST"))

    def _post_json(self, url: str, payload: dict[str, Any]) -> dict[str, Any]:
        body = json.dumps(payload).encode("utf-8")
        request = Request(
            url=url,
            data=body,
            headers={
                "Accept": "application/json",
                "Content-Type": "application/json; charset=utf-8",
                "User-Agent": "Mozilla/5.0 AppleWebKit/537 Chrome/143 Safari/537",
            },
            method="POST",
        )
        return self.transport(request)

    def _send(self, request: Request) -> dict[str, Any]:
        last_error: Exception | None = None
        attempts = max(self.config.max_retries + 1, 1)
        for attempt in range(1, attempts + 1):
            try:
                with urlopen(request, timeout=self.config.timeout) as response:
                    raw = response.read().decode("utf-8-sig")
                break
            except HTTPError as exc:
                last_error = exc
                if not self._should_retry_http(exc.code) or attempt >= attempts:
                    raise MaishouHTTPError(f"Maishou request failed with HTTP {exc.code}") from exc
            except URLError as exc:
                last_error = exc
                if attempt >= attempts:
                    raise MaishouNetworkError(f"Maishou request failed: {exc.reason}") from exc
            if self.config.retry_delay_seconds > 0:
                time.sleep(self.config.retry_delay_seconds)
        else:
            if isinstance(last_error, HTTPError):
                raise MaishouHTTPError(f"Maishou request failed with HTTP {last_error.code}") from last_error
            if isinstance(last_error, URLError):
                raise MaishouNetworkError(f"Maishou request failed: {last_error.reason}") from last_error
            raise MaishouNetworkError("Maishou request failed for unknown network reason")
        try:
            data = json.loads(raw) if raw else {}
        except json.JSONDecodeError as exc:
            raise MaishouPayloadError(f"Maishou returned invalid JSON: {raw[:200]!r}") from exc
        if not isinstance(data, dict):
            raise MaishouPayloadError(f"Maishou returned unexpected body: {data!r}")
        return data

    @staticmethod
    def _should_retry_http(status_code: int) -> bool:
        return status_code == 429 or 500 <= status_code < 600

    @staticmethod
    def _to_float(value: Any) -> float:
        try:
            return round(float(value), 2)
        except (TypeError, ValueError):
            return 0.0

    @staticmethod
    def _to_float_or_none(value: Any) -> float | None:
        try:
            return round(float(value), 2)
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _to_int(value: Any, *, default: int = 0) -> int:
        try:
            return int(value)
        except (TypeError, ValueError):
            return default

    @staticmethod
    def _to_int_or_none(value: Any) -> int | None:
        if isinstance(value, str):
            digits = re.sub(r"[^\d]", "", value)
            if digits:
                return int(digits)
        try:
            return int(value)
        except (TypeError, ValueError):
            return None
