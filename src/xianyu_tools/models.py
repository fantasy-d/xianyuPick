from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(slots=True)
class HotItem:
    hot_item_id: str
    platform: str
    title: str
    price: float
    want_count: int | None = None
    seller_name: str | None = None
    area: str | None = None
    sales_volume: int | None = None
    hot_score: float | None = None
    item_url: str = ""
    image_url: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class SourceResolution:
    hot_item_id: str
    resolved: bool
    source_item_ids: list[str] = field(default_factory=list)
    resolution_reason: str = ""
    source_query: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class RawSourceItem:
    source_platform: str
    source_item_id: str
    title: str
    price: float
    item_url: str
    original_price: float | None = None
    images: list[str] = field(default_factory=list)
    specs: dict[str, str] = field(default_factory=dict)
    shop_name: str | None = None
    sales: int | None = None
    shipping_fee: float | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class NormalizedSourceItem:
    source_platform: str
    source_item_id: str
    title: str
    normalized_title: str
    price: float
    item_url: str
    original_price: float | None = None
    images: list[str] = field(default_factory=list)
    specs: dict[str, str] = field(default_factory=dict)
    shop_name: str | None = None
    sales: int | None = None
    shipping_fee: float = 0.0
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class Candidate:
    item: NormalizedSourceItem
    estimated_cost: float
    estimated_resale_price: float
    estimated_margin: float
    estimated_margin_rate: float
    score: float
    risk_flags: list[str] = field(default_factory=list)


@dataclass(slots=True)
class PricingConfig:
    markup_rate: float = 0.45
    platform_fee_rate: float = 0.03
    payment_fee_rate: float = 0.006
    packaging_cost: float = 1.5
    aftersale_reserve_rate: float = 0.02
    min_margin: float = 8.0
    min_margin_rate: float = 0.18


@dataclass(slots=True)
class XianyuMarket:
    hot_item_id: str
    keyword: str
    listing_count: int
    min_price: float | None = None
    median_price: float | None = None
    price_band: dict[str, float | None] = field(default_factory=dict)
    merchant_ratio: float = 0.0
    competition_level: str = "unknown"
    sample_items: list[dict[str, Any]] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class XianyuSearchItem:
    item_id: str
    title: str
    price: float
    original_price: float | None = None
    want_count: int | None = None
    seller_name: str | None = None
    area: str | None = None
    publish_time: str | None = None
    item_url: str = ""
    image_url: str | None = None
    tags: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class XianyuDetailItem:
    item_id: str
    title: str
    price: float
    original_price: float | None = None
    seller_id: str | None = None
    seller_name: str | None = None
    description: str = ""
    images: list[str] = field(default_factory=list)
    area: str | None = None
    want_count: int | None = None
    browse_count: int | None = None
    seller_credit_level: str | None = None
    user_registration_days: int | None = None
    item_url: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class XianyuSellerProfile:
    user_id: str
    seller_name: str
    avatar_url: str | None = None
    bio: str = ""
    on_sale_count: int | None = None
    rating_count: int | None = None
    seller_credit_level: str | None = None
    buyer_credit_level: str | None = None
    seller_positive_rate: str | None = None
    buyer_positive_rate: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
