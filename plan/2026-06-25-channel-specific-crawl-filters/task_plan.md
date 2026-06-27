# 任务计划：按渠道配置 1688 商品列表筛选项

> 计划状态：调研与实施方案细化完成，等待按批次推进  
> 当前阶段：阶段 1 进行中  
> 关联计划：
> - `plan/2026-06-13-source-channel-pool`
> - `plan/2026-06-22-crawl-source-channel-config`
> - `plan/2026-06-26-channel-search-capability-config`

## 1. 目标

在“系统参数配置 -> 商品爬取与筛选配置”中，为每个货源渠道新增独立的 1688 搜索筛选配置能力，使以下列表页条件可以按渠道单独配置、进入抓取运行时、并在决策资产库与详情页中追溯“本次结果使用了哪些渠道、每个渠道使用了哪些筛选策略”：

- 极速开票
- 分销严选
- 一件代发
- 7天无理由
- 1件代发包邮
- 包邮
- 退货包运费
- 真实工厂认证
- 实力认证
- 官方物流
- 密文面单

## 2. 本次计划要解决的核心问题

1. 这些筛选项如何按“渠道维度”配置，而不是做成全局 1688 单例配置。
2. 哪些筛选项已经有较强的 query/runtime 证据，哪些只能先停留在配置层与快照层。
3. 如何保证抓取结果、任务详情、决策资产库都能说明“用了哪些渠道”和“渠道下用了哪些筛选条件”。
4. 如何避免把“渠道筛选”和“固定排序策略”混在一起。

## 3. 边界

### 3.1 包含

- 为 `crawl_config` 增加按渠道保存搜索筛选条件的结构
- 为系统设置页增加按渠道编辑这些筛选项的 UI
- 为抓取链路增加“读取渠道筛选配置 -> 生成运行时快照 -> 写入结果”的完整设计
- 为任务级、渠道级、货源明细级追溯补充字段设计
- 为后续真实 runtime 接入准备调研结论、批次顺序、验证口径

### 3.2 不包含

- 不重做 `source_channels` 的账号池结构
- 不要求本轮一次性把 11 个筛选项全部做成真实生效
- 不把排序做成用户配置项
- 不为非 1688 渠道强行补同构筛选定义

## 4. 与既有计划的关系

### `plan/2026-06-13-source-channel-pool`

- 已完成渠道账号池、登录状态、激活账号管理
- 本计划只消费其输出：
  - `channel_id`
  - `channel_type`
  - `accounts`
  - `active_account_ids`
  - 登录态

### `plan/2026-06-22-crawl-source-channel-config`

- 已完成“商品爬取与筛选配置 -> 货源渠道配置”
- 本计划是在其基础上，为每个渠道继续补“搜索筛选策略”

### `plan/2026-06-26-channel-search-capability-config`

- 已完成 11 个搜索能力项的共享定义与第一批 query 证据整理
- 本计划更聚焦“这些能力如何进入渠道级配置，并影响抓取与展示”

## 5. 当前代码现状快照

### 5.1 已有能力

- `src/xianyu_tools/channel_search_filters.py`
  - 已有 11 个共享筛选定义
  - 已包含 `encrypted_waybill`
- `src/xianyu_tools/config.py`
  - 已有 `channel_search_filters` 归一化能力
  - 已有渠道级筛选快照 helper
- `web/app.jsx`
  - 已有 11 个筛选项前端展示元数据
- `src/xianyu_tools/source_adapter/ali1688.py`
  - 已有部分 query 级筛选映射能力
- `scripts/run_full_pipeline.py` / `scripts/run_ali1688_slow_flow.py`
  - 已有筛选快照透传与结果记录基础
- `src/web_api/main.py`
  - 已能返回渠道分组、渠道摘要

### 5.2 当前缺口

1. 还没有把“本轮新增的 11 个筛选项配置”整理成专门面向实施的分批计划。
2. 还没有把“不同映射策略的筛选项”分成 query/UI/组合语义/特殊面板四类去推进。
3. 决策资产库与详情页虽已有渠道分组，但尚未在本计划中明确：
   - 展示哪些渠道字段
   - 渠道筛选摘要展示到哪一层
   - 哪一层只展示渠道，哪一层展示筛选细节
4. 对“密文面单、分销严选、极速开票”等项，缺少更细的调研批次与证据采集顺序。

## 6. 数据契约

### 6.1 渠道级筛选配置

建议继续沿用当前结构，不再新开平行字段：

```json
{
  "crawl_config": {
    "channel_search_filters": [
      {
        "channel_id": "ali1688",
        "filters": {
          "rapid_invoice": false,
          "selected_distributors": false,
          "single_piece_drop_shipping": true,
          "seven_day_return": false,
          "single_piece_free_shipping": false,
          "free_shipping": true,
          "freight_insurance_return": true,
          "real_factory_verified": false,
          "strength_verified": false,
          "official_logistics": true,
          "encrypted_waybill": false
        }
      }
    ]
  }
}
```

### 6.2 运行时快照最小字段

每个渠道至少记录：

```json
{
  "channel_id": "ali1688",
  "channel_type": "ali1688",
  "configured_filters": ["single_piece_drop_shipping", "free_shipping"],
  "query_injected_filter_keys": ["single_piece_drop_shipping", "free_shipping"],
  "applied_filter_keys": ["single_piece_drop_shipping"],
  "unapplied_filter_keys": ["free_shipping"],
  "filter_status_map": {},
  "verification_details": {},
  "mapping_notes": []
}
```

### 6.3 结果追溯字段

本计划要求至少明确三层追溯：

1. 任务级
   - 本次用了哪些渠道
2. 渠道组级
   - 某个渠道用了哪些筛选项
3. 单条货源级
   - 这条货源记录对应的渠道快照

## 7. 筛选项分层调研与实施策略

### 7.1 第一批：优先做 query/runtime 验证闭环

这些项应优先推进到“真实影响搜索结果”的级别：

| key | 文案 | 当前判断 | 推进目标 |
|---|---|---|---|
| `rapid_invoice` | 极速开票 | query candidate | 验证 query 参数稳定性 |
| `single_piece_drop_shipping` | 一件代发 | strong query candidate | 保持第一优先级 |
| `free_shipping` | 包邮 | query candidate | 补足验证闭环 |
| `freight_insurance_return` | 退货包运费 | query candidate | 补足验证闭环 |
| `official_logistics` | 官方物流 | query candidate | 补足验证闭环 |

### 7.2 第二批：先做配置/快照，再做 UI 勾选验证

| key | 文案 | 当前判断 | 推进目标 |
|---|---|---|---|
| `selected_distributors` | 分销严选 | UI checkbox candidate | 先配置可保存，再验证 DOM 勾选 |
| `seven_day_return` | 7天无理由 | UI checkbox candidate | 同上 |
| `real_factory_verified` | 真实工厂认证 | UI checkbox candidate | 同上 |
| `strength_verified` | 实力认证 | UI checkbox candidate | 同上 |

### 7.3 第三批：组合语义项

| key | 文案 | 当前判断 | 推进目标 |
|---|---|---|---|
| `single_piece_free_shipping` | 1件代发包邮 | semantic combo candidate | 先证明其是不是独立项 |

### 7.4 第四批：特殊面板/特殊能力项

| key | 文案 | 当前判断 | 推进目标 |
|---|---|---|---|
| `encrypted_waybill` | 密文面单 | special panel candidate | 先确认是否属于常规筛选区 |

## 8. 决策资产库与详情页的计划约束

### 8.1 顶层资产卡片

只要求展示：

- 本次用了哪些渠道
- 每个渠道命中了多少货源

不要求在顶层卡片直接展示完整筛选条件全文，避免信息噪音过大。

### 8.2 详情页

详情页必须按渠道分区，并在渠道分区中补充：

- 渠道标签
- 使用账号标签
- 本次配置的筛选项
- 已生效筛选项
- 未生效筛选项与原因

### 8.3 单条货源卡片

单条货源至少要能看出：

- 它属于哪个渠道
- 它由哪个账号抓取
- 它对应的渠道筛选快照

## 9. 实施批次

### 阶段 0：计划与证据整理

目标：

- 把 11 个筛选项按映射策略重新分类
- 明确哪些先做、哪些后做、哪些只保留配置
- 明确资产库与详情页的展示边界

完成标准：

- `task_plan.md`
- `findings.md`
- `progress.md`
  已同步更新

状态：`completed`

### 阶段 1：配置层补齐“按渠道编辑筛选项”

涉及文件：

- `src/xianyu_tools/config.py`
- `src/web_api/main.py`
- `web/app.jsx`

任务：

1. 确认 `channel_search_filters` 的渠道粒度行为
2. 确认“新增渠道后筛选配置如何初始化”
3. 确认“未登录成功账号不能成为激活账号”的规则不会污染筛选配置
4. 在系统设置页中，让用户能明确知道“当前编辑的是哪个渠道的筛选条件”

验收：

- 不同渠道切换时，配置独立回显
- 关闭某渠道不影响其他渠道筛选配置
- 不支持该能力的渠道显示空态

状态：`in_progress`

### 阶段 2：运行时快照与结果追溯补齐

涉及文件：

- `scripts/run_full_pipeline.py`
- `scripts/run_ali1688_slow_flow.py`
- `src/web_api/main.py`

任务：

1. 把渠道筛选配置按渠道传到 runtime
2. 为每个渠道生成快照
3. 把快照写入单条货源结果
4. 把快照回流到任务详情接口

验收：

- 每条货源都可追溯到渠道筛选快照
- 详情页渠道组能显示筛选摘要

状态：`pending`

### 阶段 3：第一批 query 候选项真实接入

涉及文件：

- `src/xianyu_tools/channel_search_filters.py`
- `src/xianyu_tools/source_adapter/ali1688.py`
- `scripts/run_ali1688_slow_flow.py`
- `scripts/validate_source_channel_config.py`

任务：

1. 先固定 query 候选项的参数映射证据
2. 验证参数是否被最终 URL 保留
3. 验证结果集是否发生变化
4. 将状态从“configured/query_injected”升级到“applied”

验收：

- `rapid_invoice`
- `single_piece_drop_shipping`
- `free_shipping`
- `freight_insurance_return`
- `official_logistics`
  至少形成可重复验证的闭环

状态：`pending`

### 阶段 4：UI 勾选候选项与特殊面板项调研

涉及文件：

- `scripts/run_ali1688_slow_flow.py`
- 新增调研脚本（如需要）
- `plan/2026-06-25-channel-specific-crawl-filters/findings.md`

任务：

1. 采集真实页面结构证据
2. 确认 `selected_distributors / seven_day_return / real_factory_verified / strength_verified`
   是否能稳定定位
3. 确认 `encrypted_waybill` 是否在独立面板或常规区域
4. 若证据不足，明确保持为“snapshot_only”

验收：

- 每个项都有明确的后续处理结论
  - `query`
  - `ui`
  - `combo`
  - `snapshot_only`

状态：`pending`

### 阶段 5：决策资产库与详情页展示收口

涉及文件：

- `src/web_api/main.py`
- `web/app.jsx`

任务：

1. 顶层资产卡片展示渠道摘要
2. 详情页渠道分区展示筛选摘要
3. 保证单条货源卡片也能追溯渠道与筛选快照

验收：

- 用户在资产库顶层能看见“使用了哪些渠道”
- 用户进入详情页能看见“各渠道用的是什么策略”

状态：`pending`

### 阶段 6：联调与回归验证

涉及文件：

- `scripts/validate_source_channel_config.py`
- 手工联调清单（待补）

任务：

1. 配置保存/刷新回归
2. 多渠道切换回归
3. 抓取结果与详情回流回归
4. 历史任务降级展示验证

状态：`pending`

## 10. 调研执行顺序

### 10.1 先做代码证据

- 统一定义是否已存在
- 配置存储是否已接通
- runtime 是否已能接到快照

### 10.2 再做页面证据

- 哪些是 query 级
- 哪些必须点 UI
- 哪些属于特殊浮层或组合语义

### 10.3 最后做展示证据

- 任务级
- 渠道组级
- 单条货源级

## 11. 风险与回退策略

### 风险 1：部分筛选项没有稳定 query 参数

处理：

- 不猜参数
- 先保留为配置项与快照项

### 风险 2：部分筛选项必须点页面，且 DOM 不稳定

处理：

- 先记录为 `ui_checkbox_candidate`
- 维持 `snapshot_only`，不伪造“已生效”

### 风险 3：资产库展示层信息过载

处理：

- 顶层只展示渠道摘要
- 详情页再展示筛选细节

## 12. 验收清单

- [ ] 系统设置页可按渠道配置 11 个筛选项
- [ ] 不同渠道间的筛选配置互不污染
- [ ] 渠道配置能进入 runtime 快照
- [ ] 抓取结果能回写渠道筛选快照
- [ ] 决策资产库顶层能展示使用了哪些渠道
- [ ] 详情页能按渠道展示，并带出筛选摘要
- [ ] 第一批 query 候选项形成真实生效闭环
- [ ] 第二批/第三批/第四批项至少有明确降级与后续结论

## 13. 下一步建议

按顺序推进：

1. 阶段 1：确认并收口系统设置页的渠道级筛选配置行为
2. 阶段 2：把快照与详情链路彻底打通
3. 阶段 3：先攻第一批 query 候选项
