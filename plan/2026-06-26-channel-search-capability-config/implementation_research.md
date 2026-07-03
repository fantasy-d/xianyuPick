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

## 1.1 本轮新增调研焦点：顶部筛选项如何按渠道落到真实链路

本轮不再只停留在“11 个 key 已存在”，而是把每个顶部筛选项继续拆到下面 6 个问题：

1. 该项是不是渠道级配置，而不是账号级配置
2. 该项在当前代码中属于哪一类映射：
   - `query_candidate`
   - `ui_checkbox_candidate`
   - `semantic_combo_candidate`
   - `special_panel_candidate`
3. 该项真实依赖哪类页面位置：
   - 标准搜索页顶部筛选条
   - 图搜结果页底部筛选区
   - 高级筛选 / 配置面板
4. 该项在多渠道并存任务中，是否需要在决策资产库详情页可见地解释
5. 该项失败时应落哪种 reason code，避免误报“已生效”
6. 该项后续需要哪种验证：
   - 纯静态契约
   - fixture 页面验证
   - 真实 1688 页面动作回归

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
5. 详情接口也应返回固定排序后的数据，而不是只依赖前端二次排序：
   - 渠道内 `sources` 按预估纯利倒序
   - `channel_groups` 按各渠道最佳预估纯利倒序
   - `used_channels` 顺序与渠道组一致
6. 详情接口应直接暴露排序依赖值，而不是只暴露原始成本：
   - `sources[*].estimated_profit`
   - `channel_groups[*].best_estimated_profit`
7. 详情接口应显式暴露排序规则说明，避免前端硬编码：
   - `source_sort_strategy`
   - `channel_group_sort_strategy`

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
| `special_panel_entry_detected_unmapped` | 结果页已观察到特殊入口线索，但二级面板动作链路仍未打通 |
| `special_panel_open_failed` | 特殊入口存在，但面板打开失败 |
| `semantic_combo_not_confirmed` | 组合语义尚未确认 |

## 4. 逐项研究矩阵

### 4.0 当前 11 项的“真源字段 -> 页面入口 -> 渠道解释”总表

| key | 当前定义真源 | 主要入口层 | 当前资产解释层必须展示什么 |
|---|---|---|---|
| `rapid_invoice` | `channel_search_filters` + `ALI1688_CHANNEL_SEARCH_FILTER_DEFINITIONS` | query / tag | 是否已注入、是否保留目标值、是否已进入 `applied` |
| `selected_distributors` | 同上 | 结果页 checkbox | 是否找到稳定 selector、是否观察到选中态、是否结果变化 |
| `single_piece_drop_shipping` | 同上 | query / alias tag | 是否命中 `filtOfferTags / offerTags`、是否结果变化 |
| `seven_day_return` | 同上 | 结果页 checkbox | 是否找到稳定 selector、是否应用成功 |
| `single_piece_free_shipping` | 同上 | 组合语义或独立入口 | 当前语义结论 `semantic_conclusion` |
| `free_shipping` | 同上 | query | 是否命中 `freeShipping=1`、是否结果变化 |
| `freight_insurance_return` | 同上 | query | 是否命中 `complexTags=1001`、是否结果变化 |
| `real_factory_verified` | 同上 | 结果页 checkbox | 是否找到稳定 selector、是否应用成功 |
| `strength_verified` | 同上 | 结果页 checkbox | 是否找到稳定 selector、是否应用成功 |
| `official_logistics` | 同上 | query / alias tag | 是否命中 `filtOfferTags=2484802`、是否结果变化 |
| `encrypted_waybill` | 同上 | 配置筛选面板 / 二级入口 | 当前入口线索、面板动作状态、`special_panel_conclusion` |

这张表的作用不是重复 key 清单，而是给后续实现一个强约束：

1. 顶部筛选项的定义真源只能有一套
2. 决策资产库详情页要按“当前渠道 + 当前项当前证据”解释
3. 不能让前端自己猜某个项是 query 还是 checkbox

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

#### DOM checkbox 候选项的“渠道隔离”额外要求

这些项除了要验证动作本身，还必须额外验证：

1. 渠道 A 开启、渠道 B 关闭时
   - runtime 只允许在渠道 A 的抓取上下文中尝试该 checkbox 动作
2. 渠道 A 未登录、渠道 B 已登录时
   - 不能因为渠道 B 有可用账号，就替渠道 A 执行 DOM 勾选
3. 详情页展示时
   - 渠道 A 的 `未应用 / 已配置未验证` 不能投射到渠道 B
4. 若同一任务中多个渠道都尝试了 checkbox 类项
   - 必须能按 `channel_group` 分别解释成功与失败，不允许只显示一个全局摘要

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

#### 2026-06-27 新增页面证据

- 在图搜结果页 dump 中，已经观察到 `1件代发包邮` 作为独立 `bottomFilterOption` 出现：
  - 与 `一件代发`
  - 与 `包邮`
  - 同级并列展示
- 这说明它在图搜结果页里并不只是“组合语义的文案回显”，而是至少具备：
  - 独立 UI 入口
  - 独立点击目标
- 但这条证据还不能直接推出“业务语义必然独立”，因为仍缺：
  - 点击该项后的真实结果变化
  - 与“只开一件代发 / 只开包邮 / 二者组合”的结果对照

#### 当前结论收紧

- 旧结论：
  - `single_piece_free_shipping` 高概率是组合语义
- 当前更准确的结论：
  - 在图搜结果页中，`single_piece_free_shipping` 已确认存在独立 UI 入口

#### 2026-06-27 新增实现约束：统一语义结论字段

- 对 `single_piece_free_shipping` 这类 `semantic_combo_candidate`，仅保留以下原始证据还不够：
  - `semantic_verification_stage`
  - `independent_ui_entry_observed`
  - `result_signature_changed`
- 原因：
  - 前端会被迫用多组布尔位和阶段值临时拼结论
  - API / 快照 / UI 很容易出现同一事实、不同解释口径
- 因此归一化层应统一沉淀：
  - `semantic_conclusion`

#### 当前 `semantic_conclusion` 口径

| semantic_conclusion | 含义 | 证据来源 |
|---|---|---|
| `dependency_pair_incomplete` | 依赖组合未齐，暂不能判断独立语义 | 结果页文案命中，但依赖项未同时启用 |
| `dependency_pair_ready_pending_runtime` | 依赖组合已齐备，待真实动作验证 | 结果页文案命中，且依赖项都已开启 |
| `independent_entry_observed_pending_result_validation` | 已观察到独立入口，但还缺结果侧变化 | 独立入口存在，但还没拿到结果变化结论 |
| `independent_entry_no_result_shift` | 独立入口可点击，但暂未观察到结果变化 | 已执行真实动作，但结果签名未变化 |
| `independent_entry_result_shift_observed` | 独立入口动作后已观察到结果变化 | 已执行真实动作，且结果签名变化 |

#### 对前端与 API 的影响

1. `filter_status_map[filter_key].semantic_conclusion`
   - 必须可直接消费
2. `verification_details[filter_key].semantic_conclusion`
   - 必须同步投影
3. `query_verification_details[filter_key].semantic_conclusion`
   - 也必须同步投影，避免旧消费层看不到统一结论

#### 组合语义项的渠道化展示要求

`single_piece_free_shipping` 对详情页的影响比普通项更大，因为它天然容易让用户误会：

1. 渠道 A 如果只配置了 `single_piece_free_shipping`
   - 详情页不能直接说“已等价于 一件代发 + 包邮”
2. 渠道 A 如果显式配置了：
   - `single_piece_drop_shipping = true`
   - `free_shipping = true`
   - `single_piece_free_shipping = true`
   - 才允许解释为“依赖组合已齐备，待真实动作验证”
3. 渠道 B 如果只配置了 `single_piece_drop_shipping`
   - 不能被详情页误解释成也参与了 `single_piece_free_shipping`
4. 因此该项必须在详情页中展示：
   - 当前渠道配置态
   - 依赖组合是否齐备
   - 当前统一结论

### 4.4 特殊入口候选项的渠道化要求

`encrypted_waybill` 当前属于最需要避免“误报成功”的项，因此这里锁定 4 个边界：

1. 只要当前渠道没有真实面板动作证据
   - 就不能把它提升为 `applied`
2. 只要当前渠道只命中了结果页文本
   - 也只能停留在：
     - `entry_signal_detected_pending_panel_mapping`
     - 或更细的 `special_panel_conclusion`
3. 渠道 A 命中入口线索、渠道 B 未命中时
   - 详情页必须能区分这两个渠道，而不是给出一个全局“密文面单待补验证”
4. 若后续引入真实面板 fixture
   - 必须把结果继续沉到 `channel_group.filter_summary`，保证决策资产库详情页不用重新推断

## 5. 按文件的实施调研补充

### 5.1 `src/xianyu_tools/channel_search_filters.py`

本文件现在已经承担“11 项定义真源”，后续只能继续增强，不能拆出第二套平行字典。

后续推进时要优先检查：

1. 新增或修改某个顶部筛选项时，是否同时补了：
   - `mapping_type`
   - `group`
   - `query_param / query_values`
   - `probe_terms`
   - `verification_entry`
   - `mapping_hint`
2. 该项若属于特殊语义，是否补了：
   - `semantic_dependencies`
   - `observation_scope`
   - `entry_signal_type`
   - `next_required_action`
3. 不允许把“渠道级配置默认值”直接写死在这里
   - 这里定义的是能力项元信息，不是某个渠道当前是否启用

### 5.2 `src/xianyu_tools/config.py`

本文件要继续承担“按渠道保存 / 回读顶部筛选项”的唯一配置层职责。

本轮实施时要额外关注：

1. 新增渠道时
   - 不应自动把新账号或新渠道默认选中进顶部筛选配置
2. 非 `ali1688` 渠道时
   - `filters` 仍应稳定回空
3. 多个 `ali1688` 渠道共存时
   - 回读必须按 `channel_id` 隔离
4. 当前活动渠道切换时
   - 页面回显必须跟随活动渠道，而不是跟随最后一次编辑过的渠道

### 5.3 `scripts/run_ali1688_slow_flow.py`

这是顶部筛选项真正进入搜索行为的关键层，本轮调研收紧为：

1. 先区分当前项属于：
   - query
   - checkbox
   - semantic combo
   - special panel
2. 再决定动作链路，不允许前端或 API 再反向猜测
3. 执行后必须同时保留：
   - 配置态
   - 动作态
   - 结果态
   - 失败态
4. 这些状态必须能按渠道独立回流到资产详情页

### 5.4 `src/web_api/main.py` 与 `web/app.jsx`

这两层后续要共同保证一个结果：

1. 列表页只回答：
   - 本次用了哪些渠道
2. 详情页进一步回答：
   - 每个渠道用了哪些顶部筛选项
   - 哪些已生效
   - 哪些未应用
   - 哪些仍是已配置未验证
3. 排序文案固定说明
   - 不与渠道筛选混成一个控件
4. 同一任务里的不同渠道
   - 不能共享一个全局顶部筛选结论
   - 保持与顶层口径一致，避免前端读不同字段得到不同结论
4. 详情页展示策略
   - 优先展示统一语义结论
   - 再展示原始阶段、依赖项、动作前后结果签名等辅助证据
  - 但其最终业务语义是否独立，仍待真实结果对照验证

### 4.4 特殊入口候选项的统一入口结论

- 对 `encrypted_waybill` 这类 `special_panel_candidate`，仅保留以下原始证据也不够：
  - `reason`
  - `entry_signal_detected`
  - `panel_trigger_clicked`
  - `result_signature_changed`
- 原因：
  - 前端仍需要自己猜“只是看到入口”还是“已经尝试动作但失败”
  - 特殊入口链路比 query / checkbox 更容易出现解释分叉
- 因此归一化层应统一沉淀：
  - `special_panel_conclusion`

#### 当前 `special_panel_conclusion` 口径

| special_panel_conclusion | 含义 | 证据来源 |
|---|---|---|
| `entry_signal_detected_pending_panel_mapping` | 已观察到特殊入口线索，但面板动作链路还未打通 | 结果页文本命中 `密文面单` |
| `panel_open_or_toggle_failed` | 已尝试打开面板或切换筛选，但动作未完成 | `dom_panel_action` 失败场景 |
| `panel_action_applied_no_result_shift` | 面板动作已命中，但结果侧暂未观察到变化 | 已 applied，但结果签名未变化 |
| `panel_action_result_shift_observed` | 面板动作后已观察到结果变化 | 已 applied，且结果签名变化 |

#### 对前端与 API 的影响

1. `filter_status_map[filter_key].special_panel_conclusion`
   - 必须可直接消费
2. `verification_details[filter_key].special_panel_conclusion`
   - 必须同步投影
3. `query_verification_details[filter_key].special_panel_conclusion`
   - 保持与顶层口径一致
4. 详情页展示策略
   - 优先展示统一入口结论
   - 再展示：
     - 面板触发器
     - 动作前后可见性与选中态
     - 结果签名变化

#### 当前实现口径收口

- 当 `single_piece_free_shipping` 在图搜结果页通过独立可点击入口完成动作，且已观察到选中态时：
  - runtime 已明确写入：
    - `status = applied`
    - `mapping_stage = ui_automation`
- 因此快照归一化层也必须保持同一口径：
  - 对于 `semantic_combo_candidate + applied`，不能再把缺省阶段回退成 `mixed`
- `mixed` 只应保留给更高层的“本渠道整体同时包含成功项与失败项”场景，而不应覆盖单项已经完成真实 UI 动作闭环的事实。

#### 新增结果侧旁证

- 当前对 `ui_checkbox_candidate / semantic_combo_candidate / special_panel_candidate`，除了入口与选中态证据外，还会补采样：
  - `result_signature_before_action`
  - `result_signature_after_action`
  - `result_signature_changed`
- 对 `single_piece_free_shipping`，当前又新增了一层更细的语义阶段字段：
  - `dependency_pair_enabled`
  - `dependency_pair_incomplete`
  - `direct_entry_result_shift_observed`
  - `direct_entry_result_shift_not_observed`
- 同时需要注意一个契约层要求：
  - 上述证据不能只存在于 `filter_status_map[filter_key].verification_detail`
  - 还必须同步投影到顶层：
    - `verification_details`
    - `query_verification_details`
  - 否则旧消费层或简化消费层会出现“状态层知道，摘要层看不到”的回退
- 这组字段的职责不是直接替代最终业务判定，而是提供统一的结果侧旁证：
  - 如果动作成功且结果签名也变化，那么“该筛选项确实影响了结果集”的置信度会更高
  - 如果动作成功但结果签名不变，则后续在真实页面上要继续确认：
    - 是否页面只是局部重绘但首屏结果未变
    - 是否该项只是 UI 可勾选，但业务语义并未真正独立生效
- 对 `single_piece_free_shipping` 来说，这一步尤其重要：
  - 它现在已经不只是“有独立 UI 入口”
  - 而是已经具备了“动作前后结果侧变化也可被结构化记录”的能力
  - 后续真正缺的只剩真实 1688 页面上的对照采样，而不是证据模型本身

### 4.4 特殊入口项

| key | 中文名 | 当前判断 | 预期入口 | 关键问题 | 成功定义 | 失败降级 |
|---|---|---|---|---|---|---|
| `encrypted_waybill` | 密文面单 | 更像配置面板入口 | `configFilter` 或二级面板 | 是否能从主搜索页稳定打开 | 能定位入口并稳定应用 | `special_panel_unmapped` |

#### 特殊入口项统一实施动作

1. 找入口 selector
2. 打开面板
3. 找面板内真实控件
4. 应用后观察结果变化

#### 2026-06-27 新增页面结构证据

- 标准搜索页（`selloffer/offer_search.htm`）：
  - 已在 dump 中观察到：
    - `高级筛选`
    - `.search-filt-item`
    - `.sn-row`
    - `.sn-select-wrap`
  - 说明此页面更适合走“标准筛选条 / 高级筛选区”定位策略。
- 图搜结果页：
  - 未观察到：
    - `高级筛选`
    - `配置筛选`
  - 已观察到：
    - `configFilter / configLabel` 承载 `密文面单`
    - `bottomFilterOption` 承载 `分销严选 / 一件代发 / 1件代发包邮 / 官方物流`
  - 说明此页面不能再依赖“高级筛选触发词”，而应直接命中对应容器。

#### 当前实现收口

- runtime 需要先识别布局：
  - `image_result_filter_bar`
  - `standard_search_filter_bar`
- 再选择入口策略：
  - 图搜结果页：`configFilter / configLabel / bottomFilterOption`
  - 标准搜索页：`.search-filt-item / .select-item / .sn-col-item`
- 当前新增的 runtime 证据：
  - `verification_detail.page_filter_layout`
  - `verification_detail.entry_selector_strategy`
- 当前新增的 runtime 动作分层：
  - `ui_checkbox_candidate`
  - `semantic_combo_candidate`
  - `special_panel_candidate`
- 对图搜结果页中已直接可见的筛选项，runtime 当前已具备：
  - 点击真实容器
  - 观察选中态
  - 在成功时升级为 `applied / ui_automation`
  - 在失败时升级为 `ui_apply_not_observed`
- 仍未拿到的闭环证据：
  - 真实页面点击 `密文面单` 后，是否出现稳定选中态
  - 真实页面点击后，是否带来结果变化或 URL / query 侧证据
  - `single_piece_free_shipping` 在真实页面里，究竟是：
    - 独立筛选项
    - 还是组合语义在 UI 上的展示入口

#### 当前已落地的中间证据结构

当结果页文本已经命中 `密文面单`，但动作链路尚未打通时，runtime 需要至少保留：

- `verification_detail.probe_mode = "html_text_scan"`
- `verification_detail.observation_scope = "result_page_text"`
- `verification_detail.entry_signal_detected = true`
- `verification_detail.entry_signal_type = "text_term"`
- `verification_detail.next_required_action = "panel_open_and_toggle"`

这样后续继续推进特殊入口项时，可以明确知道：
- 入口线索来自哪里
- 还缺哪一段真实动作

上述三项元数据同时也应该进入共享定义真源与快照层投影：

- `observation_scope`
- `entry_signal_type`
- `next_required_action`

避免它们只存在于某条 runtime 分支里，导致前端解释和后续验证无法稳定复用。

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

### 5.5 当前剩余调研缺口

下面这些点已经有方向，但还不能称为“调研闭环”：

1. `single_piece_free_shipping`
   - 已确认图搜结果页存在独立入口
   - 但还没在真实 1688 页面完成“独立项 vs 组合语义”的最终对照
2. `encrypted_waybill`
   - 已确认存在特殊入口线索与面板动作路径
   - 但还没在真实页面上完成稳定的最终结果变化闭环
3. DOM checkbox 项
   - 图搜结果页已有容器级点击路径
   - 标准搜索页 selector 还需继续收紧
4. 配置 -> runtime -> 快照 -> 详情解释
   - 契约已经成形
   - 但仍需继续补齐灰区状态的静态回归，避免 UI / API 解释重新分叉

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

### 6.4 统一结论字段模板

对批次 5 中最容易解释分叉的两类项，后续调研与实现都应优先收口到统一结论字段，而不是继续依赖前端拼接：

| filter_key | mapping_type | 统一字段 | 当前已知值 | 用途 |
|---|---|---|---|---|
| `single_piece_free_shipping` | `semantic_combo_candidate` | `semantic_conclusion` | `dependency_pair_incomplete` / `dependency_pair_ready_pending_runtime` / `independent_entry_observed_pending_result_validation` / `independent_entry_no_result_shift` / `independent_entry_result_shift_observed` | 给 UI / API / 快照提供统一语义结论 |
| `encrypted_waybill` | `special_panel_candidate` | `special_panel_conclusion` | `entry_signal_detected_pending_panel_mapping` / `panel_open_or_toggle_failed` / `panel_action_applied_no_result_shift` / `panel_action_result_shift_observed` | 给 UI / API / 快照提供统一入口结论 |

#### 统一结论字段验收要求

1. 必须同步出现在：
   - `filter_status_map`
   - `verification_details`
   - `query_verification_details`
2. 前端必须优先展示统一结论，再补原始细节
3. 新增灰区状态时，必须先补静态断言，再允许 UI 消费

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
- 当前阶段：批次 0 ~ 4 已完成，批次 5 / 6 / 7 仍在推进中，不能宣称已完全闭环
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

## 8.1 更细的提交顺序建议

为减少“调研先散掉、实现再返工”，后续提交建议继续细化为：

### 提交 5A：批次 5 统一结论字段与灰区回归

文件：

- `src/xianyu_tools/config.py`
- `scripts/validate_source_channel_config.py`
- `web/app.jsx`

验收：

1. `semantic_conclusion` 与 `special_panel_conclusion` 三层投影一致
2. UI 不再自己猜测灰区状态
3. 静态校验覆盖“动作失败 / 动作成功但结果不变 / 动作成功且结果变化”

### 提交 5B：批次 5 真实动作链路补强

文件：

- `scripts/run_ali1688_slow_flow.py`

验收：

1. 图搜结果页与标准搜索页都能先识别布局，再选入口策略
2. `verification_detail` 中稳定保留：
   - `page_filter_layout`
   - `entry_selector_strategy`
   - `result_signature_before_action`
   - `result_signature_after_action`
   - `result_signature_changed`

### 提交 6A：DOM checkbox 项页面来源与 selector 收紧

文件：

- `scripts/run_ali1688_slow_flow.py`
- `scripts/validate_source_channel_config.py`

验收：

1. 每一项都能明确来自稳定筛选区，而不是临时浮层
2. 图搜结果页至少一套 selector 链路稳定
3. 失败统一收口到 `ui_selector_not_stable` 或 `ui_apply_not_observed`

### 提交 6B：配置页 / 配置接口 / runtime 渠道隔离复核

文件：

- `web/app.jsx`
- `src/xianyu_tools/config.py`
- `src/web_api/main.py`
- `scripts/run_full_pipeline.py`

验收：

1. 新增渠道默认空配置
2. 非 `ali1688` 渠道回读为空 `filters`
3. 同一任务多渠道时不会串写筛选快照

### 提交 7A：详情接口排序契约与渠道解释收口

文件：

- `src/web_api/main.py`
- `web/app.jsx`

验收：

1. 排序固定为 `预估纯利倒序`
2. 渠道筛选只影响展示范围
3. 详情页可解释“每个渠道用了哪些筛选策略、哪些成功、哪些失败”

### 提交 7B：筛选摘要解释改成 API-first

文件：

- `src/web_api/main.py`
- `web/app.jsx`
- `scripts/validate_source_channel_config.py`

验收：

1. `filter_summary` 直接下沉：
   - `filter_status_map`
   - `query_verification_details`
2. 前端统一归一化：
   - 兼容 snake_case / camelCase
   - 优先消费接口 summary
   - 只有缺失时才退回 snapshot 推断
3. 静态校验继续锁住：
   - 详情摘要包含 runtime 明细字段
   - 任务级渠道摘要保持同一套解释字段

### 提交 7C：source 卡片消费单条货源筛选摘要

文件：

- `web/app.jsx`
- `scripts/validate_source_channel_config.py`

验收：

1. `sources[*].source_filter_summary` 不再只是接口保留字段
2. 详情页单条货源卡片直接展示：
   - `已配置未验证`
   - `已注入待验证`
   - `已生效`
   - `未应用`
   - `历史快照缺失 / 当前渠道不支持`
3. 静态契约继续锁住：
   - `source_filter_summary` 保留已启用全集
   - `applied / query_injected / unapplied` 三类状态稳定

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
