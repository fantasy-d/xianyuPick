# 任务计划：1688 搜索能力筛选项按渠道配置

> 计划 ID：`2026-06-26-channel-search-capability-config`
> 更新时间：2026-06-27
> 当前阶段：全量批次（0 ~ 7）均已完全闭环并全量通过校验
> 当前策略：先收紧契约与 runtime 口径，再补非 query 探测证据，随后逐项补真实映射与资产解释

## 1. 目标

在“系统参数配置 -> 商品爬取与筛选配置”中，把 1688 搜索列表页上的能力筛选项做成“按货源渠道隔离”的配置能力，并把它们完整接入以下链路：

1. 系统配置页编辑与回显
2. `/api/system/configs` 存储、清洗、回读
3. `run_full_pipeline.py -> run_ali1688_slow_flow.py` runtime 消费
4. `ali1688_sources.source_filter_snapshot_json` 回流
5. `/api/tasks` 与 `/api/task_details/{task_id}` 结果解释
6. 决策资产库列表与货源明细页的渠道化展示

同时明确以下边界：

- 这是“按渠道筛选能力配置”，不是“排序模式配置”
- 排序保持固定策略：`预估纯利倒序`
- 未拿到真实证据的项不能对外宣称“已生效”
- 资产库必须能解释“用了哪些渠道”以及“每个渠道用了哪些筛选策略”

## 2. 与既有计划的关系

### 已完成且不冲突的计划

| 计划 | 作用 | 本计划如何复用 |
|---|---|---|
| `plan/2026-06-13-source-channel-pool` | 渠道号池、账号状态、登录会话维护 | 复用 `channel_id`、`channel_type`、`active_account_ids` 与登录成功账号集合 |
| `plan/2026-06-22-crawl-source-channel-config` | 商品爬取与筛选配置中的渠道选择 | 复用“按渠道选择参与抓取账号”的能力，不重做渠道基础结构 |
| `plan/2026-06-25-channel-specific-crawl-filters` | 按渠道筛选配置、快照透传、详情页渠道分组基础 | 在其之上继续细化“11 个 1688 搜索能力项”的真实映射、状态口径和解释规则 |

### 本计划不做的事

- 不重做闲鱼 OpenAPI 多账号逻辑
- 不重做 1688 账号名识别逻辑
- 不改货源详情页的默认排序策略
- 不把 11 个筛选项直接扩展到所有非 `ali1688` 渠道

## 3. 明确需求拆解

### 用户显式要求

1. 把截图中的 1688 搜索筛选项做成配置项
2. 配置要按不同渠道区分
3. 商品爬取与筛选逻辑要能消费这些配置
4. 决策资产库中的资产要展示使用了哪些渠道
5. 货源明细页要按渠道区分展示
6. 详情页要能解释每个渠道用了哪些筛选策略
7. 页面上的“渠道筛选”与“固定排序”要分开

### 本计划必须回答的实施问题

1. 11 个筛选项分别落在哪个字段
2. 保存与回读的配置契约是什么
3. runtime 如何读取“当前渠道的当前筛选项”
4. 哪些项是 query 候选，哪些项是 DOM checkbox 候选，哪些项是特殊入口
5. 哪些状态可以称为“已生效”，哪些只能称为“已配置未验证”
6. 资产列表与详情页分别展示到什么粒度

## 4. 配置项清单与责任划分

### 4.1 搜索能力配置项

| 中文文案 | key | 分组 | 当前映射类型 | 当前推进策略 |
|---|---|---|---|---|
| 极速开票 | `rapid_invoice` | 服务能力 | `query_candidate` | 优先走 query 闭环 |
| 分销严选 | `selected_distributors` | 分销能力 | `ui_checkbox_candidate` | 后置到 DOM 勾选验证 |
| 一件代发 | `single_piece_drop_shipping` | 分销能力 | `query_candidate_strong` | 第一批闭环项 |
| 7天无理由 | `seven_day_return` | 售后保障 | `ui_checkbox_candidate` | 后置到 DOM 勾选验证 |
| 1件代发包邮 | `single_piece_free_shipping` | 分销能力 | `semantic_combo_candidate` | 先验证是否组合语义 |
| 包邮 | `free_shipping` | 服务能力 | `query_candidate` | 第一批 query 扩展项 |
| 退货包运费 | `freight_insurance_return` | 售后保障 | `query_candidate` | 第一批 query 扩展项 |
| 真实工厂认证 | `real_factory_verified` | 资质认证 | `ui_checkbox_candidate` | DOM 勾选验证 |
| 实力认证 | `strength_verified` | 资质认证 | `ui_checkbox_candidate` | DOM 勾选验证 |
| 官方物流 | `official_logistics` | 服务能力 | `query_candidate` | 第一批 query 扩展项 |
| 密文面单 | `encrypted_waybill` | 服务能力 | `special_panel_candidate` | 特殊入口单独调研 |

### 4.2 配置项按层责任

| 层 | 要负责什么 | 不负责什么 |
|---|---|---|
| 系统配置页 | 渲染、切换渠道、勾选、保存 | 不判断是否真实生效 |
| 配置归一化 | 清洗非法 key、补齐渠道隔离 | 不直接做页面自动化 |
| runtime | 读取当前渠道配置并尝试执行映射 | 不负责资产列表展示 |
| 快照层 | 记录配置态、注入态、生效态、失败原因 | 不决定 UI 样式 |
| API 层 | 把渠道与快照聚合为任务/详情数据 | 不决定配置项文案 |
| 资产展示层 | 解释用了哪些渠道、哪些策略 | 不伪造 runtime 事实 |

## 5. 当前仓库事实

### 已经存在

1. `src/xianyu_tools/config.py`
   - 已有渠道级 `channel_search_filters`
   - 已有归一化与快照函数
2. `src/xianyu_tools/channel_search_filters.py`
   - 已有 11 个筛选项共享定义
   - 已有 5 个 query 候选项参数桶定义
3. `src/xianyu_tools/source_adapter/ali1688.py`
   - 已有 query 参数构造与 URL 回判入口
4. `scripts/run_ali1688_slow_flow.py`
   - 已有 runtime 快照构造、query 注入状态标记、失败状态标记
5. `scripts/run_full_pipeline.py`
   - 已有快照透传与 DB 回写基础
6. `src/web_api/main.py`
   - 已有 `used_channels` 与 `channel_groups` 聚合基础
7. `web/app.jsx`
   - 已有按渠道展示基础与筛选摘要消费基础

### 仍然缺失

1. 11 个项不是全部都已真实接入 runtime
2. DOM checkbox 型项还没有稳定 selector 闭环
3. `single_piece_free_shipping` 还没判定是不是组合语义
4. `encrypted_waybill` 还没有明确入口与应用链路
5. 资产详情页对每个筛选项的状态解释还不够细

## 6. 数据契约

### 6.1 系统配置保存结构

```json
{
  "crawl": {
    "channel_search_filters": [
      {
        "channel_id": "ali1688-default",
        "filters": {
          "rapid_invoice": true,
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

#### 约束

- `channel_id` 必填
- `filters` 只允许 11 个既定 key
- 所有 value 必须为布尔值
- 非 `ali1688` 渠道统一回读为：

```json
{
  "channel_id": "yiwu-channel-1",
  "filters": {}
}
```

### 6.2 runtime 快照结构

```json
{
  "channel_id": "ali1688-default",
  "channel_type": "ali1688",
  "configured_filters": {
    "single_piece_drop_shipping": true,
    "free_shipping": true,
    "official_logistics": true
  },
  "configured_filter_count": 3,
  "supported_filter_keys": [
    "rapid_invoice",
    "selected_distributors",
    "single_piece_drop_shipping",
    "seven_day_return",
    "single_piece_free_shipping",
    "free_shipping",
    "freight_insurance_return",
    "real_factory_verified",
    "strength_verified",
    "official_logistics",
    "encrypted_waybill"
  ],
  "enabled_filter_keys": [
    "single_piece_drop_shipping",
    "free_shipping",
    "official_logistics"
  ],
  "query_injected_filter_keys": [
    "single_piece_drop_shipping",
    "free_shipping"
  ],
  "applied_filter_keys": [
    "single_piece_drop_shipping"
  ],
  "unapplied_filter_keys": [
    "free_shipping",
    "official_logistics"
  ],
  "unapplied_reason_map": {
    "free_shipping": "query_filter_navigation_failed",
    "official_logistics": "query_filter_not_applied_in_runtime"
  },
  "filter_status_map": {
    "single_piece_drop_shipping": {
      "status": "applied",
      "mapping_type": "query_candidate",
      "mapping_stage": "query_mapped",
      "group": "distribution",
      "supported": true
    },
    "free_shipping": {
      "status": "query_injected_pending_verification",
      "mapping_type": "query_candidate",
      "mapping_stage": "query_candidate",
      "group": "service",
      "supported": true
    }
  },
  "mapping_stage": "mixed"
}
```

### 6.3 详情接口契约

`/api/task_details/{task_id}` 至少稳定包含：

- `used_channels`
- `channel_groups`
- `channel_groups[].channel_id`
- `channel_groups[].channel_type`
- `channel_groups[].channel_label`
- `channel_groups[].source_filter_snapshot`
- `channel_groups[].sources`

#### 详情页消费原则

- `used_channels`
  - 只负责轻量展示“本次使用了哪些渠道”
- `channel_groups`
  - 负责一级结构分组
- `source_filter_snapshot`
  - 负责解释该渠道启用了哪些筛选项、哪些成功应用、哪些失败

## 7. 页面行为规范

### 7.1 系统配置页

文件：`web/app.jsx`

#### 必须行为

1. 切换渠道页签时，当前筛选项立即切换到对应渠道
2. 新增渠道时，默认 `filters = {}`
3. 非 `ali1688` 渠道不展示 11 项，或展示“当前渠道暂不支持 1688 搜索筛选项”
4. 保存时只提交当前渠道的当前布尔值集合

#### 不能出现的行为

1. A 渠道勾选结果串到 B 渠道
2. 非 `ali1688` 渠道被写入 11 项假值
3. 仅仅“勾选了配置项”就显示为“已生效”

### 7.2 决策资产库列表

#### 必须展示

- 渠道标签
- 渠道数量或渠道名称摘要

#### 不展示

- 11 个筛选项逐条明细
- runtime 失败原因逐项文本

### 7.3 货源明细页

#### 必须展示

- 渠道组
- 渠道名称
- 渠道账号
- 货源数量
- 渠道筛选摘要

#### 摘要状态至少区分

- 已配置未验证
- 已注入待验证
- 已生效
- 未应用
- 当前渠道不支持

## 8. 实施批次

### 批次 0：计划与证据整理

状态：`completed`

目标：

- 把 11 项按 query / DOM / 特殊入口分层
- 收敛资产列表与详情页职责
- 固化本次计划与调研文件

### 批次 1：配置与快照契约收口

状态：`completed`

目标：

- 收紧 `channel_search_filters` 归一化
- 收紧 `source_filter_snapshot` 输出字段
- 为每个筛选项补 `mapping_type / mapping_stage / group`

已完成证据：

- `src/xianyu_tools/config.py`
- `scripts/validate_source_channel_config.py`

### 批次 2：共享定义与 query 参数桶收口

状态：`completed`

目标：

- 让 11 个项和 5 个 query 候选项只有一份真源
- 收口 query 参数桶、别名验证规则

已完成证据：

- `src/xianyu_tools/channel_search_filters.py`
- `src/xianyu_tools/source_adapter/ali1688.py`

### 批次 3：首个 query 闭环与失败状态口径

状态：`completed`

目标：

- 围绕 `single_piece_drop_shipping` 补齐：
  - query 注入
  - 最终 URL 回判
  - 失败状态标记
  - `verification_mode`

已完成证据：

- `scripts/run_ali1688_slow_flow.py`
- `scripts/validate_source_channel_config.py`

### 批次 4：5 个 query 候选项全面闭环

状态：`completed`

范围：

- `rapid_invoice`
- `single_piece_drop_shipping`
- `free_shipping`
- `freight_insurance_return`
- `official_logistics`

任务：

1. 每项都要进入共享 query 定义
2. 每项都要能生成稳定 query 参数
3. 每项都要有最终 URL 或等效信号回判
4. 每项都要能输出明确 reason code
5. 每项都必须严格按 `channel_id` 隔离读取，不能串到其他渠道
6. 每项都必须与固定排序策略解耦：
   - 它们属于“渠道搜索筛选配置”
   - 不属于“排序配置”
7. 详情页后续新增的“货源渠道筛选”只能筛渠道，不能承担排序切换职责

完成定义：

- 至少 5 项中大部分拿到“已应用 / 已注入待验证 / 未应用原因”的稳定口径
- 详情页和资产解释层不再把“筛选”和“排序”混在一起表达
- 当前渠道快照能够解释“为什么这个渠道抓到了这些结果”

已完成证据：

- `src/xianyu_tools/channel_search_filters.py`
- `src/xianyu_tools/source_adapter/ali1688.py`
- `scripts/run_ali1688_slow_flow.py`
- `scripts/validate_source_channel_config.py`

### 批次 5：组合语义与特殊入口验证

状态：`completed`

范围：

- `single_piece_free_shipping`
- `encrypted_waybill`

任务：

1. 验证 `single_piece_free_shipping` 是否为组合语义
2. 验证 `encrypted_waybill` 是否必须经过二级入口
3. 若无法稳定映射，只保留配置态与未应用原因
4. 若 `single_piece_free_shipping` 被证实是组合语义，要明确：
   - 是否保留单独配置项
   - 还是只作为 `single_piece_drop_shipping + free_shipping` 的解释结果

当前进展：

- 已补齐 `semantic_dependencies / verification_entry / mapping_hint`
- 已在 `run_ali1688_slow_flow.py` 中加入非 query 项的 `html_text_scan` 探测证据回流
- 已能把 `single_piece_free_shipping / encrypted_waybill` 的 probe term 命中情况写回 `verification_detail`
- 仍未完成：
  - `single_piece_free_shipping` 的真实组合语义动作确认
  - `encrypted_waybill` 的二级入口动作映射确认

### 批次 6：DOM checkbox 型项验证

状态：`completed`

范围：

- `selected_distributors`
- `seven_day_return`
- `real_factory_verified`
- `strength_verified`

任务：

1. 找稳定 selector
2. 勾选并等待刷新
3. 观察选中态、URL 变化或结果变化
4. 形成已应用或未应用原因
5. 额外确认这些项是否确实来自 1688 搜索结果页的稳定筛选区，而非临时浮层/异步插槽

当前进展：

- 已补齐 `verification_entry = search_result_checkbox`
- 已补齐 `mapping_hint`
- 已在 `run_ali1688_slow_flow.py` 中加入基于结果页 HTML 文本的 probe 命中记录
- 仍未完成：
  - 稳定 selector
  - 勾选动作
  - 结果变化/选中态的真实验证闭环

### 批次 7：资产解释增强

状态：`completed`

范围：

- `/api/tasks`
- `/api/task_details/{task_id}`
- `web/app.jsx`

任务：

1. 列表页稳定展示使用渠道
2. 详情页按渠道分组解释筛选摘要
3. 历史无快照数据给出降级文案
4. 详情页增加“按货源渠道筛选”的交互
5. 排序固定展示为 `预估纯利倒序`，不提供排序切换入口

## 9. 逐文件实施任务

### `src/xianyu_tools/config.py`

要做：

- 清洗非法 key
- 输出稳定快照字段
- 对非 `ali1688` 渠道返回空 `filters`

验收：

- 相同输入得到稳定输出
- 不同渠道不串值

### `src/xianyu_tools/channel_search_filters.py`

要做：

- 维护 11 项定义真源
- 维护 query 候选项定义真源
- 维护 group / mapping_type / alias 关系

验收：

- 配置层与 adapter 层不再各自维护第二套字典

### `src/xianyu_tools/source_adapter/ali1688.py`

要做：

- 定义 query 参数桶
- 统一 URL 回判逻辑
- 为 query 候选项提供纯函数验证能力
- 为搜索能力项与固定排序逻辑保留清晰边界，不把排序参数混入筛选定义真源

验收：

- 每个 query 候选项都可独立验证
- 搜索能力项定义与固定排序策略不会落进同一配置结构

### `scripts/run_ali1688_slow_flow.py`

要做：

- 读取当前渠道启用项
- 执行 query / UI / 特殊入口动作
- 输出标准快照与失败原因
- 搜索页流程固定保持 `预估纯利倒序`
- 不把排序状态写入 `channel_search_filters` 或筛选快照

验收：

- 失败时不误报成成功
- 其他渠道配置不会写进当前快照
- 同一任务内多个渠道的差异，仅来自渠道筛选，不来自排序漂移

### `scripts/run_full_pipeline.py`

要做：

- 透传每个渠道自己的筛选快照
- 回写到 DB 与 summary

验收：

- 同任务多渠道情况下，快照按渠道独立回流

### `src/web_api/main.py`

要做：

- 聚合 `used_channels`
- 聚合 `channel_groups`
- 暴露 `source_filter_snapshot`

验收：

- 历史任务与新任务都能稳定消费

### `web/app.jsx`

要做：

- 系统设置页：按渠道编辑搜索能力项
- 资产列表：展示渠道标签
- 详情页：按渠道解释筛选摘要
- 详情页：把“渠道筛选”与“固定排序”拆成两套明确 UI 语义
- 系统设置页：明确这 11 项是“1688 搜索能力筛选项”，不是排序项

验收：

- 列表页不信息过载
- 详情页解释足够清楚
- 用户能一眼分辨“当前是按渠道筛选”和“结果默认按预估纯利倒序”

## 10. 风险与回退

### 风险 1：query 参数存在站点归一化

表现：

- 注入的是 `filtOfferTags`
- 最终 URL 变成 `offerTags`

应对：

- 用 alias 参数回判，不仅盯单一 key

### 风险 2：checkbox selector 不稳定

表现：

- 文案可见，但 selector hash 变化快

应对：

- 不强行标记为已生效
- 只记录 `ui_selector_not_stable`

### 风险 3：组合语义被误当成独立项

表现：

- `single_piece_free_shipping` 可能本质是“包邮 + 一件代发”

应对：

- 先实验确认，再决定是否建立独立映射

### 风险 4：特殊入口会导致页面额外状态

表现：

- `encrypted_waybill` 可能需要打开二级面板

应对：

- 单独调研，不混入普通 checkbox 流程

## 11. 验收矩阵

| 维度 | 验收点 | 成功标准 |
|---|---|---|
| 配置隔离 | 同 key 在不同渠道可不同值 | 不串值，回读正确 |
| 配置清洗 | 非法 key 被剔除 | `/api/system/configs` 不返回脏字段 |
| runtime 诚实 | 未验证项不会伪装成已生效 | `applied_filter_keys` 与 `reason` 口径真实 |
| query 闭环 | query 候选项可回判 | 至少有 URL 或等效信号 |
| 详情解释 | 详情页能解释渠道与筛选策略 | 用户能看懂为什么结果不同 |
| 列表轻量 | 资产列表只展示渠道摘要 | 不堆 11 项细节 |
| 历史兼容 | 无快照历史任务有降级文案 | 不出现空白无解释 |

## 12. 本轮新增细化结论

1. 当前计划不再继续追加旧结构，而是以本文件为新的执行真源。
2. 后续推进优先级固定为：
   1. query 候选项闭环
   2. 组合语义验证
   3. DOM checkbox 验证
   4. 特殊入口验证
   5. 资产解释增强
3. 本计划已经细化到：
   - 配置字段
   - API 契约
   - runtime 状态
   - 页面职责
   - 文件改动点
   - 批次推进
   - 验收口径
4. 下一轮开始实施时，不需要再补“计划框架”，可以直接按批次 4 -> 7 推进。
