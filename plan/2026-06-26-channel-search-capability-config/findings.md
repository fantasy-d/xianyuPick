# 调研结论：1688 搜索能力筛选项按渠道配置

> 本文件只记录“当前已确认的事实”和“实现时必须坚持的边界”，不再重复大段计划正文。

## 1. 已确认事实

### 1.1 配置骨架已经存在

- `src/xianyu_tools/config.py`
  - 已有渠道级 `channel_search_filters`
  - 已有归一化与快照输出入口
- `web/app.jsx`
  - 已有 11 项配置 UI 基础
  - 已有按渠道切换基础

结论：

- 这次不是从零做 schema
- 重点在 runtime 映射、快照口径、资产解释

### 1.2 快照与结果回流链路已经存在

- `scripts/run_full_pipeline.py`
  - 已能透传 `source_filter_snapshot`
  - 已能写回 DB
- `src/web_api/main.py`
  - 已能返回 `used_channels`
  - 已能返回 `channel_groups`
- `web/app.jsx`
  - 已有消费 `channel_groups` 与筛选摘要的基础

结论：

- 不需要新建第二条结果回流通道
- 应继续复用现有 `source_filter_snapshot`

### 1.3 当前真实缺口在 runtime 生效层

- 不是 11 项都没做
- 也不是 11 项都已生效
- 当前最核心的缺口是：
  - 哪些项真实进入了 1688 搜索行为
  - 哪些项只是“配置留痕”
  - 哪些项已注入但还没完成结果级验证

## 2. 已确认的项分层

### 2.1 Query 候选优先组

- `rapid_invoice`
- `single_piece_drop_shipping`
- `free_shipping`
- `freight_insurance_return`
- `official_logistics`

原因：

- 已拿到 query / tag 级证据
- 更适合先做纯函数验证和 runtime 闭环

### 2.2 DOM checkbox 候选组

- `selected_distributors`
- `seven_day_return`
- `real_factory_verified`
- `strength_verified`

原因：

- 当前主要证据是结果页筛选区文本或 checkbox 文案
- 需要 selector 稳定性验证

### 2.3 特殊处理组

- `single_piece_free_shipping`
  - 当前必须先验证是否是组合语义
- `encrypted_waybill`
  - 当前必须先验证是否属于特殊入口 / 二级面板

## 3. 实现边界

### 3.1 不能把“已配置”写成“已生效”

仅满足以下其中之一时，都只能算未验证：

- 勾选了配置项
- 参数注入了 URL
- 页面文案中看到了该项
- 详情页能回显该项

必须拿到最终结果级证据，才能升级为“已生效”。

### 3.2 “按渠道区分”至少要同时落在 3 层

1. 配置存储：`channel_id -> filters`
2. runtime 消费：当前抓取渠道只读取自己的配置
3. 详情展示：每个 `channel_group` 只解释自己的快照

### 3.3 列表页与详情页职责必须分开

- 列表页：
  - 只回答“用了哪些渠道”
- 详情页：
  - 解释“该渠道启用了哪些筛选项、哪些应用了、哪些失败了”

## 4. 资产库联动必须保留的最小事实

为了保证决策资产库可解释，后续快照必须稳定保留：

- `configured_filters`
- `enabled_filter_keys`
- `applied_filter_keys`
- `unapplied_filter_keys`
- `unapplied_reason_map`
- `filter_status_map`
- `mapping_stage`

否则会出现：

- 资产虽然按渠道分组了
- 但用户仍然看不懂为什么两个渠道结果不同

## 5. 当前最重要的实施结论

1. 先做 query 候选项，不先做 checkbox 大面积接入
2. 先保证 runtime 诚实，再追求“更多项已生效”
3. 先把详情页解释清楚，再考虑列表页加更多信息
4. `single_piece_free_shipping` 与 `encrypted_waybill` 要单独验证，不和普通项混做

## 7. 本轮补充边界（2026-06-27）

### 7.1 搜索能力项与排序策略不是一回事

- `极速开票 / 分销严选 / 一件代发 / 7天无理由 / 1件代发包邮 / 包邮 / 退货包运费 / 真实工厂认证 / 实力认证 / 官方物流 / 密文面单`
  - 都属于“按渠道隔离的搜索筛选配置”
- `预估纯利倒序`
  - 属于固定排序策略
  - 不是系统配置项
  - 不应该写进 `channel_search_filters`

### 7.2 详情页后续必须拆成两层语义

1. 固定说明：
   - 当前排序：`预估纯利倒序`
2. 可交互项：
   - 按货源渠道筛选当前结果

结论：

- 后续实现时，如果代码里把“渠道筛选”和“排序切换”混进同一个状态或同一个控件，需要优先拆开。

## 6. 本轮新增细化结论

1. 计划文件已经重整为“可执行版本”，不再继续依赖旧的追加式结构。
2. 后续实施应直接按以下顺序推进：
   - query 闭环
   - 资产解释增强
   - 组合语义验证
   - DOM checkbox 验证
   - 特殊入口验证
3. 之后每次推进实现时，只需要同步更新：
   - `task_plan.md`
   - `implementation_research.md`
   - `progress.md`
4. 如果某项验证失败，必须把失败原因写入快照和计划，而不是重试同一条路径后当作“暂时忽略”。
