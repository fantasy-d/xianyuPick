# 任务计划：1688 商品列表页指标采集、入库与展示

> 计划 ID：`2026-07-02-ali1688-list-metrics-capture`
> 创建时间：2026-07-02
> 当前阶段：已完成
> 关联但不合并的计划：`2026-06-26-channel-search-capability-config`

## 1. 目标

1688 抓取商品时，把商品列表页中用户圈出的经营与履约指标稳定采集下来，写入数据库，并在决策资产库的货源列表 / 详情中展示。

必须覆盖的字段：

1. `48H揽收xx%`
2. `24H揽收xx%`
3. `月代发xxx`
4. `7天代发xxx`
5. `铺货数xxx`
6. `分销商数xxx`
7. `面单支持 / 不支持面单`
8. `入驻x年`
9. `供应商 / 公司名称`

## 2. 边界

- 本计划只处理 1688 商品列表页指标采集与展示。
- 不重做渠道号池、账号登录态、顶部筛选项配置。
- 不改变货源排序策略，仍保持 `预估纯利倒序`。
- 不把指标缺失误报为抓取失败；缺失字段应留空并可追踪原因。

## 3. 当前仓库事实

### 已有基础

- `ali1688_sources` 已有字段：
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
- `scripts/run_full_pipeline.py` 已把上述字段从 `res` 写入 `ali1688_sources`。
- `/api/task_details/{task_id}` 已把上述字段透出到 `sources[*]`。
- `web/app.jsx` 的商品详情货源卡片已有 `sourceMetrics` 展示逻辑。

### 仍需确认 / 补齐

1. `src/xianyu_tools/source_adapter/ali1688.py` 是否稳定从列表页解析这些字段。
2. `summary.json` 是否写出这些字段，供 `run_full_pipeline.py` 入库。
3. 决策资产库任务报告页是否需要展示这些指标摘要。
4. 详情页展示是否包含全部 9 类字段，且文案与 1688 原页面一致。
5. 需要补 fixture / 静态校验，锁住解析、入库、API、前端展示契约。

## 4. 分阶段计划

### 阶段 1：调研与契约收敛

状态：`completed`

任务：
- 梳理现有解析链路：
  - 列表页 DOM / 数据源
  - `summary.json`
  - DB 入库
  - API 返回
  - 前端展示
- 明确每个字段的标准 key、文本字段、数值字段。
- 确认当前已有字段是否满足需求，避免新增重复列。

验收：
- `findings.md` 记录字段链路现状。
- `task_plan.md` 明确后续阶段。

### 阶段 2：解析层补齐

状态：`completed`

任务：
- 在 1688 列表页解析逻辑中补齐 9 类字段。
- 对 `1k+ / 100内 / 400+` 等中文数量表达做数值归一化。
- 保留原始展示文案，避免数值归一化丢语义。

验收：
- fixture 能从样例 HTML / 数据结构解析出全部字段。
- 缺失字段不会抛异常。

结果：
- 已补 `validate_ali1688_list_metrics_extraction_contract`。
- 已修复 `月代发1k+` 等“单位 + 后缀”文本只保留到 `1k` 的问题。

### 阶段 3：入库与 API 校验

状态：`completed`

任务：
- 确认 `summary.json -> run_full_pipeline.py -> ali1688_sources` 字段完整。
- 确认 `/api/task_details/{task_id}` 返回字段完整。
- 若任务报告页需要轻量展示，补充接口字段或前端摘要。

验收：
- 插入 fixture 数据后，API 返回 9 类字段。
- 数值字段与文本字段均正确。

### 阶段 4：前端展示

状态：`completed`

任务：
- 详情页货源卡片展示全部指标。
- 需要时在任务报告页增加轻量指标摘要。
- 保持指标展示紧凑，不影响批量操作和渠道分组阅读。

验收：
- 页面能看到 9 类指标。
- 没有字段时不显示空标签。

### 阶段 5：真实抓取验收

状态：`completed`

任务：
- 使用真实 1688 抓取结果跑一次。
- 检查 `summary.json`、DB、API、页面四层一致。

验收：
- 真实样本入库。
- 页面级验收结果写入 `scratch/`。
- `progress.md` 记录最终闭环结果。

## 5. 成功标准

- 真实抓取结果中，用户圈出的 9 类指标能入库。
- API 能稳定返回字段。
- 页面能展示字段。
- 指标按货源展示，不跨渠道、不跨商品串值。
- 有 fixture 或脚本校验防止回归。

## 6. 闭环结果

- 解析契约已覆盖列表页截图格式与详情页补充格式。
- 真实任务 `ec24a2fd` 已完成，`/api/task_details/ec24a2fd` 返回 100 条货源。
- API 验收确认已入库并返回：
  - `pickup_48h_text`
  - `pickup_24h_text`
  - `month_dispatch_text`
  - `seven_day_dispatch_text`
  - `listing_count_text`
  - `distributor_count_text`
  - `settled_years_text`
  - `company_name`
- 当前真实样本未出现可提取的 `waybill_support_text`，字段链路保留且契约覆盖 `面单支持 / 不支持面单`。
- 页面验收确认 Rank 9 货源卡片展示：
  - `48H揽收98%`
  - `24H揽收88%`
  - `月代发100`
  - `7天代发100`
  - `铺货数100`
  - `分销商数5000+`
  - `入驻2年`
  - `商家: 上海涵潇电子商务有限公司`
