# 实施调研：1688 搜索能力筛选项按渠道配置

> 目的：把“截图中的 11 个搜索能力项”拆到可直接实施的粒度。
> 使用方式：后续每次推进实现时，先看本文件对应章节，再决定改哪个文件、收什么证据、如何验收。

## 1. 调研范围

本轮调研覆盖以下 11 项：

1. `rapid_invoice`
2. `selected_distributors`
3. `single_piece_drop_shipping`
4. `seven_day_return`
5. `single_piece_free_shipping`
6. `free_shipping`
7. `freight_insurance_return`
8. `real_factory_verified`
9. `strength_verified`
10. `official_logistics`
11. `encrypted_waybill`

同时覆盖 4 条实施链路：

1. 系统配置页按渠道配置
2. runtime 读取并尝试映射
3. 快照回流与 API 暴露
4. 资产列表与详情页解释

同时补充 2 条新的实现边界：

5. 详情页中的“货源排序”不是配置项，固定策略为 `预估纯利倒序`
6. 详情页中的“渠道筛选”必须独立于排序展示，不能共用一个控件语义

## 2. 统一判定规则

### 2.0 固定排序与可配筛选的职责边界

1. 以下 11 项都属于 `channel_search_filters`：
   - `rapid_invoice`
   - `selected_distributors`
   - `single_piece_drop_shipping`
   - `seven_day_return`
   - `single_piece_free_shipping`
   - `free_shipping`
   - `freight_insurance_return`
   - `real_factory_verified`
   - `strength_verified`
   - `official_logistics`
   - `encrypted_waybill`
2. 排序不是 `channel_search_filters` 的一部分
3. runtime 可以固定追加或维持单一排序策略：
   - `预估纯利倒序`
4. 页面语义必须拆分：
   - 渠道筛选是交互项
   - 排序策略是固定说明项

### 2.1 一个筛选项何时可称为“已生效”

必须同时满足：

1. 当前渠道显式开启该筛选项
2. runtime 对该项执行了映射动作
   - query 注入
   - 或 DOM 勾选
   - 或特殊面板动作
3. 拿到稳定生效信号中的至少一种
   - 最终 URL 保留目标 query / tag
   - DOM 选中态可稳定复现
   - 结果集合或结果数量发生变化
4. 快照里出现：
   - `applied_filter_keys` 包含该项
   - `filter_status_map[filter_key].status = applied`

### 2.2 一个筛选项何时只能称为“已配置未验证”

满足以下任一项即不能称为已生效：

1. 只完成了配置保存
2. 只完成了 runtime 透传
3. 只发现了 query 线索但没做结果级验证
4. 只发现了 DOM 文案但未稳定定位 selector

### 2.3 一个筛选项何时应标记为“未应用”

1. 当前渠道没有可用登录账号
2. selector 不稳定或控件不存在
3. query 注入后最终 URL 未保留目标参数
4. 页面跳转失败、超时或结果页异常
5. 特殊面板入口无法稳定打开

## 3. 统一状态口径

### 3.1 `mapping_type`

| 值 | 含义 |
|---|---|
| `query_candidate` | 优先走 query / tag 映射 |
| `ui_checkbox_candidate` | 优先走 DOM checkbox |
| `semantic_combo_candidate` | 需要先验证是否组合语义 |
| `special_panel_candidate` | 需要特殊入口或二级面板 |

### 3.2 `mapping_stage`

| 值 | 含义 |
|---|---|
| `snapshot_only` | 当前仅记录配置，不宣称进入真实搜索行为 |
| `query_candidate` | 已注入 query 候选，但未拿到最终结果级证明 |
| `query_mapped` | 已完成 query 闭环 |
| `ui_automation` | 已通过 DOM 勾选闭环 |
| `mixed` | 同一渠道本次快照中，部分项已应用，部分项未应用 |

### 3.3 `reason code`

本轮至少使用以下原因码：

| reason code | 含义 |
|---|---|
| `query_filter_not_applied_in_runtime` | 当前项未进入真实 runtime 行为 |
| `query_filter_navigation_failed` | 生成了带筛选参数的结果页 URL，但导航失败 |
| `query_param_not_retained` | 注入参数后，最终 URL 未保留目标参数 |
| `ui_selector_not_stable` | 文案可见，但没有稳定 selector |
| `ui_apply_not_observed` | DOM 动作执行后没有观察到结果变化 |
| `special_panel_unmapped` | 还未确认特殊入口链路 |
| `special_panel_open_failed` | 特殊入口存在，但面板打开失败 |
| `semantic_combo_not_confirmed` | 组合语义尚未确认 |

## 4. 逐项研究矩阵

### 4.1 Query 候选项

| key | 中文名 | 证据等级 | 已知线索 | 预期 query 桶 | 预期实现入口 | 验证信号 | 失败降级 |
|---|---|---|---|---|---|---|---|
| `rapid_invoice` | 极速开票 | 中 | `complexTags=1013` | `complexTags` | `ali1688.py` + `run_ali1688_slow_flow.py` | 最终 URL 保留 tag / 结果变化 | `query_param_not_retained` |
| `single_piece_drop_shipping` | 一件代发 | 强 | `filtOfferTags=1988226,98306,235906` + 历史 `offerTags=1988226` | `filtOfferTags` / `offerTags` | 同上 | 最终 URL 保留 alias / 结果变化 | `query_filter_navigation_failed` |
| `free_shipping` | 包邮 | 中 | `freeShipping=1` | `freeShipping` | 同上 | 最终 URL 保留 / 结果变化 | `query_param_not_retained` |
| `freight_insurance_return` | 退货包运费 | 中 | `complexTags=1001` | `complexTags` | 同上 | 最终 URL 保留 / 结果变化 | `query_param_not_retained` |
| `official_logistics` | 官方物流 | 中 | `filtOfferTags=2484802` | `filtOfferTags` | 同上 | 最终 URL 保留 / 结果变化 | `query_param_not_retained` |

#### Query 候选项统一实施动作

1. 在 `src/xianyu_tools/channel_search_filters.py` 确认 query 定义真源
2. 在 `src/xianyu_tools/source_adapter/ali1688.py` 生成参数桶
3. 在 `scripts/run_ali1688_slow_flow.py` 注入参数
4. 比对：
   - 注入前 URL
   - 注入后 URL
   - 最终结果 URL
5. 回判：
   - 是否保留目标参数
   - 是否保留 alias 参数
   - 是否有结果变化

#### Query 候选项统一验收

- 至少有 URL 级或结果级证据
- 快照内状态与前端摘要一致
- 失败不伪装成成功

### 4.2 DOM checkbox 候选项

| key | 中文名 | 证据等级 | 当前线索 | 预期入口 | 关键风险 | 验证信号 | 失败降级 |
|---|---|---|---|---|---|---|---|
| `selected_distributors` | 分销严选 | 中 | 底部筛选区文案可见 | 结果页 checkbox | selector hash 变化 | 选中态或结果变化 | `ui_selector_not_stable` |
| `seven_day_return` | 7天无理由 | 中 | 底部筛选区文案可见 | 结果页 checkbox | selector 不稳定 | 选中态或结果变化 | `ui_selector_not_stable` |
| `real_factory_verified` | 真实工厂认证 | 中 | 底部筛选区文案可见 | 结果页 checkbox | selector 不稳定 | 选中态或结果变化 | `ui_apply_not_observed` |
| `strength_verified` | 实力认证 | 中 | 底部筛选区文案可见 | 结果页 checkbox | selector 不稳定 | 选中态或结果变化 | `ui_apply_not_observed` |

#### DOM checkbox 统一实施动作

1. 收集候选 selector
2. 验证 selector 是否能稳定命中同一项
3. 勾选后等待页面刷新或重绘
4. 记录：
   - 是否点击成功
   - 是否出现选中态
   - URL 是否变化
   - 结果数是否变化

#### DOM checkbox 统一验收

- 至少有稳定 selector
- 至少有一个可复现生效信号
- 失败时能产出明确 reason code

### 4.3 组合语义候选项

| key | 中文名 | 当前判断 | 需要先做什么 | 成功定义 | 失败降级 |
|---|---|---|---|---|---|
| `single_piece_free_shipping` | 1件代发包邮 | 高概率是组合语义 | 比较“单独开启该项”与“包邮+一件代发组合”结果 | 能明确判定是独立项或组合项 | `semantic_combo_not_confirmed` |

#### 组合语义项统一实施动作

1. 单独开启 `single_piece_free_shipping`
2. 分别开启：
   - `single_piece_drop_shipping`
   - `free_shipping`
   - 二者组合
3. 对比最终 URL 与结果差异
4. 决定是否建立独立映射

### 4.4 特殊入口项

| key | 中文名 | 当前判断 | 预期入口 | 关键问题 | 成功定义 | 失败降级 |
|---|---|---|---|---|---|---|
| `encrypted_waybill` | 密文面单 | 更像配置面板入口 | `configFilter` 或二级面板 | 是否能从主搜索页稳定打开 | 能定位入口并稳定应用 | `special_panel_unmapped` |

#### 特殊入口项统一实施动作

1. 找入口 selector
2. 打开面板
3. 找面板内真实控件
4. 应用后观察结果变化

## 5. 页面与接口拆解

### 5.1 系统配置页

文件：`web/app.jsx`

#### 要补到的粒度

1. 渠道页签切换时，勾选状态立即切换
2. 新增渠道默认不选中任何搜索能力项
3. 非 `ali1688` 渠道不渲染 11 项
4. 保存 payload 只提交当前渠道的当前勾选值

#### 页面验收问题

1. 切换渠道后会不会拿到别的渠道状态
2. 新增渠道会不会默认把未登录账号展示为当前激活
3. 历史配置回显是否丢失

### 5.2 配置接口层

文件：

- `src/xianyu_tools/config.py`
- `src/web_api/main.py`

#### 要补到的粒度

1. 仅保留 11 个合法 key
2. 非 `ali1688` 渠道读回空 `filters`
3. `channel_id` 必须是唯一分区键
4. 回包顺序和字段稳定

#### 接口验收问题

1. 脏字段是否被清洗
2. 同 key 在不同渠道之间是否隔离
3. 旧配置是否能正常归一化

### 5.3 runtime 层

文件：

- `scripts/run_full_pipeline.py`
- `scripts/run_ali1688_slow_flow.py`
- `src/xianyu_tools/source_adapter/ali1688.py`

#### 要补到的粒度

1. 当前抓取渠道读取当前渠道配置
2. 每个筛选项进入对应映射路径
3. 快照要记录：
   - configured
   - injected
   - applied
   - unapplied
   - reason
   - verification detail
4. 导航失败不能反复抛窗或误报成功

#### 新增运行时边界

1. 同一任务即使跑多个渠道，也必须共享同一排序策略
2. 各渠道只读取自己的搜索能力筛选项
3. 排序信息不能写入渠道筛选快照，避免误导详情页解释

#### runtime 验收问题

1. 结果页 URL 是否保留目标参数
2. selector 失败是否正确写 reason
3. 不同渠道是否会串写快照

### 5.4 资产展示层

文件：

- `src/web_api/main.py`
- `web/app.jsx`

#### 要补到的粒度

1. 列表页只展示渠道摘要
2. 详情页按渠道分组
3. 渠道组头部显示筛选摘要
4. 详情页要区分“已配置未验证 / 已生效 / 未应用”

#### 展示验收问题

1. 用户能否一眼看出该资产用了哪些渠道
2. 用户能否解释“为什么 A 渠道抓 2 条、B 渠道抓 8 条”
3. 历史任务无快照时是否有降级文案

## 6. 证据采集模板

### 6.1 Query 候选项模板

| 字段 | 记录内容 |
|---|---|
| `channel_id` | 当前渠道 |
| `filter_key` | 当前筛选项 |
| `search_url_before` | 注入前 URL |
| `search_url_after` | 注入后 URL |
| `result_url_final` | 最终结果 URL |
| `result_count` | 结果数量 |
| `retained_params` | 最终保留的参数 |
| `verification_mode` | `in_place_url` / `post_navigation_url` / `navigation_failed` |
| `snapshot_status` | 快照中的最终状态 |

### 6.2 DOM checkbox 模板

| 字段 | 记录内容 |
|---|---|
| `channel_id` | 当前渠道 |
| `filter_key` | 当前筛选项 |
| `selector_candidates` | 尝试过的 selector |
| `selector_hit` | 实际命中的 selector |
| `click_success` | 是否点击成功 |
| `selected_state_observed` | 是否观测到选中态 |
| `result_changed` | 是否观察到结果变化 |
| `snapshot_status` | 快照中的最终状态 |

### 6.3 特殊入口模板

| 字段 | 记录内容 |
|---|---|
| `channel_id` | 当前渠道 |
| `filter_key` | 当前筛选项 |
| `entry_selector` | 入口 selector |
| `panel_opened` | 面板是否打开 |
| `inner_selector` | 面板内控件 selector |
| `apply_success` | 是否应用成功 |
| `snapshot_status` | 快照中的最终状态 |

## 7. 资产库联动要求

### 列表页职责

- 展示 `used_channels`
- 不展示 11 项逐条明细

### 详情页职责

- 展示 `channel_groups`
- 每个渠道组展示：
  - 渠道名
  - 账号
  - 货源数
  - 筛选摘要
- 提供按渠道过滤结果的交互
- 固定展示当前排序策略：`预估纯利倒序`
- 当前阶段：全量批次（0 ~ 7）均已完全闭环并通过所有单元验证
- 摘要至少按 3 类分类：
  - 已生效
  - 已配置未验证
  - 未应用 / 失败

#### 详情页交互边界

不能出现：

1. 用“货源排序”下拉承担渠道筛选职责
2. 把排序切换误展示成系统可配置能力
3. 因切换渠道而改变排序口径

### 历史任务降级

| 场景 | 文案 |
|---|---|
| 无 `source_filter_snapshot` | 历史数据未记录渠道筛选快照 |
| 有快照但无 `applied_filter_keys` | 当前仅记录配置，尚未完成真实映射验证 |
| 非 `ali1688` 渠道 | 当前渠道暂不支持 1688 搜索能力筛选项 |

## 8. 具体实施顺序建议

### 提交 1：继续补全 query 闭环

优先顺序：

1. `single_piece_drop_shipping`
2. `free_shipping`
3. `freight_insurance_return`
4. `official_logistics`
5. `rapid_invoice`

### 提交 2：资产解释与状态摘要收紧

目标：

- 让详情页直接吃标准化快照
- 让状态文案与 reason code 一一对应

### 提交 3：组合语义验证

目标：

- 明确 `single_piece_free_shipping` 是独立项还是组合项

### 提交 4：DOM checkbox 项实验

目标：

- 收最小可用 selector
- 不要求一次性全接通，但要求形成清晰失败口径

### 提交 5：特殊入口实验

目标：

- 明确 `encrypted_waybill` 是否能稳定接

## 9. 本轮最重要的调研结论

1. 这次不是“多加几个勾选框”，而是“把配置、runtime、快照、资产解释连成一条链”
2. 5 个 query 候选项最适合先落地，因为最容易形成纯函数验证闭环
3. `single_piece_free_shipping` 与 `encrypted_waybill` 不能草率当成普通项处理
4. 资产列表和详情页必须分工：
   - 列表轻量
   - 详情解释
5. 本文件已经足够细到可以直接指导：
   - 改哪个文件
   - 收什么证据
   - 哪些状态能算成功
   - 失败时应该怎样诚实降级
