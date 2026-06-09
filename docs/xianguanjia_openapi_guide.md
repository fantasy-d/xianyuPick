# 闲管家 (Goofish) 开放平台接入要点指南

本文件记录了闲管家开放平台（Goofish OpenAPI）的核心接口定义、参数要点以及本项目在其之上已实现的“多规格 SKU 自愈”与“分类模糊匹配”对接规范。

---

## 1. 基础接入与协议规范

*   **API 基础域名**：`https://open.goofish.pro`
*   **认证参数**：
    *   `appid` (Query 参数): 开放平台的 AppKey。
    *   `timestamp` (Query 参数): 当前时间戳（秒级，需在 5 分钟内有效）。
    *   `sign` (Query 参数): 签名值。由密钥 `app_secret` 对请求 Payload 数据以特定排序进行 MD5 计算得到。
*   **推送通知机制**：系统支持商品上架、下架、订单状态流转等消息的推送通知，开发者可在闲管家后台或通过商品接口指定具体的 Webhook 回调地址。

---

## 2. 核心接口一览

### 2.1 店铺与类目
1.  **查询闲鱼店铺** (`POST /api/open/user/shop/list`)
    *   *说明*：获取授权在该 AppID 下的所有闲鱼账号列表。
2.  **查询商品类目** (`POST /api/open/product/category/list`)
    *   *说明*：获取闲鱼支持的所有行业分类及其三级细分叶子类目 ID（MD5 哈希形式的 `channel_cat_id`）。
3.  **查询商品属性** (`POST /api/open/product/attribute/list`)
    *   *说明*：获取特定类目下要求或推荐的属性字段（如材质、品牌、型号）。

### 2.2 商品管理
1.  **创建商品（单个）** (`POST /api/open/product/create`)
    *   *要点*：主价格字段 `price` 需乘以 100 转换为“分”单位传入。图片最多上传 9 张。
2.  **创建商品（批量）** (`POST /api/open/product/batchCreate`)
    *   *要点*：支持在一次 HTTP 请求中批量创建最多 50 个商品。各商品的入参字段与单创建接口一致，但包装在 `product_data` 数组下，各商品必须通过唯一 `item_key` 作为主键标识。
3.  **正式上架商品** (`POST /api/open/product/publish`)
    *   *要点*：通过单个创建接口创建的商品仅处于“草稿”或“待发布”状态，必须调用上架接口传入商品 ID 才能在闲鱼端公开可见。
4.  **编辑商品** (`POST /api/open/product/update`)
5.  **下架商品** (`POST /api/open/product/depublish`) 与 **删除商品** (`POST /api/open/product/delete`)
6.  **编辑库存** (`POST /api/open/product/stock/update`)

### 2.3 订单与物流
1.  **查询订单列表** (`POST /api/open/order/list`)
    *   *要点*：主要用于第三方 ERP 同步订单流水。
2.  **查询订单详情** (`POST /api/open/order/detail`)
3.  **订单物流发货** (`POST /api/open/order/ship`)
    *   *要点*：传入快递公司代码与运单号进行确认发货。
4.  **订单修改价格** (`POST /api/open/order/update_price`)

---

## 3. 本项目已落实的自愈对接规范 (Xianyu-Tools Custom Specs)

闲鱼官方对多规格（SKU）以及上架商品有极其严格的校验限制。为防止发布阶段发生 API 报错，本项目在 [PublisherV3](file:///Users/mac/PycharmProjects/mytools/xianyu-tools/src/xianyu_tools/xianyu_adapter/publisher_v3.py) 中落实了以下三大自愈规避逻辑：

### 3.1 SKU 维度对齐与缺失值补齐机制
*   **规则限制**：同一商品下，所有 SKU 行的属性维度（冒号前的分类名，如颜色、尺码）的数量与名字在同行之间必须完全相同。
*   **实施策略**：
    1.  **频次过滤**：统计全部 SKU 属性名的出现次数，只保留频次比例 $\ge 50\%$ 的键作为有效公共维度 `valid_dimensions`（最多取前 2 个）。
    2.  **默认补齐**：重构规格文本时，若某 SKU 缺失了部分公共维度，自动以 `"默认"` 属性值填充补齐该项（例如：补齐为 `颜色:蓝色;尺码:默认`）。
    3.  **图片规格文案同步对齐**：`sku_images`（规格主图）里的 `sku_text` 经历完全相同的对齐逻辑，确保图片与规格数量和维度名绝对匹配。

### 3.2 一维退化与敏感字符清洗
*   **规则限制**：若多规格属性值或文本中带有敏感的英文或中文冒号、分号（如 `;`、`:`），会被闲鱼后台再次截断拆分，极易报 `SKU属性项数量异常` 的错误。
*   **实施策略**：
    1.  **一维自动退化**：如规格提取出的有效公共维度为空（属于“一维伪多维”，仅是单规格文字中自带了冒号），则直接判定为一维商品，将全部规格的分类名统一标为 `"规格"`。
    2.  **字符强制清洗**：无论是多维还是一维，属性值中的任何冒号和分号字符一律强制清洗替换为短横线 `-`（如 `规格:加量装-60包`）。
    3.  **双重降级闭环**：对对齐后的规格强制进行排重，若排重后仅剩 1 个规格，或者原始规格本身小于 2，系统自动将发布模式剥离降级为“普通单商品模式”发布，防止闲鱼拦截。

### 3.3 商品分类智能模糊匹配与本地缓存
*   **规则限制**：上架商品需传入精准的渠道类目 `channel_cat_id`，否则会发错分区或被系统下架。
*   **实施策略**：
    1.  **接口本地缓存**：在第一次运行或缓存缺失时调用 `/api/open/product/category/list` 获取闲鱼类目全表，缓存在 [xianyu_categories.json](file:///Users/mac/PycharmProjects/mytools/xianyu-tools/config/xianyu_categories.json) 中，实现秒级零延迟读取。
    2.  **长短语优先匹配**：按类目名称的长度降序打分匹配商品标题（优先选择最精确的词）。同时支持多词复合匹配（如“平衡垫/球/盘”只要标题含有其一即可命中）。
    3.  **缺省配置回退**：若标题无法命中任何分类，自动以 [openapi.json](file:///Users/mac/PycharmProjects/mytools/xianyu-tools/config/openapi.json) 中配置的默认 ID 作为安全兜底。

### 3.4 批量创建接口的 Chunk 分批与草稿自愈自动上架
*   **规则限制**：批量创建商品接口 `/api/open/product/batchCreate` 有两个限制：
    1. 单次 HTTP 请求中商品的数量上限为 50 个；
    2. 创建成功后，商品在后台仅为“草稿”状态，不会公开可见，必须再次调用正式上架接口 `/api/open/product/publish`。
*   **实施策略**：
    1.  **Chunk 物理分批**：在 `publish_items_batch` 中，当待发布的商品总数超过 50 个时，自动按每组最多 50 个商品切片（Chunking），独立进行签名计算和 HTTP 发送，对上游调用方屏蔽底层分批逻辑。
    2.  **唯一 Key 映射召回**：通过拼接唯一商品发布键 `pub-{source_id}-{index}` 作为 `item_key` 传入。接口返回批量结果后，依次提取成功商品的 `product_id`，利用 `item_key` 倒查召回原数据库中的 `source_id`。
    3.  **串行事务上架**：对批量创建成功的 `product_id`，在后端立即自动、串行执行 `/api/open/product/publish` 正式上架，保证商品能直接公开发售，避免商品驻留在草稿箱中。
    4.  **容错隔离**：对于批量创建成功但上架失败的商品，或部分创建失败的商品，将其标记为 `failed` 并记录详细错误原因，而不影响同批次其他商品的创建和上架。

