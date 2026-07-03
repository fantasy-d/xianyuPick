# 任务计划：1688 搜索能力筛选项按渠道配置

> 计划 ID：`2026-06-26-channel-search-capability-config`
> 更新时间：2026-07-03
> 当前阶段：completed
> 当前策略：真实运行审计已经通过人工验证码跑到搜索结果与详情页；`一件代发`、`包邮`、`分销严选`、`1件代发包邮`、`密文面单` 均已有真实强证据。真实审计、入库、接口解释与页面级验收均已闭环，后续新需求应另起计划，不再继续追加到本计划。

## 0.3 本轮新增约束：1688 顶部筛选条按渠道配置

本轮继续推进时，必须同时满足下面 5 条，不允许只做 UI 勾选而忽略 runtime / 资产解释：

1. 截图中的顶部筛选项仍统一归属 `channel_search_filters`
   - `极速开票`
   - `分销严选`
   - `一件代发`
   - `7天无理由`
   - `1件代发包邮`
   - `包邮`
   - `退货包运费`
   - `真实工厂认证`
   - `实力认证`
   - `官方物流`
   - `密文面单`
   - 这些中文标签必须来自共享定义真源，不能只在前端或文档中散落硬编码
2. 这些项必须严格按 `channel_id` 保存、回读、运行时消费、快照回流与详情解释
3. 同一任务若启用多个 1688 渠道，不同渠道的顶部筛选项不能串值，也不能共用“最近一次全局勾选状态”
4. 决策资产库列表与详情页都必须能说明“本次货源是从哪些渠道抓到的”，且详情页要能进一步说明“每个渠道用了哪些顶部筛选项”
5. 货源明细页中的排序必须保持固定策略：
   - `预估纯利倒序`
   - 渠道筛选只是过滤展示范围，不承担排序语义

## 0.1 当前完成状态总览

为避免后续推进被旧记录误导，本计划的 3 个收尾批次当前状态如下：

| 批次 | 核心对象 | 要达成的结果 | 当前约束 |
|---|---|---|---|
| 批次 5 | `single_piece_free_shipping`、`encrypted_waybill` | 统一结论字段、真实动作链路、灰区状态解释全部收口 | completed |
| 批次 6 | DOM checkbox 项、配置回读、runtime 渠道隔离 | 配置保存、配置回读、运行时消费三层口径完全一致 | completed |
| 批次 7 | 资产列表、货源明细页、详情接口 | 渠道筛选与固定排序彻底解耦，渠道解释可被用户直接读懂 | completed |

当前真实审计样本：

- 输出目录：`scratch/channel_filter_real_audit_manual_20260702_full_closure`
- 审计阶段：`summary_written`
- 映射阶段：`mixed`
- 结论：人工验证码后已进入真实搜索结果与详情页；`single_piece_drop_shipping`、`free_shipping`、`selected_distributors`、`single_piece_free_shipping`、`encrypted_waybill` 均已获得真实强证据，`pending_filter_count = 0`

页面级验收样本：

- 任务 ID：`cf20260702`
- 任务名：`1688筛选闭环页面验收样本`
- 验收结论：决策资产列表、任务报告页、商品详情页均已基于真实入库数据完成页面级验收。

## 0.2 剩余工作统一验收顺序

每一批都按同一顺序推进，不允许只做一半就宣称完成：

1. 先补共享定义或契约层
2. 再补 runtime 或 API 回流
3. 再补前端消费与解释
4. 最后补静态校验、fixture 校验与计划文档同步

只有同时满足以下 4 点，才允许把某一批改成 `completed`：

1. 代码层已有对应实现
2. 至少有一组静态校验或 fixture 校验锁住契约
3. 前端 / API 不再需要自行猜测状态语义
4. `progress.md` 与本计划中的“当前进展”已经同步

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

### 4.3 渠道级“顶部筛选能力”与账号池的关系

为避免后续实现把“渠道配置”和“账号登录态”混成一层，这里单独锁定边界：

1. `channel_search_filters`
   - 表达“这个渠道在抓取时希望尝试哪些顶部筛选能力”
   - 归属渠道，不归属单个账号
2. `active_account_ids`
   - 表达“这个渠道本次允许哪些账号参与抓取”
   - 归属渠道账号池，不携带顶部筛选语义
3. runtime 真实执行时的关系只能是：
   - 先选当前渠道
   - 再拿该渠道的激活账号
   - 再消费该渠道自己的 `channel_search_filters`
4. 账号登录失败时，只能影响：
   - 该渠道本次是否能执行真实页面动作
   - 不能把别的渠道的顶部筛选配置借来兜底
5. 详情解释时必须区分：
   - “当前渠道配置了什么”
   - “当前渠道本次实际使用了哪个账号”
   - “当前账号是否让这些配置真正进入 runtime”

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

分解步骤：

1. 统一结论字段收口
   - 文件：
     - `src/xianyu_tools/config.py`
     - `scripts/validate_source_channel_config.py`
     - `web/app.jsx`
   - 目标：
     - `semantic_combo_candidate` 统一沉淀 `semantic_conclusion`
     - `special_panel_candidate` 统一沉淀 `special_panel_conclusion`
   - 验收：
     - 顶层投影、`filter_status_map`、前端解释三处口径一致
2. 真实动作链路收口
   - 文件：
     - `scripts/run_ali1688_slow_flow.py`
   - 目标：
     - 图搜结果页与标准搜索页都能识别布局
     - 对可见入口尽量走真实点击链路
   - 验收：
     - 至少能明确区分：
       - 入口未映射
       - 面板打开失败
       - 动作成功但结果未变
       - 动作成功且结果变化
3. 灰区状态回归补齐
   - 文件：
     - `scripts/validate_source_channel_config.py`
   - 目标：
     - 对“已看到入口但未完成动作”“动作成功但结果不变”等中间态补断言
   - 验收：
     - `special_panel_candidate` 与 `semantic_combo_candidate` 的关键灰区分支都有静态校验
4. 结论文案与计划同步
   - 文件：
     - `web/app.jsx`
     - `plan/2026-06-26-channel-search-capability-config/progress.md`
     - `plan/2026-06-26-channel-search-capability-config/implementation_research.md`
   - 验收：
     - UI 优先展示统一结论，再补原始证据
     - 文档明确哪些仍属“证据已收口，但浏览器级回归未完成”

当前进展：

最终闭环结论：

- `single_piece_free_shipping` 已按 `single_piece_drop_shipping + free_shipping` 依赖组合强证据闭环。
- `encrypted_waybill` 已按真实页面已选条件条 `密文面单：抖音面单` 闭环。
- 真实审计样本 `scratch/channel_filter_real_audit_manual_20260702_full_closure` 中 `pending_filter_count = 0`。

- 已补齐 `semantic_dependencies / verification_entry / mapping_hint`
- 已在 `run_ali1688_slow_flow.py` 中加入非 query 项的 `html_text_scan` 探测证据回流
- 已能把 `single_piece_free_shipping / encrypted_waybill` 的 probe term 命中情况写回 `verification_detail`
- `single_piece_free_shipping`
  - 当页面命中 `1件代发包邮`
  - 且 `single_piece_drop_shipping + free_shipping` 已同时开启
  - 当前已升级为更诚实的中间态：
    - `reason = snapshot_only_until_semantics_confirmed`
    - `mapping_stage = mixed`
  - 并且已新增更强的页面证据：
    - 在图搜结果页中，该项以独立 `bottomFilterOption` 形式出现
    - runtime 已可把这条证据写入：
      - `verification_detail.independent_ui_entry_observed = true`
- `encrypted_waybill`
  - 当结果页命中 `密文面单`
  - 当前已升级为更细的特殊入口中间态：
    - `reason = special_panel_entry_detected_unmapped`
    - `mapping_stage = mixed`
  - 并且已经结构化保留：
    - `observation_scope = result_page_text`
    - `entry_signal_type = text_term`
    - `next_required_action = panel_open_and_toggle`
- 已在 `run_ali1688_slow_flow.py` 中补入第一版 `special_panel_candidate` runtime helper：
  - 会先尝试命中 `密文面单` 文案
  - 若当前不可见，则尝试通过 `配置筛选 / 高级筛选 / 更多筛选 / 筛选` 打开面板
  - 再执行入口点击，并回写：
    - `panel_trigger_text`
    - `panel_trigger_clicked`
    - `entry_click_attempted`
    - `entry_click_succeeded`
    - `panel_term_selected_before_action`
    - `panel_term_selected_after_action`
- 已把 `special_panel_open_failed` 从“文档中的保留原因码”推进到真实 runtime 分支：
  - 当已尝试打开/点击特殊入口
  - 但未观察到选中态
  - 当前会回写：
    - `reason = special_panel_open_failed`
    - `mapping_stage = mixed`
- 已补本地 Playwright fixture 回归：
  - 成功场景：面板打开并勾选后，`encrypted_waybill -> applied / ui_automation`
  - 图搜结果页布局场景：入口直接挂在 `configFilter / configLabel` 容器时，也能完成 `applied / ui_automation`
  - 失败场景：面板打开链路未完成时，`encrypted_waybill -> special_panel_open_failed`
- 已确认真实 1688 页面至少存在两套不同筛选 DOM：
  - 标准搜索页：
    - 可见 `高级筛选`
    - 主要候选容器为 `.search-filt-item / .sn-row / .sn-select-wrap`
  - 图搜结果页：
    - 不存在 `高级筛选 / 配置筛选` 文案入口
    - `密文面单` 挂在 `configFilter / configLabel`
    - `分销严选 / 一件代发 / 1件代发包邮 / 官方物流` 等挂在 `bottomFilterOption`
- 已在 `run_ali1688_slow_flow.py` 中增加页面布局识别与入口策略分流：
  - `image_result_filter_bar`
  - `standard_search_filter_bar`
  - 并把 `page_filter_layout / entry_selector_strategy` 回写进 `verification_detail`
- 已在 `run_ali1688_slow_flow.py` 中新增“结果页可见筛选项点击链路”：
  - 覆盖：
    - `ui_checkbox_candidate`
    - `semantic_combo_candidate`
  - 当图搜结果页中对应入口已可见时：
    - 会尝试点击真实容器
    - 观察选中态
    - 成功则回写 `status = applied / mapping_stage = ui_automation`
    - 失败则回写 `reason = ui_apply_not_observed`
- 已补入动作前后结果页签名采样：
  - 当前 `ui_checkbox_candidate / semantic_combo_candidate / special_panel_candidate`
  - 都会把以下字段写入 `verification_detail`：
    - `result_signature_before_action`
    - `result_signature_after_action`
    - `result_signature_changed`
  - 这意味着后续在真实 1688 页面上继续验证时，可以直接判断：
    - 只有入口与选中态变化
    - 还是连结果集签名也发生了变化
- 已为 `single_piece_free_shipping` 增加更细的语义阶段字段：
  - 依赖配置态：
    - `dependency_pair_enabled`
    - `dependency_pair_incomplete`
  - 独立入口动作态：
    - `direct_entry_result_shift_observed`
    - `direct_entry_result_shift_not_observed`
  - 这一步的目标不是提前宣称“语义独立已证实”，而是把当前证据分层收紧为：
    - 依赖是否齐备
    - 独立入口动作后是否已观察到结果变化
- 已把组合语义候选项的分散证据继续收口为统一结论字段：
  - `semantic_conclusion`
  - 当前已覆盖：
    - `dependency_pair_incomplete`
    - `dependency_pair_ready_pending_runtime`
    - `independent_entry_observed_pending_result_validation`
    - `independent_entry_no_result_shift`
    - `independent_entry_result_shift_observed`
  - 这意味着后续 UI / API / 快照消费时，可先读统一语义结论，再补充展示原始细节证据
- 已新增顶层快照契约回归：
  - `semantic_combo_verification_detail_projection`
  - 用于锁定以下证据不会只停留在 `filter_status_map`，而会继续投影到顶层消费字段：
    - `independent_ui_entry_observed`
    - `result_signature_changed`
    - `semantic_verification_stage`
    - `semantic_conclusion`
- 已把特殊入口候选项的分散证据继续收口为统一入口结论字段：
  - `special_panel_conclusion`
  - 当前已覆盖：
    - `entry_signal_detected_pending_panel_mapping`
    - `panel_open_or_toggle_failed`
    - `panel_action_applied_no_result_shift`
    - `panel_action_result_shift_observed`
  - 这意味着后续 UI / API / 快照消费时，对 `encrypted_waybill` 也可以先读统一入口结论，再补充展示动作细节
- 已新增静态顶层快照契约回归：
  - `special_panel_verification_detail_projection`
  - 用于锁定 `special_panel_conclusion` 会继续投影到顶层消费字段
- 已继续补强批次 5 灰区静态回归：
  - `validate_semantic_combo_no_result_shift_projection()`
  - `validate_special_panel_applied_no_result_shift_projection()`
  - 当前除了 `verification_details / filter_status_map` 以外，也会继续锁定：
    - `query_verification_details`
- 已继续补强 `html_text_scan` 中间态的顶层投影契约：
  - `validate_non_query_filter_runtime_html_probe()`
  - `validate_non_query_filter_runtime_html_probe_without_dependencies()`
  - 当前已锁住以下统一结论在中间态场景下也必须进入：
    - `verification_details`
    - `query_verification_details`
  - 覆盖值包括：
    - `dependency_pair_incomplete`
    - `dependency_pair_ready_pending_runtime`
    - `entry_signal_detected_pending_panel_mapping`
- 已把批次 5 的成功态统一结论也改成纯静态可验证：
  - `validate_semantic_combo_verification_detail_projection()`
    - 当前已继续锁定：
      - `query_verification_details["single_piece_free_shipping"]["semantic_conclusion"]`
  - `validate_special_panel_result_shift_observed_projection()`
    - 当前会纯静态锁定：
      - `panel_action_result_shift_observed`
      - 同时进入：
        - `verification_details`
        - `query_verification_details`
        - `filter_status_map`
- 已补本地 Playwright fixture 回归：
  - `selected_distributors` 图搜底部筛选项点击成功 -> `applied`
  - `single_piece_free_shipping` 图搜底部筛选项点击成功 -> `applied`
  - `selected_distributors` 点击后无选中态 -> `ui_apply_not_observed`
  - `selected_distributors / single_piece_free_shipping / encrypted_waybill`
    - 动作成功后都已验证会记录结果页签名变化
- 已新增真实运行审计产物分类工具：
  - `scripts/inspect_channel_filter_runtime_audit.py`
  - 用于读取真实输出目录中的 `_channel_filter_runtime_snapshot.json`
  - 只有同时具备选中态与结果签名变化的项，才会进入 `strong_evidence_filter_keys`
  - 这能避免把“只看到入口 / 只点击过 / 只选中但无结果变化”的弱证据误判为真实闭环
  - 当前已支持多个路径与 `--recursive` 批量扫描
  - 批量扫描报告当前已补齐渠道级强证据索引：
    - `strong_evidence_filter_keys_by_channel`
    - 用于直接查看每个 `channel_id` 自己形成了哪些强证据
    - 避免后续资产解释或验收只依赖全局 `strong_evidence_filter_keys`
  - 批量扫描报告当前已补齐渠道级待验证索引：
    - `pending_filters_by_channel`
    - 用于直接查看每个 `channel_id` 自己有哪些仍待验证 / 未闭环筛选项
    - 每条待验证项继续保留来源 `audit_file`，便于回查真实运行输出目录
  - 早期扫描 `outputs scratch` 结果为 `audit_file_count = 0`，该记录仅用于说明审计工具能识别无产物失败场景，不代表当前最终闭环状态
  - 当前已支持 `--required-filter` / `--require-configured-channel` 验收门槛：
    - 只有 required filters 全部进入 `strong_evidence_filter_keys`
    - 且 `missing_strong_filter_keys = []`
    - 且 `passed = true`
    - 才能关闭对应真实站点缺口
    - 当前已支持 `--strict-exit`：
      - 默认模式保持兼容，只打印报告并返回 0
      - 显式传入 `--strict-exit` 时，若 `passed = false` 则返回 1
      - 后续 CI / 自动脚本可以用该开关直接拦截未闭环缺口
    - 当前已支持 `missing_filter_diagnostics`：
      - `pending_without_strong_evidence` 表示该项已在审计中出现，但只形成 pending / 弱证据
      - `not_observed_in_audit` 表示该项在当前审计产物中完全没有出现
      - pending 诊断会尽量带出 `evidence_level / pending_reason / audit_file / channel_id`
    - 当前已支持 `required_filter_status_map`：
      - 按 required filter key 直接给出 `strong / pending / missing`
      - `strong` 表示该 required filter 已形成强站点证据
      - `pending` 表示该 required filter 已出现但强证据不足
      - `missing` 表示该 required filter 在当前审计产物中没有出现
    - 当前已支持 `required_filter_status_counts / required_filter_next_actions`：
      - `required_filter_status_counts` 汇总 `strong / pending / missing` 数量
      - `required_filter_next_actions` 为每个 required filter 给出下一步排查建议
      - `pending` 项建议检查 pending 审计文件
      - `missing` 项建议重新跑真实爬取并生成审计产物
    - 当前已支持 `gate_failure_reasons`：
      - `required_filters_empty` 表示显式请求门槛但没有解析到 required filters
      - `audit_files_empty` 表示未找到任何审计文件
      - `scoped_audit_files_empty` 表示指定渠道下没有审计文件
      - `missing_strong_evidence` 表示 required filters 缺少强站点证据
    - 当前已支持审计文件新鲜度门槛：
      - CLI 参数：`--max-age-minutes`
      - 超龄审计文件不能贡献 strong / pending gate 证据
      - gate 失败原因会区分：
        - `stale_audit_files_only`
        - `scoped_audit_files_stale`
      - 报告会透出：
        - `freshness_check`
        - `fresh_audit_file_count`
        - `stale_audit_file_count`
        - `stale_audit_files`
        - `scoped_stale_audit_file_count`
    - 当前已支持精简待办报告：
      - CLI 参数：`--todo-report`
      - 只能与 `--required-filter` 或 `--require-configured-channel` 搭配
      - 输出 `runtime_audit_gate_todos`
      - 保留 `closure_blockers` 与 `required_filter_gap_todos`
      - 配合 `--strict-exit` 时不能绕过失败退出码
    - 当前已支持按真实运行批次限定 gate 证据：
      - CLI 参数：`--require-audit-run-id <audit_run_id>`
      - 只有匹配该 `audit_run_id` 的审计文件能贡献 strong / pending gate 证据
      - 非匹配批次只保留为诊断字段：
        - `matched_audit_run_file_count`
        - `matched_stale_audit_run_file_count`
        - `unmatched_audit_run_file_count`
        - `unmatched_audit_run_files`
      - gate 失败原因会区分：
        - `audit_run_id_not_found`
        - `scoped_audit_run_id_not_found`
        - `audit_run_files_stale`
        - `scoped_audit_run_files_stale`
    - 当前已支持自动选择最新运行批次：
      - CLI 参数：`--latest-audit-run`
      - 自动使用扫描结果中最新的 `audit_run_id` 作为 gate 范围
      - 当与 `--require-configured-channel <channel_id>` 搭配时，只在该渠道自己的审计文件中选择最新 `audit_run_id`
      - 与 `--require-audit-run-id` 互斥
      - 如果审计文件存在但都缺少 `audit_run_id`，gate 会失败为 `latest_audit_run_id_missing`
      - 报告会透出：
        - `latest_audit_run_only`
        - `latest_audit_run_channel_id`
        - `latest_audit_run_id`
        - `latest_audit_file`
        - `latest_audit_generated_at_epoch`
    - `--require-configured-channel` 的配置读取路径已增加契约保护：
      - 会按指定 `channel_id` 读取当前渠道已启用的筛选项
      - 不允许不同 1688 渠道之间串值
      - 即使当前渠道没有启用任何筛选项，也会输出门槛报告
      - 空 required filters 时 `passed = false`，不能被误判为完成
      - 当前门槛报告已支持 `required_channel_id` 作用域：
        - 指定渠道验收时，只统计该渠道审计文件里的强证据
        - 不允许用其他渠道的同名筛选项强证据关闭当前渠道缺口
        - 缺少指定渠道审计文件时 `scoped_audit_file_count = 0` 且 `passed = false`
- 最终 gate 结论：
  - 2026-07-02 已使用真实审计目录 `scratch/channel_filter_real_audit_manual_20260702_full_closure` 关闭缺口。
  - `selected_distributors / single_piece_drop_shipping / single_piece_free_shipping / free_shipping / encrypted_waybill` 均已有强证据。
  - 最终快照 `pending_filter_count = 0`。
  - 早期 `passed = false / audit_file_count = 0` 记录仅作为历史失败样本保留，不再代表当前计划状态。
- 已完成：
  - `single_piece_free_shipping` 真实语义按组合依赖强证据收口。
  - `encrypted_waybill` 真实页面已选条件条路径已收口。
  - 当前 required filter 门槛不再缺 `single_piece_free_shipping / encrypted_waybill`。
  - 最终真实审计产物已落在 `scratch/channel_filter_real_audit_manual_20260702_full_closure`。

最终检查点：

1. `single_piece_free_shipping` 的组合依赖强证据已同步到顶层契约与前端解释。
2. `encrypted_waybill` 的已选条件条证据已同步到顶层契约与前端解释。
3. 浏览器级真实回归已通过 2026-07-02 真实站点审计样本闭环；后续若 1688 页面结构变化，应作为新回归任务处理。

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

分解步骤：

1. 页面来源确认
   - 确认每一项来自：
     - 标准搜索页稳定筛选区
     - 或图搜结果页稳定筛选区
   - 不把临时浮层、异步插槽、一次性运营位误判为长期筛选项
2. selector 策略分层
   - 图搜结果页：
     - 优先 `bottomFilterOption` 等稳定容器
   - 标准搜索页：
     - 优先 `.search-filt-item / .sn-row / .sn-select-wrap` 等稳定容器
3. 动作与结果双验证
   - 不只看点击成功
   - 还要看：
     - 选中态
     - 结果签名变化
     - 必要时的 URL / query 旁证
4. 失败口径统一
   - `ui_selector_not_stable`
   - `ui_apply_not_observed`
   - 不允许继续使用模糊失败描述

当前进展：

- 已补齐 `verification_entry = search_result_checkbox`
- 已补齐 `mapping_hint`
- 已在 `run_ali1688_slow_flow.py` 中加入基于结果页 HTML 文本的 probe 命中记录
- 当前在图搜结果页场景下，系统已能诚实降级为：
  - `status = unapplied`
  - `reason = ui_selector_not_stable`
- 但对于“图搜结果页中已直接可见”的 checkbox 项，当前已不再只停留在文案探测：
  - 会尝试点击底部筛选容器
  - 若观察到选中态，则升级为 `applied / ui_automation`
  - 若动作已执行但未观察到选中态，则升级为 `ui_apply_not_observed`
- 已新增多 `ali1688` 渠道并存场景的静态隔离校验：
  - `validate_channel_search_filters_per_channel_isolation()`
  - 当前已锁住：
    - `get_channel_search_filters(...)` 按 `channel_id` 正确回读
    - `get_channel_search_filter_snapshot(...)` 按 `channel_id` 正确生成快照
    - A 渠道不会串入 B 渠道的启用项
    - B 渠道不会串入 A 渠道的启用项
- 已新增“省略 `channel_id` 时默认按活动渠道回读”的静态校验：
  - `validate_channel_search_filters_follow_active_channel_selection()`
  - 当前已锁住：
    - `get_channel_search_filters(...)` 在未显式传入 `channel_id` 时，会回读 `active_channel_id`
    - `get_channel_search_filter_snapshot(...)` 在未显式传入 `channel_id` 时，会绑定当前活动渠道
    - 不会误串入非活动渠道的启用项
- 已新增“不支持搜索筛选能力的渠道必须保持空快照”的静态校验：
  - `validate_channel_search_filters_unsupported_channel_stays_empty()`
  - 当前已锁住：
    - 非 `ali1688` 渠道回读结果必须保持 `filters = {}`
    - `supported_filter_keys` / `configured_enabled_filter_keys` / `filter_status_map` / `verification_details` 不会被伪造
- 已新增“标准搜索页可见筛选项动作链路”的浏览器级 fixture 校验：
  - `validate_visible_filter_toggle_runtime_apply_for_standard_search_layout()`
  - `validate_visible_filter_toggle_runtime_apply_for_standard_search_checkbox_group()`
  - `validate_visible_filter_toggle_runtime_apply_for_standard_select_item()`
  - `validate_visible_filter_toggle_runtime_apply_for_standard_col_item()`
  - `validate_standard_layout_selector_priority_over_text_fallback()`
  - `validate_image_layout_selector_priority_over_text_fallback()`
  - 当前已锁住：
    - `standard_search_filter_bar` 布局能被稳定识别
    - `standard_search_filter_item` 会被优先作为点击入口
    - 标准搜索页动作成功后会写入真实选中态与结果签名变化
    - `selected_distributors / seven_day_return / real_factory_verified / strength_verified`
      已在标准搜索页 fixture 中验证可完成：
      - 布局识别
      - 入口定位
      - 点击动作
      - 选中态确认
      - 结果签名变化
    - 标准搜索页的 selector 变体也已覆盖：
      - `standard_search_filter_item`
      - `standard_select_item`
      - `standard_col_item`
    - 当稳定容器存在时，图搜 / 标准搜索页都不会优先退化到 `text_fallback`
    - 运行时快照现在还会补齐 selector 诊断字段：
      - `selector_candidates_tried`
      - `selector_resolution_mode`
      - `text_fallback_considered`
    - 特殊入口路径现在还会补齐触发器诊断字段：
      - `panel_trigger_candidates`
      - `panel_visible_via`
- 已补齐 API 与前端解释层对 runtime selector 诊断字段的契约保护：
  - `selector_candidates_tried`
  - `selector_resolution_mode`
  - `text_fallback_considered`
  - `panel_trigger_candidates`
  - `panel_visible_via`
  - `entry_selector_strategy`
  - `page_filter_layout`
  - `result_signature_changed`
- 已完成完整本地契约套件补跑：
  - `scripts/validate_source_channel_config.py`
  - 当前 52 个检查全部通过
- 已完成：
  - `selected_distributors` 已通过真实站点 URL 变化证据闭环。
  - DOM checkbox 型项的配置回读、runtime 渠道隔离、失败口径和前端解释均已有契约保护。
  - 真实页面更复杂结构属于后续站点变化回归，不再作为本计划未完成项。

完成定义：

1. 4 个 DOM checkbox 项都具备稳定的来源判断
2. 至少图搜结果页与标准搜索页中的一套路径有稳定动作链路
3. 失败时都能回落到统一 reason code，而不是只停留在“文案命中”

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

分解步骤：

1. 列表页渠道摘要收口
   - 只展示：
     - `used_channels`
     - 渠道数量 / 渠道名称摘要
   - 不把 11 项逐条细节堆到列表页
2. 详情页渠道筛选与固定排序分离
   - 渠道筛选控件只影响展示范围
   - 固定排序文案只表达“当前系统固定排序策略”
   - 不再用同一个控件承担两种语义
3. 渠道组头部解释增强
   - 每个渠道组都能解释：
     - 启用了哪些筛选项
     - 哪些已生效
     - 哪些未应用
     - 哪些仅属已配置未验证
4. 详情接口契约稳定化
   - 字段至少稳定包含：
     - `used_channels`
     - `channel_groups`
     - `estimated_profit`
     - `best_estimated_profit`
     - `source_sort_strategy`
     - `channel_group_sort_strategy`

当前进展：

- 已在列表页轻量展示 `used_channels`
- 已在详情页按渠道分组展示 `channel_groups`
- 已补齐历史无快照数据的降级提示
- 已把“按货源渠道筛选”和“固定排序说明”拆开
- 已把“固定按预估纯利倒序”从前端文案推进到详情接口契约：
  - `/api/task_details/{task_id}` 当前会直接返回：
    - 渠道内 `sources` 按预估纯利倒序
    - `channel_groups` 按各渠道最佳预估纯利倒序
    - `used_channels` 顺序与渠道组保持一致
    - 单条货源直接透出 `estimated_profit`
    - 排序策略说明直接透出 `source_sort_strategy / channel_group_sort_strategy`
  - 前端若拿到 `best_estimated_profit`，会优先复用后端排序权重
  - 前端若拿到 `estimated_profit`，会优先复用后端利润值
  - 详情页固定排序标签与说明文案优先消费接口契约，不再在 JSX 内硬编码规则
- 已新增后端静态排序契约校验：
  - `validate_detail_channel_sorting_contract()`
  - 当前已锁住：
    - 全量 `sources` 固定按 `estimated_profit` 倒序
    - `channel_groups` 固定按 `best_estimated_profit` 倒序
    - `used_channels` 顺序与 `channel_groups` 保持一致
    - 每个 `channel_groups[*].sources` 内部也固定按预估纯利倒序
- 已将详情页渠道筛选摘要状态口径收紧为计划要求的 5 类：
  - `已配置未验证`
  - `已注入待验证`
  - `已生效`
  - `未应用`
  - `当前渠道不支持`
- 已将“历史无快照资产”的降级口径下沉到详情接口：
  - `channel_groups[*].filter_summary.legacy_missing_snapshot`
  - `sources[*].source_filter_summary.legacy_missing_snapshot`
  - 当前前端已优先消费接口侧 `filter_summary`，不再只依赖 JSX 现场推断
- 已将统一筛选摘要上提到任务列表聚合层：
  - `/api/tasks` 当前会直接返回 `channel_summaries`
  - `channel_summaries[*]` 已补齐：
    - `filter_summary`
    - `has_recorded_filter_snapshot`
  - 当前结果列表与历史任务列表已优先消费 `channel_summaries`，不再只依赖 `used_channels`
  - 已新增任务级静态契约校验：
    - `validate_task_channel_summary_contract()`
  - 当前已锁住：
    - `channel_summaries` 顺序与 `used_channels` 保持一致
    - 真实快照会稳定回填到任务级 `filter_summary`
    - 历史无快照渠道会继续保留 `legacy_missing_snapshot`
    - `has_recorded_filter_snapshot` 不会把历史缺失快照误判为已记录
- 已将渠道筛选摘要基础字段下沉到详情接口：
  - `configured_pending`
  - `query_injected`
  - `applied`
  - `unapplied`
  - `unsupported`
  - `configured_filter_count`
  - `mapping_stage`
  - `mapping_notes`
- 已继续把详情解释所需的 runtime 明细字段下沉到统一摘要契约：
  - `filter_status_map`
  - `query_verification_details`
  - 当前 `filter_summary` 已可直接承载：
    - 每项的 status / reason / mapping_stage
    - query 命中参数与动作级 verification detail
  - 前端已新增统一归一化层，优先消费接口侧 `filter_summary`
  - 仅在历史数据或回退场景下，才继续从 `source_filter_snapshot` 做兜底推断
- 当前 `web/app.jsx` 中的摘要分层规则已明确区分：
  - 仅配置态 / 语义待确认 / 特殊入口未映射
    - 归入 `已配置未验证`
  - 已尝试真实动作但未成功
    - 归入 `未应用`
  - 非 `ali1688` 渠道
    - 归入 `当前渠道不支持`
- 已为 `已配置未验证` 新增明细解释区：
  - `配置态线索`
  - 当前会直接透出：
    - 依赖项是否齐备
    - 页面文案是否命中
    - 当前 reason code 的解释
    - 验证入口与映射提示
- 已能展示批次 5 / 6 的中间态解释，包括：
  - `snapshot_only_until_semantics_confirmed`
  - `special_panel_entry_detected_unmapped`
  - `ui_selector_not_stable`
- 已把新接入的 runtime 动作证据展示到详情解释层，包括：
  - `dom_toggle_action`
  - `dom_panel_action`
  - 页面布局
  - 点击入口策略
  - 动作前后可见性与选中态
- 已把 `sources[*].source_filter_summary` 接入单条货源卡片展示：
  - 每个 source 卡片现在都会直接展示：
    - `已配置未验证`
    - `已注入待验证`
    - `已生效`
    - `未应用`
    - `历史快照缺失 / 当前渠道不支持`
  - 这样详情页不再只有 `channel_groups[*].filter_summary` 能解释筛选结果，单条货源也能直接消费接口契约
- 已新增静态契约校验继续锁住 API-first 目标：
  - `validate_detail_channel_filter_summary_contract()`
    - 当前已要求 `filter_summary` 自带 `filter_status_map / query_verification_details`
  - `validate_detail_source_filter_summary_contract()`
    - 当前已要求 `source_filter_summary` 保留：
      - 已启用全集
      - `applied / query_injected / unapplied`
      - `configured_filter_count`
  - `validate_task_channel_summary_contract()`
    - 当前也已要求任务列表聚合层保留同一套解释字段
- 已完成：
  - 已使用真实入库任务 `cf20260702` 完成页面级验收。
  - 决策资产列表、任务报告页、商品详情页均已展示真实渠道与筛选解释。
  - 渠道筛选与固定排序策略已经解耦，排序固定为 `预估纯利倒序`。

完成定义：

1. 用户能一眼看出“本次用了哪些渠道”
2. 用户能在详情页解释“每个渠道用了哪些筛选策略、哪些成功、哪些失败”
3. 页面不再把“渠道筛选”和“排序策略”混成同一个交互语义

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

## 11. 后续推进边界

本计划已闭环，后续不再按批次 5 / 6 / 7 继续追加实现。若继续做渠道筛选相关新需求，应另起计划并明确是否属于以下方向：

1. 1688 商品列表页新增字段采集、入库与展示
2. 新的顶部筛选项或 1688 页面结构变更回归
3. 非 1688 渠道的筛选能力建模
4. 渠道筛选在任务调度策略中的权重或优先级

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
