#!/usr/bin/env python3
"""Static probe for the Goofish seller workbench item module.

This script does not use login cookies and does not call business APIs. It
fetches the observed frontend bundle and extracts mtop API names, route names,
and publish-payload field markers so the POC has a repeatable artifact.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass
from typing import Iterable
from urllib.request import Request, urlopen


DEFAULT_BUNDLE_URL = "https://g.alicdn.com/idle-pc/seller-item/0.0.14/js/main.js"

API_RE = re.compile(r"api\s*:\s*[\"']([^\"']+)[\"']")
ROUTE_RE = re.compile(r"path\s*:\s*[\"']([^\"']*)[\"']")

FIELD_MARKERS = [
    "itemTextDTO",
    "itemCatDTO",
    "itemPriceDTO",
    "itemPostFeeDTO",
    "itemSkuList",
    "imageInfoDOList",
    "propertyImageList",
    "descImages",
    "itemAddrDTO",
    "userRightsProtocols",
    "uniqueCode",
    "sourceId",
    "bizcode",
    "publishScene",
]

CAPABILITY_KEYWORDS = {
    "publish": ("publish", "idleitem.publish"),
    "draft": ("draft",),
    "search": ("search", "status.statistics"),
    "offline": ("offline", "downshelf"),
    "delete": ("delete",),
    "edit": ("edit", "update"),
    "price_quantity": ("price.update", "quantity.update"),
    "freight": ("freight",),
    "category_property": ("category", "property", "brands", "models", "kgraph"),
    "security": ("security", "badwords"),
    "poi": ("poi", "division"),
}


@dataclass(frozen=True)
class ProbeResult:
    bundle_url: str
    bundle_size: int
    api_count: int
    apis_by_capability: dict[str, list[str]]
    routes: list[str]
    field_markers: dict[str, bool]


def fetch_text(url: str) -> str:
    request = Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urlopen(request, timeout=30) as response:
        return response.read().decode("utf-8", errors="replace")


def unique_sorted(values: Iterable[str]) -> list[str]:
    return sorted({value for value in values if value is not None})


def classify_apis(apis: list[str]) -> dict[str, list[str]]:
    result: dict[str, list[str]] = {key: [] for key in CAPABILITY_KEYWORDS}
    result["other"] = []
    for api in apis:
        lowered = api.lower()
        matched = False
        for capability, keywords in CAPABILITY_KEYWORDS.items():
            if any(keyword in lowered for keyword in keywords):
                result[capability].append(api)
                matched = True
        if not matched:
            result["other"].append(api)
    return {key: unique_sorted(values) for key, values in result.items() if values}


def probe_bundle(bundle_url: str) -> ProbeResult:
    bundle = fetch_text(bundle_url)
    apis = unique_sorted(api for api in API_RE.findall(bundle) if api.startswith("mtop."))
    routes = unique_sorted(
        route
        for route in ROUTE_RE.findall(bundle)
        if not route.startswith(".") and (route == "" or re.fullmatch(r"[A-Za-z0-9_*/-]+", route))
    )
    field_markers = {marker: marker in bundle for marker in FIELD_MARKERS}
    return ProbeResult(
        bundle_url=bundle_url,
        bundle_size=len(bundle),
        api_count=len(apis),
        apis_by_capability=classify_apis(apis),
        routes=routes,
        field_markers=field_markers,
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Probe Goofish seller workbench item module statically.")
    parser.add_argument("--bundle-url", default=DEFAULT_BUNDLE_URL)
    args = parser.parse_args()

    result = probe_bundle(args.bundle_url)
    print(json.dumps(result.__dict__, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
