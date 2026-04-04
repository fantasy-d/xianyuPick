import json

from xianyu_tools.xianyu_adapter import FixtureXianyuAdapter


def test_fixture_xianyu_adapter_replays_captured_payloads(tmp_path) -> None:
    fixture_root = tmp_path / "fixtures"
    (fixture_root / "search" / "iphone-15-pro-max").mkdir(parents=True)
    (fixture_root / "detail").mkdir(parents=True)
    (fixture_root / "seller" / "u-001").mkdir(parents=True)

    with (fixture_root / "search" / "iphone-15-pro-max" / "page_1.json").open("w", encoding="utf-8") as handle:
        json.dump(
            {
                "data": {
                    "resultList": [
                        {
                            "data": {
                                "item": {
                                    "main": {
                                        "targetUrl": "fleamarket://item?id=xy-001",
                                        "clickParam": {"args": {"publishTime": "1719999999000", "wantNum": "13"}},
                                        "exContent": {
                                            "itemId": "xy-001",
                                            "title": "iPhone 15 Pro Max 国行 99新",
                                            "price": [{"text": "¥"}, {"text": "6299"}],
                                            "userNickName": "上海数码",
                                        },
                                    }
                                }
                            }
                        }
                    ]
                }
            },
            handle,
            ensure_ascii=False,
        )

    with (fixture_root / "detail" / "xy-001.json").open("w", encoding="utf-8") as handle:
        json.dump(
            {
                "data": {
                    "itemDO": {"itemId": "xy-001", "title": "iPhone 15 Pro Max 国行 99新", "price": "6299"},
                    "sellerDO": {"sellerId": "u-001", "nick": "上海数码"},
                }
            },
            handle,
            ensure_ascii=False,
        )

    with (fixture_root / "seller" / "u-001" / "head.json").open("w", encoding="utf-8") as handle:
        json.dump(
            {
                "data": {
                    "module": {
                        "base": {"userId": "u-001", "displayName": "上海数码"},
                        "tabs": {},
                    }
                }
            },
            handle,
            ensure_ascii=False,
        )

    adapter = FixtureXianyuAdapter(fixture_root)
    assert adapter.search("iphone 15 pro max")[0].item_id == "xy-001"
    assert adapter.detail("https://www.goofish.com/item?id=xy-001").seller_id == "u-001"
    assert adapter.seller("u-001").seller_name == "上海数码"
