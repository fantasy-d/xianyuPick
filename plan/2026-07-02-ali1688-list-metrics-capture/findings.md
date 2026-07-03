# 调研记录：1688 商品列表页指标采集

## 2026-07-02 初始代码事实

### DB 字段已存在

`src/web_api/main.py` 与 `scripts/run_full_pipeline.py` 都包含 `ali1688_sources` 的字段补齐逻辑：

- `pickup_48h_text`
- `pickup_24h_text`
- `month_dispatch_text`
- `seven_day_dispatch_text`
- `listing_count_text`
- `distributor_count_text`
- `waybill_support_text`
- `settled_years_text`
- `company_name`
- `month_dispatch_count`
- `seven_day_dispatch_count`
- `listing_count`
- `distributor_count`

结论：
- 不需要优先新增 DB 列。
- 优先检查解析层是否真的把这些字段写入 `res`。

### 入库链路已预留

`scripts/run_full_pipeline.py` 插入 `ali1688_sources` 时已经读取：

- `res.get("pickup_48h_text", "")`
- `res.get("pickup_24h_text", "")`
- `res.get("month_dispatch_text", "")`
- `res.get("seven_day_dispatch_text", "")`
- `res.get("listing_count_text", "")`
- `res.get("distributor_count_text", "")`
- `res.get("waybill_support_text", "")`
- `res.get("settled_years_text", "")`
- `res.get("company_name", "")`
- 对应数值字段也已入库

结论：
- 如果页面没有展示，优先怀疑解析层或 `summary.json` 生成层，而不是 DB 层。

### API 详情已透出

`src/web_api/main.py` 的 `/api/task_details/{task_id}` 已返回：

- `pickup_48h_text`
- `pickup_24h_text`
- `month_dispatch_text`
- `seven_day_dispatch_text`
- `listing_count_text`
- `distributor_count_text`
- `waybill_support_text`
- `settled_years_text`
- `company_name`
- `month_dispatch_count`
- `seven_day_dispatch_count`
- `listing_count`
- `distributor_count`

结论：
- 详情页展示不应额外新增 API 字段，除非任务报告页需要摘要。

### 前端详情页已有展示入口

`web/app.jsx` 中商品详情页货源卡片已有：

```js
const sourceMetrics = [
    src.pickup_48h_text,
    src.pickup_24h_text,
    src.month_dispatch_text,
    src.seven_day_dispatch_text,
    src.listing_count_text,
    src.distributor_count_text,
    src.waybill_support_text,
    src.settled_years_text,
].filter(Boolean);
```

同时已展示：

- `商家: {src.company_name}`

结论：
- 详情页已经具备显示能力。
- 需要验收真实数据是否进入这些字段。

## 当前最大风险

1. 1688 列表页字段可能来自动态 DOM，不一定出现在详情页 HTML。
2. 当前截图中的字段排列是列表页卡片信息，不能只从详情页 JSON-LD 解析。
3. `面单支持` 与 `不支持面单` 都要保留原文，不能只存布尔。
4. `月代发1k+ / 7天代发600+ / 铺货数100内 / 分销商数400+` 需要同时保留文本和可排序数值。
5. 公司名称与 `入驻x年` 可能在同一行，需要防止解析串联。

## 下一步调研重点

1. 定位 `src/xianyu_tools/source_adapter/ali1688.py` 中列表搜索结果解析函数。
2. 查看 `scripts/run_ali1688_slow_flow.py` 如何写 `summary.json`。
3. 找一份真实 `summary.json` 或 HTML 样本，确认字段是否已经存在。

## 2026-07-02 解析层复核

### 列表页 HTML 片段解析链路

`scripts/run_ali1688_slow_flow.py` 在搜索结果页阶段会根据 `offer_id` 从 `html_content` 附近截取列表卡片片段，并调用 `_extract_dispatch_metrics_from_text()` 提取指标。

已确认该函数覆盖：

- `pickup_48h_text`
- `pickup_24h_text`
- `month_dispatch_text`
- `seven_day_dispatch_text`
- `listing_count_text`
- `distributor_count_text`
- `waybill_support_text`
- `settled_years_text`
- `company_name`
- `month_dispatch_count`
- `seven_day_dispatch_count`
- `listing_count`
- `distributor_count`

### 已修复问题

`月代发1k+` 这类“数字 + 单位 + 后缀”的文本原先会被提取为 `月代发1k`，因为正则把 `k` 与 `+` 放在同一个互斥分组里。

已改为：

- 数字
- 可选单位：`万 / k / K`
- 可选后缀：`+ / 内`

因此以下样例会同时保留原文和归一数值：

- `月代发1k+` -> 文本 `月代发1k+`，数值 `1000`
- `7天代发600+` -> 文本 `7天代发600+`，数值 `600`
- `铺货数100内` -> 文本 `铺货数100内`，数值 `100`
- `分销商数400+` -> 文本 `分销商数400+`，数值 `400`

## 2026-07-03 真实任务验收结论

### 详情页补充解析是必要的

真实抓取样本显示，部分履约指标并不稳定出现在搜索列表卡片片段中，但会出现在 1688 详情页 HTML 中，例如：

- `近30天代发数量`
- `48h揽收率`
- `近7天代发数量`
- `24h揽收率`
- `铺货分销商数`
- `入驻x年`

因此解析策略调整为：

- 优先保留列表页卡片片段提取结果。
- 详情页导出 SKU 时同步解析详情页 HTML。
- 仅当列表页字段为空时，用详情页字段补齐，避免覆盖列表页原始展示文案。

### 已确认的真实入库结果

真实任务：`ec24a2fd`，关键词：`海飞丝洗发水`。

API：`/api/task_details/ec24a2fd`

结果：

- `detail_count`: 10
- `source_count`: 100
- `company_name`: 100 条有值
- `pickup_48h_text`: 14 条有值
- `pickup_24h_text`: 14 条有值
- `month_dispatch_text`: 19 条有值
- `seven_day_dispatch_text`: 19 条有值
- `listing_count_text`: 4 条有值
- `distributor_count_text`: 19 条有值
- `settled_years_text`: 20 条有值

当前真实样本未出现可提取的 `waybill_support_text`；该字段链路仍保留，解析契约已覆盖 `面单支持 / 不支持面单`。

### 页面验收结果

在 in-app browser 中打开任务 `ec24a2fd`，进入 Rank 9（闲鱼 DB_ID `273`）货源详情页，页面实际展示了：

- `48H揽收98%`
- `24H揽收88%`
- `月代发100`
- `7天代发100`
- `铺货数100`
- `分销商数5000+`
- `入驻2年`
- `商家: 上海涵潇电子商务有限公司`

同时确认页面保留：

- 固定排序：`预估纯利倒序`
- 货源渠道筛选：`全部渠道 / 1688 货源渠道`
