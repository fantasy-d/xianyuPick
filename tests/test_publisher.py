import json
import pytest
from pathlib import Path
from xianyu_tools.xianyu_adapter.publisher_v3 import PublisherV3

def test_publisher_v3_format_sku_text_truncates_property_names() -> None:
    # 临时覆盖配置文件不存在的异常，只用来测试 _format_sku_text
    class DummyPublisher(PublisherV3):
        def __init__(self):
            self.base_url = "https://open.goofish.pro"
            self.appid = "test_appid"
            self.app_secret = "test_secret"
            self.defaults = {}

    pub = DummyPublisher()
    
    # 属性项名称长度测试
    # 1. 超过4个字，如 "商品描述属性:红色;尺码描述:M"
    res1 = pub._format_sku_text("商品描述属性:红色;尺码描述:M")
    assert res1 == "商品描述:红色;尺码描述:M"
    
    # 2. 正好4个字或以内
    res2 = pub._format_sku_text("颜色:红色;尺码:L")
    assert res2 == "颜色:红色;尺码:L"
    
    # 3. 包含垃圾 span 的处理
    res3 = pub._format_sku_text("颜色描述<span style=\"color:red;\">热卖</span>:红色;尺码:M")
    assert res3 == "颜色描述:红色;尺码:M"


def test_publisher_v3_publish_item_degrades_single_sku(monkeypatch) -> None:
    # 模拟 openapi.json 的加载
    mock_config = {
        "base_url": "https://open.goofish.pro",
        "appid": "mock_appid",
        "app_secret": "mock_secret",
        "default_config": {
            "user_name": "test_user",
            "province": "上海",
            "city": "上海",
            "district": "浦东"
        }
    }
    
    monkeypatch.setattr(Path, "exists", lambda self: True)
    monkeypatch.setattr(Path, "read_text", lambda self, encoding=None: json.dumps(mock_config))

    # 模拟网络 POST 请求
    last_payload = {}
    class FakeResponse:
        def json(self):
            return {"code": 0, "data": {"product_id": "999888777"}}

    def mock_post(url, params=None, data=None, headers=None, timeout=None):
        nonlocal last_payload
        last_payload = json.loads(data.decode('utf-8'))
        return FakeResponse()

    import requests
    monkeypatch.setattr(requests, "post", mock_post)

    pub = PublisherV3()
    # 阻止 commit_publish 发起真实的 HTTP 调用
    monkeypatch.setattr(pub, "commit_publish", lambda product_id: {"status": "success"})

    # 场景 1：传入仅有 1 个 SKU 的数据，断言自动退化为单商品模式
    single_sku_data = {
        "title": "测试单SKU降级商品",
        "price": 10.0,
        "images": ["https://example.com/img1.jpg"],
        "description": "测试商品描述",
        "sku_items": [
            {
                "price": 8.0,
                "stock": 100,
                "outer_id": "out1",
                "sku_text": "颜色描述属性:白色"
            }
        ],
        "sku_images": [
            {
                "src": "https://example.com/sku_white.jpg",
                "sku_text": "颜色描述属性:白色"
            }
        ]
    }
    
    res = pub.publish_item(single_sku_data)
    assert res["status"] == "success"
    
    # 验证降级后的 payload
    assert "sku_items" not in last_payload
    assert "sku_images" not in last_payload
    assert last_payload["price"] == 800  # 唯一 SKU 价格 8.0 元 转换为分
    assert last_payload["stock"] == 100  # 唯一 SKU 库存
    
    # 场景 2：传入 2 个及以上 SKU 的数据，断言以多规格发布
    multi_sku_data = {
        "title": "测试多SKU商品",
        "price": 10.0,
        "images": ["https://example.com/img1.jpg"],
        "description": "测试商品描述",
        "sku_items": [
            {"price": 8.0, "stock": 100, "sku_text": "颜色描述属性:红色"},
            {"price": 9.0, "stock": 200, "sku_text": "颜色描述属性:蓝色"}
        ],
        "sku_images": [
            {"src": "https://example.com/red.jpg", "sku_text": "颜色描述属性:红色"},
            {"src": "https://example.com/blue.jpg", "sku_text": "颜色描述属性:蓝色"}
        ]
    }
    
    res_multi = pub.publish_item(multi_sku_data)
    assert res_multi["status"] == "success"
    
    # 验证多规格 payload
    assert "sku_items" in last_payload
    assert len(last_payload["sku_items"]) == 2
    assert last_payload["sku_items"][0]["sku_text"] == "颜色描述:红色"  # 5字截断为4字
    assert last_payload["sku_items"][1]["sku_text"] == "颜色描述:蓝色"
    assert "sku_images" in last_payload
    assert len(last_payload["sku_images"]) == 2
    assert last_payload["sku_images"][0]["sku_text"] == "颜色描述:红色"


def test_publisher_v3_format_sku_text_limits_dimensions() -> None:
    class DummyPublisher(PublisherV3):
        def __init__(self):
            self.base_url = "https://open.goofish.pro"
            self.appid = "test_appid"
            self.app_secret = "test_secret"
            self.defaults = {}

    pub = DummyPublisher()
    
    # 超过 2 维的属性被截断
    res1 = pub._format_sku_text("颜色:红色;尺码:M;材质:棉")
    assert res1 == "颜色:红色;尺码:M"
    
    res2 = pub._format_sku_text("颜色:红色;尺码:M;材质:棉;重量:100g")
    assert res2 == "颜色:红色;尺码:M"


def test_publisher_v3_publish_item_deduplicates_conflict_skus(monkeypatch) -> None:
    mock_config = {
        "base_url": "https://open.goofish.pro",
        "appid": "mock_appid",
        "app_secret": "mock_secret",
        "default_config": {
            "user_name": "test_user",
            "province": "上海",
            "city": "上海",
            "district": "浦东"
        }
    }
    
    monkeypatch.setattr(Path, "exists", lambda self: True)
    monkeypatch.setattr(Path, "read_text", lambda self, encoding=None: json.dumps(mock_config))

    last_payload = {}
    class FakeResponse:
        def json(self):
            return {"code": 0, "data": {"product_id": "999888777"}}

    def mock_post(url, params=None, data=None, headers=None, timeout=None):
        nonlocal last_payload
        last_payload = json.loads(data.decode('utf-8'))
        return FakeResponse()

    import requests
    monkeypatch.setattr(requests, "post", mock_post)

    pub = PublisherV3()
    monkeypatch.setattr(pub, "commit_publish", lambda product_id: {"status": "success"})

    # 场景 1：3 维度商品，因为截断产生重复 SKU 冲突，去重后剩下 >1 个 SKU，以多规格发布
    three_dim_data = {
        "title": "测试3维度去重多SKU",
        "price": 10.0,
        "images": ["https://example.com/img1.jpg"],
        "description": "测试商品描述",
        "sku_items": [
            {"price": 8.0, "stock": 100, "sku_text": "颜色:红色;尺码:M;重量:100g"},
            {"price": 8.0, "stock": 150, "sku_text": "颜色:红色;尺码:M;重量:200g"}, # 去重时应过滤掉
            {"price": 9.0, "stock": 200, "sku_text": "颜色:蓝色;尺码:L;重量:100g"}
        ],
        "sku_images": [
            {"src": "https://example.com/red.jpg", "sku_text": "颜色:红色;尺码:M;重量:100g"},
            {"src": "https://example.com/red.jpg", "sku_text": "颜色:红色;尺码:M;重量:200g"}, # 应该过滤
            {"src": "https://example.com/blue.jpg", "sku_text": "颜色:蓝色;尺码:L;重量:100g"}
        ]
    }
    
    res = pub.publish_item(three_dim_data)
    assert res["status"] == "success"
    
    assert "sku_items" in last_payload
    # 去重后只应该剩下 2 个 SKU（红M，蓝L）
    assert len(last_payload["sku_items"]) == 2
    assert last_payload["sku_items"][0]["sku_text"] == "颜色:红色;尺码:M"
    assert last_payload["sku_items"][1]["sku_text"] == "颜色:蓝色;尺码:L"
    
    assert "sku_images" in last_payload
    assert len(last_payload["sku_images"]) == 2
    assert last_payload["sku_images"][0]["sku_text"] == "颜色:红色;尺码:M"

    # 场景 2：3 维度商品，去重后仅剩下 1 个规格，触发二次降级退化
    three_dim_degraded_data = {
        "title": "测试3维度去重后降级商品",
        "price": 10.0,
        "images": ["https://example.com/img1.jpg"],
        "description": "测试商品描述",
        "sku_items": [
            {"price": 8.0, "stock": 100, "sku_text": "颜色:红色;尺码:M;重量:100g"},
            {"price": 8.5, "stock": 150, "sku_text": "颜色:红色;尺码:M;重量:200g"} # 去重时应过滤
        ]
    }
    
    res2 = pub.publish_item(three_dim_degraded_data)
    assert res2["status"] == "success"
    
    # 因为只剩下唯一的 颜色:红色;尺码:M，应该安全退化为普通单规格发布！
    assert "sku_items" not in last_payload
    assert "sku_images" not in last_payload
    assert last_payload["price"] == 800
    assert last_payload["stock"] == 100


def test_publisher_v3_publish_item_aligns_and_pads_sku_dimensions(monkeypatch) -> None:
    mock_config = {
        "base_url": "https://open.goofish.pro",
        "appid": "mock_appid",
        "app_secret": "mock_secret",
        "default_config": {
            "user_name": "test_user",
            "province": "上海",
            "city": "上海",
            "district": "浦东"
        }
    }
    
    monkeypatch.setattr(Path, "exists", lambda self: True)
    monkeypatch.setattr(Path, "read_text", lambda self, encoding=None: json.dumps(mock_config))

    last_payload = {}
    class FakeResponse:
        def json(self):
            return {"code": 0, "data": {"product_id": "999888777"}}

    def mock_post(url, params=None, data=None, headers=None, timeout=None):
        nonlocal last_payload
        last_payload = json.loads(data.decode('utf-8'))
        return FakeResponse()

    import requests
    monkeypatch.setattr(requests, "post", mock_post)

    pub = PublisherV3()
    monkeypatch.setattr(pub, "commit_publish", lambda product_id: {"status": "success"})

    # 模拟输入：SKU 属性项不一致（维度非对齐）
    mismatched_dim_data = {
        "title": "测试维度不对齐补齐商品",
        "price": 10.0,
        "images": ["https://example.com/img1.jpg"],
        "description": "测试商品描述",
        "sku_items": [
            {"price": 8.0, "stock": 100, "sku_text": "颜色:红色;尺码:M"},
            {"price": 9.0, "stock": 200, "sku_text": "颜色:蓝色"} # 缺失尺码维度，应当自动填充为 "尺码:默认"
        ]
    }
    
    res = pub.publish_item(mismatched_dim_data)
    assert res["status"] == "success"
    
    assert "sku_items" in last_payload
    assert len(last_payload["sku_items"]) == 2
    
    # 验证红色SKU
    assert last_payload["sku_items"][0]["sku_text"] == "颜色:红色;尺码:M"
    # 验证蓝色SKU是否被成功补齐
    assert last_payload["sku_items"][1]["sku_text"] == "颜色:蓝色;尺码:默认"

    assert last_payload["price"] == 1000
    assert last_payload["stock"] == 300


def test_publisher_v3_publish_item_handles_pseudo_dimensions_and_cleanses_characters(monkeypatch) -> None:
    mock_config = {
        "base_url": "https://open.goofish.pro",
        "appid": "mock_appid",
        "app_secret": "mock_secret",
        "default_config": {
            "user_name": "test_user",
            "province": "上海",
            "city": "上海",
            "district": "浦东"
        }
    }
    
    monkeypatch.setattr(Path, "exists", lambda self: True)
    monkeypatch.setattr(Path, "read_text", lambda self, encoding=None: json.dumps(mock_config))

    last_payload = {}
    class FakeResponse:
        def json(self):
            return {"code": 0, "data": {"product_id": "999888777"}}

    def mock_post(url, params=None, data=None, headers=None, timeout=None):
        nonlocal last_payload
        last_payload = json.loads(data.decode('utf-8'))
        return FakeResponse()

    import requests
    monkeypatch.setattr(requests, "post", mock_post)

    pub = PublisherV3()
    monkeypatch.setattr(pub, "commit_publish", lambda product_id: {"status": "success"})

    # 模拟输入：1688常见的一维规格，但带有冒号（伪多维），并且属性值带有多余的冒号分号
    pseudo_dim_data = {
        "title": "测试一维伪多维冒号商品",
        "price": 30.0,
        "images": ["https://example.com/img1.jpg"],
        "description": "测试商品描述",
        "sku_items": [
            {"price": 31.0, "stock": 1000, "sku_text": "加量囤货装:【60包整箱】;五层"}, # 带有冒号和分号
            {"price": 32.0, "stock": 1000, "sku_text": "学生装:【30包整箱】"},
            {"price": 33.0, "stock": 1000, "sku_text": "热卖装:【40包整箱】"}
        ],
        "sku_images": [
            {"src": "https://example.com/img_60.jpg", "sku_text": "加量囤货装:【60包整箱】;五层"},
            {"src": "https://example.com/img_30.jpg", "sku_text": "学生装:【30包整箱】"}
        ]
    }
    
    res = pub.publish_item(pseudo_dim_data)
    assert res["status"] == "success"
    
    # 验证是否为一维（属性名是 "规格"），且内容里的冒号和分号被清洗为 "-"
    assert "sku_items" in last_payload
    assert len(last_payload["sku_items"]) == 3
    # 验证第一项
    # 原文为 "加量囤货装:【60包整箱】;五层"
    # 标准化后变成 "规格:加量囤货装-【60包整箱】-五层" (限制20字以内)
    assert last_payload["sku_items"][0]["sku_text"].startswith("规格:")
    assert ":" not in last_payload["sku_items"][0]["sku_text"][3:] # 除了前缀冒号，值里不能再有冒号
    assert ";" not in last_payload["sku_items"][0]["sku_text"]
    
    # 验证 sku_images 里的 sku_text 是否成功对齐并且清洗
    assert "sku_images" in last_payload
    assert len(last_payload["sku_images"]) == 2
    assert last_payload["sku_images"][0]["sku_text"].startswith("规格:")
    assert last_payload["sku_images"][0]["sku_text"] == last_payload["sku_items"][0]["sku_text"]


def test_publisher_v3_match_category_fuzzy_matches_title() -> None:
    class DummyPublisher(PublisherV3):
        def __init__(self):
            self.defaults = {"channel_cat_id": "default_id"}
            
        def _load_categories(self):
            return [
                {"channel_cat_id": "cat_towel", "channel_cat_name": "面巾纸/湿巾"},
                {"channel_cat_id": "cat_shoes", "channel_cat_name": "男士帆布鞋"},
                {"channel_cat_id": "cat_tang", "channel_cat_name": "男士唐装"},
            ]
            
    pub = DummyPublisher()
    
    # 1. 匹配到复合词中的一部分
    assert pub._match_category("维达面巾纸100抽") == "cat_towel"
    # 2. 匹配到完整词
    assert pub._match_category("潮流男士唐装短袖") == "cat_tang"
    # 3. 没有匹配到时，回退到 default_id
    assert pub._match_category("未知的无分类商品") == "default_id"


def test_publisher_v3_publish_items_batch(monkeypatch) -> None:
    mock_config = {
        "base_url": "https://open.goofish.pro",
        "appid": "mock_appid",
        "app_secret": "mock_secret",
        "default_config": {
            "user_name": "test_user",
            "province": "上海",
            "city": "上海",
            "district": "浦东",
            "channel_cat_id": "default_cat"
        }
    }
    
    monkeypatch.setattr(Path, "exists", lambda self: True)
    monkeypatch.setattr(Path, "read_text", lambda self, encoding=None: json.dumps(mock_config))

    last_batch_payload = {}
    class FakeResponse:
        def json(self):
            return {
                "code": 0,
                "data": {
                    "success": [
                        {"item_key": "pub-111-0", "product_id": 999111, "product_status": 10},
                        {"item_key": "pub-222-1", "product_id": 999222, "product_status": 10}
                    ],
                    "error": [
                        {"item_key": "pub-333-2", "msg": "分类不支持当前属性"}
                    ]
                }
            }

    def mock_post(url, params=None, data=None, headers=None, timeout=None):
        nonlocal last_batch_payload
        last_batch_payload = json.loads(data.decode('utf-8'))
        return FakeResponse()

    import requests
    monkeypatch.setattr(requests, "post", mock_post)

    pub = PublisherV3()
    monkeypatch.setattr(pub, "commit_publish", lambda product_id: {"status": "success"})
    monkeypatch.setattr(pub, "_load_categories", lambda: [])

    batch_data = [
        {"source_id": 111, "title": "测试商品1", "price": 10.0, "images": ["http://img.com/1.jpg"]},
        {"source_id": 222, "title": "测试商品2", "price": 20.0, "images": ["http://img.com/2.jpg"]},
        {"source_id": 333, "title": "测试商品3", "price": 30.0, "images": ["http://img.com/3.jpg"]}
    ]

    res = pub.publish_items_batch(batch_data)
    
    assert len(res["success"]) == 2
    assert res["success"][0]["source_id"] == 111
    assert res["success"][0]["product_id"] == "999111"
    assert res["success"][1]["source_id"] == 222
    
    assert len(res["failed"]) == 1
    assert res["failed"][0]["source_id"] == 333
    assert res["failed"][0]["msg"] == "分类不支持当前属性"

    assert "product_data" in last_batch_payload
    assert len(last_batch_payload["product_data"]) == 3
    assert last_batch_payload["product_data"][0]["item_key"] == "pub-111-0"
    assert last_batch_payload["product_data"][0]["publish_shop"][0]["title"] == "测试商品1"




