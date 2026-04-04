# Source Adapter Contract

## Goal

`source_adapter` 层负责把不同上游平台的原始返回统一映射成 `RawSourceItem`。

当前主线实现是 `Ali1688SourceAdapter`。


## Common Interface

统一接口定义在 [base.py](/Users/mac/PycharmProjects/mytools/xianyu-tools/src/xianyu_tools/source_adapter/base.py)。

### `search(keyword, limit=20, source=0, page=1) -> list[RawSourceItem]`

语义：

- 根据关键词搜索上游货源候选
- 返回轻量列表结果
- 可以没有购买链接
- 可以没有完整图片和规格

约束：

- 返回值必须始终是 `list[RawSourceItem]`
- `source_platform` 必须可用
- `source_item_id` 必须可用
- `title` 必须可用
- `price` 必须是数值


### `detail(item_id_or_url, source=1) -> RawSourceItem`

语义：

- 根据商品 ID 或 URL 获取单个上游商品详情
- 返回更完整的商品信息
- 应尽量补齐购买链接、图片、规格、运费等字段

约束：

- 返回值必须始终是 `RawSourceItem`
- `source_item_id` 必须稳定
- `item_url` 应尽量为最终可用购买链接
- `metadata` 应保留必要原始 payload 方便排查


## RawSourceItem Contract

定义在 [models.py](/Users/mac/PycharmProjects/mytools/xianyu-tools/src/xianyu_tools/models.py)。

### Required Fields

- `source_platform`
  统一平台名，例如 `taobao`、`tmall`、`jd`、`pinduoduo`、`1688`
- `source_item_id`
  上游平台内部商品 ID，要求稳定、可复用
- `title`
  商品标题
- `price`
  当前价格，统一为 `float`
- `item_url`
  商品链接
  - `search` 结果允许为空字符串
  - `detail` 结果应尽量补齐为真实可跳转链接


### Optional Fields

- `original_price`
- `images`
- `specs`
- `shop_name`
- `sales`
- `shipping_fee`
- `metadata`


## Field Semantics

### `source_platform`

要求：

- 使用统一平台名
- 不直接透传未清洗的平台描述文案

当前主要映射：

- `淘宝` -> `taobao`
- `天猫` -> `tmall`
- `京东` -> `jd`
- `拼多多` -> `pinduoduo`
- `抖音` -> `douyin`
- `快手` -> `kuaishou`
- `1688` -> `1688`


### `source_item_id`

要求：

- 必须是字符串
- 必须优先使用平台原始商品 ID
- 不允许用标题、链接片段等不稳定字段替代


### `item_url`

要求：

- 搜索阶段允许为空
- 详情阶段优先使用最终可访问购买链接
- 若只有 schema 链接，也允许降级保留 schema


### `price` and `original_price`

要求：

- 统一为 `float`
- 无法解析时：
  - `price` 兜底为 `0.0`
  - `original_price` 兜底为 `None`


### `sales`

要求：

- 统一为 `int | None`
- 类似 `9000+` 需要被解析成 `9000`


### `shipping_fee`

要求：

- 统一为 `float | None`
- 搜索结果通常未知，可为 `0.0`
- 详情结果优先填真实运费


### `metadata`

要求：

- 保留必要调试字段
- 允许放原始 payload
- 不应该依赖 `metadata` 才能驱动主流程

当前 `Ali1688SourceAdapter` 里常见的 `metadata`：

- `provider`
- `source_type`
- `search_payload`
- `search_html_fallback`
- `search_html_variant`
- `filter_flags`


## Ali1688-Specific Contract

实现文件：

- [ali1688.py](/Users/mac/PycharmProjects/mytools/xianyu-tools/src/xianyu_tools/source_adapter/ali1688.py)

### Search Mapping

`Ali1688SourceAdapter.search()` 当前对接：

- `selloffer/offer_search.htm`
- `youyuan/index.htm?tab=imageSearch`

输出规则：

- `item_url` 优先构造成 `detail.1688.com/offer/{offer_id}.html`
- 当前主线只依赖结果列表，不主动打开详情页
- `metadata.search_payload` 或 `metadata.search_html_variant` 保留结果页原始来源信息


### Detail Mapping

`Ali1688SourceAdapter.detail()` 当前对接：

- `detail.1688.com/offer/...`

输出规则：

- 当前不是主线必需能力
- `detail()` 只作为补充解析能力保留


## Error Contract

`Ali1688SourceAdapter` 当前把失败分成四类：

- `Ali1688HTTPError`
  - HTTP 4xx / 5xx
- `Ali1688NetworkError`
  - DNS、连接失败、超时等网络错误
- `Ali1688PayloadError`
  - JSON 非法、返回结构不符合预期
- `Ali1688CaptchaError`
  - 搜索结果页被 1688 风控拦截

语义：

- `HTTP 429` 和 `5xx` 视为可重试错误
- `URLError` 视为可重试网络错误
- `4xx` 中除 `429` 外，默认不重试
- payload 结构错误默认不重试


## Retry Contract

`Ali1688Config` 当前支持：

- `timeout`
- `max_retries`
- `retry_delay_seconds`

默认规则：

- 总尝试次数 = `1 + max_retries`
- 网络错误自动重试
- `429` 和 `5xx` 自动重试
- 达到重试上限后抛出明确异常类型


## Current Guarantees

当前项目依赖的最小保证是：

1. `search()` 一定返回结构稳定的候选列表
2. `detail()` 一定返回单个结构稳定的商品对象
3. 搜索与详情都能映射到统一 `RawSourceItem`
4. 主流程不依赖某个上游平台的原始字段名


## Non-Goals

当前这个契约阶段不处理：

- 多上游平台统一排序策略
- 更复杂的库存、佣金、活动价时效问题
- 购买链接可用性长期监控
- 上游平台账号体系和登录态复用
