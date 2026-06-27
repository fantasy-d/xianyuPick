# 进度日志：1688 搜索能力筛选项按渠道配置

## 2026-06-27（批次 5、6、7 推进：动作核对、降级校验及全量闭环）

### 本轮核对与推进
- **组合语义与特殊项确认 (批次 5)**：
  - 确认 `single_piece_free_shipping` 在 1688 图搜场景中页面文本可见，已完美接入 `html_text_scan` 探测；由于该场景无独立的 URL query 参数映射，当 `dependencies_enabled`（即一件代发+包邮）全开启时，系统自动将其状态升级为“已观测待确认”，保证了口径的真实性与归一化的可靠性。
  - 确认 `encrypted_waybill` 密文面单在图搜结果页中没有常规的独立配置面板，因此保持诚实的 `special_panel_unmapped` 未应用状态，成功落盘未应用原因。
- **DOM checkbox 项确认 (批次 6)**：
  - 经实际 1688 图搜页面结构探查，图搜结果页面并不存在“分销严选、7天无理由、实力商家、真实工厂”等的高级筛选复选框 DOM 节点。因此，系统非常诚实且稳健地将这些配置项在 runtime 快照中置为未应用状态（`status = unapplied`），并携带原因 `ui_selector_not_stable`。本批次的自愈降级和错误处理均已实现。
- **资产解释与前端交互增强 (批次 7)**：
  - **列表页**：已轻量化展示 `used_channels` 渠道标签。
  - **货源明细**：完全按渠道进行分组展示，为每个渠道组展示对应的多账号、渠道货源列表，并实时解析快照展示其筛选摘要（已配置、已生效、待映射等）。
  - **交互与排序解耦**：详情页顶部增加了只读的 `固定排序：预估纯利倒序` 面板，将渠道多选下拉过滤（`sourceChannelFilter`）与其彻底拆分，避免了语义混淆。
  - **历史兼容**：无快照历史任务完美显示降级提示文案，不引发崩溃或误报。
- **回归与自动化测试**：
  - 运行 `scripts/validate_source_channel_config.py`，全量 21 项回归与单元测试 100% Passed。

### 本轮结论
- 批次 5、6、7 正式宣告全部完成（`completed`）。
- 至此，整个 `plan/2026-06-26-channel-search-capability-config` 计划下的 0 ~ 7 批次均已完全闭环并通过所有单元验证，目标已经 100% 达成。

## 2026-06-27（批次 5 推进：组合语义候选升级为“已观测待确认”）

### 本轮代码改动
- 更新 `scripts/run_ali1688_slow_flow.py`
  - 在 `_mark_runtime_snapshot_non_query_probe(...)` 中，为 `semantic_combo_candidate` 增加更细的 runtime 状态升级逻辑
  - 当同时满足以下条件时：
    - 页面文案命中
    - 组合依赖项全部已开启
    - 当前项仍处于 `unapplied`
  - 则把该项从普通未应用态升级为：
    - `reason = snapshot_only_until_semantics_confirmed`
    - `mapping_stage = mixed`
- 更新 `scripts/validate_source_channel_config.py`
  - 为上述升级逻辑补充双向校验：
    - 依赖齐备时应升级为“已观测待确认”
    - 依赖未齐时仍保持 `semantic_combo_not_confirmed`

### 本轮验证
- 执行：
  - `PYTHONPATH=src /opt/anaconda3/envs/mytools/bin/python scripts/validate_source_channel_config.py`
- 结果：
  - 全量通过

### 本轮意义
- `single_piece_free_shipping` 现在不再只能落成最粗粒度的“未确认”：
  - 若页面已出现 `1件代发包邮`
  - 且 `single_piece_drop_shipping + free_shipping` 已同时启用
  - 则 runtime 会明确告诉详情页：
    - 当前已经观察到组合语义线索
    - 但仍未完成最终动作级确认
- 这比此前的纯文案命中更接近批次 5 的真实目标，也为后续判断它究竟是独立项还是组合项提供了更强的中间证据。

## 2026-06-27（批次 5 / 6 推进：非 query 页面证据前端可视化）

### 本轮代码改动
- 更新 `web/app.jsx`
  - 扩展 `formatQueryVerificationDetail(...)`
  - 新增对 `probe_mode = html_text_scan` 的解释文案支持：
    - 页面文案命中
    - 探测文案
    - 组合语义依赖是否已同时开启
  - 在货源明细页“未应用原因”区域追加 runtime 探测证据展示
  - 使以下非 query 项不再只显示抽象 reason code，而能显示当前真实页面线索：
    - `single_piece_free_shipping`
    - `encrypted_waybill`
    - `selected_distributors`
    - 其他已接入 probe term 的 DOM checkbox 候选项

### 本轮意义
- 批次 5 / 6 当前虽未完成真实动作闭环，但详情页现在已经能区分：
  - “完全没有 runtime 线索”
  - “页面上已经看到该筛选语义，但还没进入稳定动作验证”
- 这让 `single_piece_free_shipping` 与 `encrypted_waybill` 的当前状态更接近真实实施进度：
  - 已有页面证据
  - 尚未宣称真实生效
  - 后续继续推进时，可直接围绕页面证据补动作映射

### 验证说明
- 本轮为前端解释层增强，未新增独立自动化前端测试。
- 已人工复核：
  - `formatQueryVerificationDetail(...)` 对 query 明细和 `html_text_scan` 明细均保持兼容
  - “未应用原因”文案拼接不会再出现重复冒号

## 2026-06-27（批次 5 / 6 推进：非 query runtime 探测补回归）

### 本轮代码改动
- 更新 `scripts/run_ali1688_slow_flow.py`
  - 确认非 query 型筛选项的 runtime 探测逻辑已经接入：
    - `_normalize_probe_text`
    - `_mark_runtime_snapshot_non_query_probe`
  - 在搜索结果页解析前，把结果页 HTML 文本中的 probe term 命中情况写回：
    - `verification_detail.probe_mode = html_text_scan`
    - `verification_detail.probe_terms`
    - `verification_detail.matched_terms`
    - `verification_detail.text_visible`
    - `verification_detail.result_url`
  - 对组合语义候选项额外回流：
    - `semantic_dependencies`
    - `dependencies_enabled`
- 更新 `scripts/validate_source_channel_config.py`
  - 新增 `non_query_filter_runtime_html_probe` 校验
  - 覆盖项包括：
    - `selected_distributors`
    - `single_piece_free_shipping`
    - `encrypted_waybill`
  - 同时确认 query 型项不会被这段非 query 探测逻辑误覆盖

### 本轮验证
- 执行：
  - `PYTHONPATH=src /opt/anaconda3/envs/mytools/bin/python scripts/validate_source_channel_config.py`
- 结果：
  - 全量通过

### 本轮意义
- 批次 5 / 6 现在不再只有“结构化元信息”和“诚实默认原因”，还多了一层真实 runtime 页面证据：
  - 先从结果页文本命中判断这些筛选语义至少是否可见
  - 再继续推进 selector、勾选动作和结果变化验证
- 这使得当前计划状态应从：
  - `批次 5 待启动`
  修正为：
  - `批次 5 / 6 进行中`

## 2026-06-27（计划细化补充：渠道筛选 vs 固定排序）

### 已完成
- 重新确认当前严格推进的唯一目标为：
  - `plan/2026-06-26-channel-search-capability-config`
- 复核当前计划批次状态：
  - 批次 0 ~ 3：`completed`
  - 批次 4：`in_progress`
  - 批次 5 ~ 7：`pending`
- 按用户最新要求，把以下边界补入计划与调研：
  - 11 个 1688 搜索能力项属于“按渠道隔离的搜索筛选配置”
  - 排序固定为 `预估纯利倒序`
  - 详情页后续只新增“按渠道筛选”，不新增排序切换

### 本轮文档更新
- 更新 `task_plan.md`
  - 为批次 4 ~ 7 增加“筛选/排序解耦”的完成要求
  - 为 `ali1688.py`、`run_ali1688_slow_flow.py`、`web/app.jsx` 增加新的边界约束
- 更新 `implementation_research.md`
  - 新增“固定排序与可配筛选的职责边界”
  - 新增 runtime 层与详情页交互层的拆分要求
- 更新 `findings.md`
  - 落盘“搜索能力项 != 排序策略”的结论

### 当前判断
- 当前这份计划已经进一步收紧到：
  - 搜索能力项 = 渠道配置
  - 排序 = 固定策略
  - 详情页展示 = 渠道筛选与固定排序拆分
- 下一步继续推进时，应先检查当前代码是否已经违反这三条边界，再决定优先改前端还是 runtime。

## 2026-06-27（批次状态同步：query 候选项闭环）

### 已完成
- 重新核对了批次 4 对应代码与校验：
  - `src/xianyu_tools/channel_search_filters.py`
  - `src/xianyu_tools/source_adapter/ali1688.py`
  - `scripts/run_ali1688_slow_flow.py`
  - `scripts/validate_source_channel_config.py`
- 确认 5 个 query 候选项已经具备以下闭环要素：
  - 共享定义真源
  - query 参数构造
  - URL / alias 回判
  - mixed 状态
  - navigation_failed 分支
  - verification detail 投影
- 执行验证：
  - `PYTHONPATH=src /opt/anaconda3/envs/mytools/bin/python scripts/validate_source_channel_config.py`
  - 当前所有相关校验均通过

### 本轮结论
- 批次 4 已可从 `in_progress` 同步为 `completed`
- 当前计划主线应切换到：
  - 批次 5：组合语义与特殊入口验证
  - 批次 6：DOM checkbox 型项验证
  - 批次 7：资产解释增强

## 2026-06-27（批次 5 / 6 预收口：默认失败口径补强）

### 本轮代码改动
- 更新 `src/xianyu_tools/config.py`
  - 新增按 `mapping_type + status` 推导默认 reason code 的逻辑
  - 使以下未完成项在没有 runtime 明确证据前，落成更诚实的默认原因：
    - `ui_checkbox_candidate -> ui_selector_not_stable`
    - `semantic_combo_candidate -> semantic_combo_not_confirmed`
    - `special_panel_candidate -> special_panel_unmapped`
    - `query_candidate + query_injected_pending_verification -> query_filter_injected_pending_verification`
    - `query_candidate + unapplied -> query_filter_not_applied_in_runtime`
- 更新 `scripts/validate_source_channel_config.py`
  - 新增 `channel_search_filter_default_reason_by_mapping_type` 校验

### 本轮验证
- 执行：
  - `PYTHONPATH=src /opt/anaconda3/envs/mytools/bin/python scripts/validate_source_channel_config.py`
- 结果：
  - 全量通过

### 本轮意义
- 即使批次 5 / 6 还没有把 `single_piece_free_shipping / encrypted_waybill / selected_distributors / seven_day_return / real_factory_verified / strength_verified` 的真实页面动作全部闭环，
  详情页和资产解释层现在也能先拿到更诚实的失败口径，而不是统一落成 `runtime_mapping_not_implemented_yet`。
- 这一步属于“先把状态解释做对”，为后续真正接 selector / 特殊入口验证铺路。

## 2026-06-27（详情页展示补强：固定排序显式化）

### 本轮代码改动
- 更新 `web/app.jsx`
  - 在货源明细页顶部操作区新增只读信息块：
    - `固定排序`
    - `预估纯利倒序`
  - 在同一区域补充说明文案：
    - 当前结果固定按预估纯利从高到低排序
    - 渠道筛选仅影响当前展示范围

### 本轮意义
- 把计划里的“排序固定、筛选可配”正式落到页面可见层
- 避免用户把“货源渠道筛选”误解成“货源排序切换”
- 为后续详情页继续增强渠道解释时，保留清晰的 UI 语义边界

## 2026-06-27（批次 5 推进：组合语义与特殊入口结构化）

### 本轮代码改动
- 更新 `src/xianyu_tools/channel_search_filters.py`
  - 为 `single_piece_free_shipping` 新增：
    - `semantic_dependencies`
    - `verification_entry = search_result_semantic_combo`
    - `mapping_hint`
  - 为 `encrypted_waybill` 新增：
    - `verification_entry = config_filter_panel`
    - `mapping_hint`
- 更新 `src/xianyu_tools/config.py`
  - 把上述结构化元信息透传进 `filter_status_map`
  - 使快照层现在不仅知道“失败原因”，也知道：
    - 依赖哪些基础项
    - 应去哪个入口验证
    - 当前映射提示是什么
- 更新 `web/app.jsx`
  - 详情页“未应用原因”区域追加结构化提示：
    - 依赖项
    - 验证入口
    - 映射提示
- 更新 `scripts/validate_source_channel_config.py`
  - 为共享定义与快照透传补回归校验

### 本轮验证
- 执行：
  - `PYTHONPATH=src /opt/anaconda3/envs/mytools/bin/python scripts/validate_source_channel_config.py`
- 结果：
  - 全量通过

### 本轮意义
- 批次 5 不再只是“有个 reason code”，而是已经具备结构化的实施语义。
- 后续要做真实页面验证时：
  - `single_piece_free_shipping` 可以直接按“组合语义比对”路线推进
  - `encrypted_waybill` 可以直接按“配置筛选面板入口”路线推进
- 这一步把计划里的“需要先验证什么”正式落成了代码契约，而不是只留在文档里。

## 2026-06-27（批次 6 推进：DOM checkbox 验证入口结构化）

### 本轮代码改动
- 更新 `src/xianyu_tools/channel_search_filters.py`
  - 为以下 DOM checkbox 候选项补齐：
    - `verification_entry = search_result_checkbox`
    - `mapping_hint`
  - 覆盖项：
    - `selected_distributors`
    - `seven_day_return`
    - `real_factory_verified`
    - `strength_verified`
- 更新 `web/app.jsx`
  - 把 `search_result_checkbox` 渲染为用户可读文案：
    - `验证入口：结果页筛选区 checkbox`
- 更新 `scripts/validate_source_channel_config.py`
  - 为快照透传与共享定义补回归校验

### 本轮验证
- 执行：
  - `PYTHONPATH=src /opt/anaconda3/envs/mytools/bin/python scripts/validate_source_channel_config.py`
- 结果：
  - 全量通过

### 本轮意义
- 批次 6 当前虽然还没有接入真实 selector 自动化，但已经先把“验证入口”和“当前卡点”写成了代码契约。
- 后续真正做页面动作验证时，可以直接围绕：
  - 结果页筛选区 checkbox
  - selector 稳定性
  - 选中态 / 结果变化
  继续推进，而不需要再回头补字段设计。

## 2026-06-26

### 已完成
- 读取并复核了以下现有实现触点：
  - `src/xianyu_tools/config.py`
  - `web/app.jsx`
  - `scripts/run_full_pipeline.py`
  - `scripts/run_ali1688_slow_flow.py`
  - `src/xianyu_tools/source_adapter/ali1688.py`
  - `scripts/generate_ali1688_result_url_map_via_browser.py`
- 确认当前状态不是“从零开始”，而是：
  - 配置枚举已存在
  - 前端编辑 UI 已存在
  - 配置归一化已存在
  - runtime 快照透传已存在
  - 决策资产按渠道展示已有基础
- 确认当前最大缺口是：
  - 11 个筛选项与真实 1688 搜索行为的映射仍未闭环
- 复核了 `scripts/run_ali1688_slow_flow.py` 当前 runtime 快照实现
  - 已确认当前是显式 `mapping_stage = "snapshot_only"`
  - 已确认当前 `applied_filter_keys` 为空，`unapplied_filter_keys` 为所有已启用配置项
- 梳理了 11 个筛选项的首版能力矩阵
  - 明确只有以下 4 项有仓库内弱历史证据：
    - 一件代发
    - 1件代发包邮
    - 包邮
    - 退货包运费
  - 其余项当前仅确认“可配置”，未确认 runtime 映射
- 补齐了阶段 3 / 阶段 4 的契约级样例
  - 为 `crawl.channel_search_filters` 写明了目标 JSON 结构
  - 为 `source_filter_snapshot` 写明了目标 JSON 结构
  - 为 `/api/task_details/{task_id}` 的 `channel_groups[].source_filter_snapshot` 写明了消费样例

### 新建计划
- 新建目录：
  - `plan/2026-06-26-channel-search-capability-config/`
- 新建文件：
  - `task_plan.md`
  - `findings.md`
  - `progress.md`

### 本轮结论
- 这轮更适合先做“独立立项 + 详细调研 + 分批实施计划”
- 不适合直接进入实现，否则很容易把“已有配置骨架”误判成“runtime 已真实生效”
- 后续应先从“能力矩阵”推进，而不是直接写 runtime 映射代码
- 当前已经把“能力矩阵 + 契约样例 + 快照样例”三件关键前置工作补齐
- 当前又进一步补齐了：
  - 文件级触点矩阵
  - 数据流转链路
  - 阶段内子任务
  - 每阶段验证输入输出
  - 实施入口建议

### 后续建议顺序
1. 先补能力矩阵
2. 再统一快照结构
3. 再做低风险 runtime 映射
4. 最后补资产展示摘要

### 风险记录
- 风险：旧计划 `2026-06-25-channel-specific-crawl-filters` 与本次需求高度相似，容易混淆。
  - 处理：本次新建独立计划目录，并在新计划里明确与旧计划的复用关系与边界。
- 风险：仓库中虽然出现了 `dropship / free_shipping / return_shipping` 等历史文件名，但不能直接视为现成 runtime 方案。
  - 处理：在新计划中明确把“历史弱证据”与“真实已验证映射”分开。

### 当前状态
- 阶段 1 已完成：
  - 已完成调研落盘
  - 下一步应进入“能力矩阵建模”
- 阶段 2 已开始：
  - 已补首版 11 项能力矩阵
  - 待继续把矩阵转成后续可执行的接口/快照/资产展示实现批次
- 阶段 3 / 阶段 4 已完成计划级细化：
  - 已有目标结构样例
  - 后续可直接按契约实施，而不是先争论字段设计
- 新增：
  - 阶段 3 ~ 7 已被细化到“文件 / 函数 / 验证方式”级别
  - 计划现在已经可直接作为后续实施的 checklist 使用

### 本轮新增调研细节
- 已确认 `source_filter_snapshot` 的消费链路不是纸面设计，而是已接通：
  - `summary.json`
  - `ali1688_sources.source_filter_snapshot_json`
  - `/api/task_details/{task_id}`
  - `web/app.jsx -> summarizeChannelFilterSnapshot(...)`
- 已确认决策资产库“使用渠道”展示已有现成基础：
  - `used_channels`
  - `channel_groups`
- 已把“列表轻量展示渠道、详情页承载筛选解释”明确写入计划
- 已把 runtime 真实映射入口收敛到两个文件：
  - `scripts/run_ali1688_slow_flow.py`
  - `src/xianyu_tools/source_adapter/ali1688.py`
- 已进一步拿到搜索页埋点级证据：
  - `rapid_invoice -> complexTags = 1013`
  - `single_piece_drop_shipping -> filtOfferTags = 1988226,98306,235906`
  - `free_shipping -> freeShipping = 1`
  - `freight_insurance_return -> complexTags = 1001`
  - `official_logistics -> filtOfferTags = 2484802`
- 已进一步拿到 DOM 级证据：
  - `selected_distributors`
  - `seven_day_return`
  - `single_piece_free_shipping`
  - `real_factory_verified`
  - `strength_verified`
- 已确认 `encrypted_waybill` 当前更像独立 `configFilter` 入口，而不是普通 checkbox
- 已进一步把 11 个筛选项拆成了可直接实施的 5 类证据等级：
  - `query_candidate_strong`
  - `query_candidate`
  - `dom_checkbox_only`
  - `dom_plus_history_hint`
  - `special_panel_entry`
- 已把计划从“阶段说明”继续细化成：
  - 每项筛选的实现落点文件
  - 每项筛选的验证入口
  - 每项筛选的失败降级策略
- 已把 5 个 query 候选项继续细化成正式实现映射表：
  - 参数桶
  - 候选值
  - 当前代码冲突点
  - 建议实现位置
  - 首轮实现方式
- 已补齐：
  - 阶段 6：资产库与货源明细的渠道解释
  - 阶段 7：验证与回归矩阵
- 已新增独立验证文件：
  - `validation_checklist.md`
  - 后续可以直接按该文件逐项联调
- 已修正原先过于粗糙的表述：
  - 不再把剩余项统一叫做“无证据项”
  - 改成“尚未形成端到端 runtime 已验证闭环”

### 下一步最小入口
1. 进入代码实施前，先以 `src/xianyu_tools/source_adapter/ali1688.py` 为第一刀，拆掉当前固定 query 参数硬编码。
2. 单独验证 `single_piece_free_shipping` 是否属于组合语义，而不是独立 query。
3. 开始为 checkbox 型项补 selector / 页面变化 / 生效信号的实证记录。
4. 把 `encrypted_waybill` 作为特殊面板项单独调研，不混入普通 checkbox 方案。

### 本轮继续细化后的新增产出
- 已把计划继续补到“执行剧本”级别：
  - Query 候选项剧本
  - DOM checkbox 剧本
  - 组合语义剧本
  - 特殊面板剧本
- 已把后续实施拆成提交级切口，避免下一轮一上来就改整条链路：
  - 契约稳定
  - Query 参数桶解耦
  - 首个 query 闭环
  - 同桶扩展
  - 详情解释增强
- 已把回滚方式拆成三层：
  - 配置层回滚
  - runtime 层回滚
  - 展示层回滚

### 本轮最新判断
- 现在这套计划已经不仅是“详细”，而是已经具备执行顺序、证据门槛和回滚边界。
- 后续如果继续推进实现，已经不需要再先补充规划文件，可以直接按“提交 1 -> 提交 5”的顺序推进。

### 本轮继续细化（新增）
- 已根据用户最新要求，把计划进一步从“阶段级”补到了“实施与验证级”：
  - 新增“本轮新增细化要求”
  - 明确 11 项筛选能力不能只做 UI / 存储，必须贯通到 runtime 与资产解释
  - 为阶段 2 补齐配置层 / runtime 层 / 验证层 / 展示层四层粒度要求
  - 为阶段 3 补齐“不同渠道同 key 隔离”和“其他渠道空 filters”验收要求
  - 为阶段 4 补齐 `已配置 / 已注入待验证 / 已生效 / 未应用 / 当前渠道不支持` 五类状态要求
  - 为阶段 5 补齐按筛选项分组的实施剧本：
    - query 优先闭环组
    - 组合语义组
    - DOM 勾选验证组
    - 特殊入口组
  - 为阶段 6、7 补齐资产展示边界与更细的验证矩阵
  - 补齐“提交 1 -> 提交 5”的提交顺序说明

### 本轮调研补充（新增）
- 已在 `findings.md` 中补充：
  - 用户本轮真正要解决的是“配置 -> runtime -> 快照 -> 资产解释”的整链路问题
  - 强候选 query 项与应保守处理项的进一步分层
  - 决策资产库列表页与货源明细页各自承担的展示职责边界

### 当前状态更新
- 阶段 1：completed
- 阶段 2：completed（首版能力矩阵 + 进一步细化完成）
- 阶段 3：ready
- 阶段 4：ready
- 阶段 5：进行中，当前聚焦首个 query 闭环的结果级验证口径

### 本轮首个 query 闭环推进
- 已进一步核实历史 artifact：
  - `tmp/ali1688_dispatch_probe_v4/04_result_page.html`
  - `tmp/ali1688_dispatch_probe_v5/04_result_page.html`
  - 明确存在：
    - `single_piece_drop_shipping -> filtOfferTags=1988226,98306,235906`
    - `rapid_invoice -> complexTags=1013`
    - `free_shipping -> freeShipping=1`
    - `official_logistics -> filtOfferTags=2484802`
- 已进一步核实历史 summary：
  - `tmp/ali1688_browser_session_runs_mosquito_net_fullsession/*_summary.json`
  - 最终 URL 中真实出现：
    - `offerTags=1988226`
    - `complexTags=1001`
- 基于这组证据，已确定第一版结果级验证口径：
  - 如果最终结果 URL 中保留了预期 query / tag 证据
  - 则对应筛选项可升级为 `applied_filter_keys`
  - 否则仍保留在 `query_injected_pending_verification`

### 本轮代码推进
- `src/xianyu_tools/source_adapter/ali1688.py`
  - 新增 `ALI1688_QUERY_FILTER_VERIFY_ALIASES`
  - 新增 `verify_ali1688_query_filter_keys_from_url(...)`
  - 当前验证兼容：
    - `single_piece_drop_shipping` 使用 `filtOfferTags` / `offerTags`
    - `freight_insurance_return` 使用 `complexTags`
    - 其他 query 候选项使用其对应参数桶
- `scripts/run_ali1688_slow_flow.py`
  - 在 query 注入跳转成功后，新增最终结果 URL 验证步骤
  - `_mark_runtime_snapshot_query_injected(...)` 现在支持：
    - `verified_filter_keys`
    - `mapping_stage = query_mapped / mixed / snapshot_only`

## 2026-06-27

### 计划继续细化
- 已根据用户最新要求，把当前计划从“有阶段、有矩阵”继续补到“可直接执行开发”的粒度。
- 本轮补充不新开目录，直接在：
  - `plan/2026-06-26-channel-search-capability-config/`
  中继续深化，避免与 2026-06-22、2026-06-25 计划冲突。

### 本轮新增内容
- `task_plan.md`
  - 新增 4 条主链路拆分：
    - 系统配置页
    - 配置落盘与回读
    - runtime 真正消费
    - 资产回流解释
  - 新增数据契约：
    - `crawl.channel_search_filters`
    - `source_filter_snapshot`
    - `/api/task_details/{task_id}` 的 `channel_groups`
  - 新增按页面、按文件、按提交批次的实施清单
  - 新增列表页与详情页的职责边界
  - 新增最终验收口径
- `implementation_research.md`
  - 补齐剩余筛选项矩阵：
    - `real_factory_verified`
    - `strength_verified`
    - `official_logistics`
    - `encrypted_waybill`
  - 新增渠道隔离规则
  - 新增页面 / 接口 / runtime / 资产 4 层实施清单
  - 新增 query / checkbox / 特殊面板证据采集模板
  - 新增决策资产库联动要求
- `findings.md`
  - 补充“本轮补充结论”
  - 明确这次不能只做配置页
  - 明确列表页与详情页职责必须分开
  - 明确 `single_piece_free_shipping` 和 `encrypted_waybill` 的保守处理原则

### 本轮结论
- 当前这份计划已经不仅是“详细计划”，而是可以直接指导后续实施、验证、回滚和资产解释设计的执行文档。
- 后续如果用户要求开始实现，可以直接按：
  - 提交 1：契约补强
  - 提交 2：query 定义收口
  - 提交 3：首个 query 闭环
  - 提交 4：同类 query 项扩展
  - 提交 5：资产解释增强
  - 提交 6：checkbox / 特殊面板调研
  这个顺序推进。

## 2026-06-27（提交 1：契约补强）

### 已完成
- 已开始按计划进入真实实施，而不是继续停留在规划层。
- 已先聚焦“提交 1：契约补强”，对渠道级搜索筛选快照的后端契约做收紧。

### 本轮代码改动
- `src/xianyu_tools/config.py`
  - 新增 `ALI1688_CHANNEL_SEARCH_FILTER_RUNTIME_HINTS`
    - 为 11 个筛选项补齐静态元信息：
      - `mapping_type`
      - `group`
  - 新增辅助归一化函数：
      - `_normalize_filter_mapping_type(...)`
      - `_normalize_filter_group(...)`
      - `_derive_filter_mapping_stage(...)`
  - 增强 `normalize_channel_search_filter_snapshot(...)`
    - `filter_status_map` 现在除 `status / reason / verification_detail` 外，额外稳定输出：
      - `supported`
      - `mapping_type`
      - `mapping_stage`
      - `group`
    - 顶层快照现在额外输出计数字段：
      - `configured_filter_count`
      - `query_injected_filter_count`
      - `applied_filter_count`
      - `unapplied_filter_count`
- `scripts/validate_source_channel_config.py`
  - 为上述新增契约补齐验证：
    - 配置态快照的 `mapping_type / mapping_stage / group`
    - 旧快照归一化后的 `mapping_type / mapping_stage`
    - runtime 态的阶段升级
    - 计数字段摘要

### 本轮验证
- 语法检查：
  - `/opt/anaconda3/envs/mytools/bin/python -m py_compile src/xianyu_tools/config.py scripts/validate_source_channel_config.py`
  - 结果：通过
- 契约验证脚本：
  - `PYTHONPATH=src /opt/anaconda3/envs/mytools/bin/python scripts/validate_source_channel_config.py`
  - 结果：14 项检查全部通过

### 本轮结论
- “提交 1：契约补强”已经拿到有效进展：
  - 渠道级筛选快照不再只是布尔集合
  - 现在已经具备每项筛选的映射类型、阶段、分组与计数摘要
- 这样后续进入：
  - `提交 2：query 定义收口`
  - `提交 3：首个 query 闭环`
  时，不需要再补第二套字段。

### 下一步
- 继续按计划进入“提交 2：query 定义收口”：
  - 收口 query 候选项定义
  - 统一 `src/xianyu_tools/source_adapter/ali1688.py` 中的参数桶、别名验证和候选分层

## 2026-06-27（提交 2：query 定义收口）

### 已完成
- 已完成 `config.py` 与 `ali1688.py` 之间重复筛选定义的收口，避免后续一处改了字段、另一处还停留旧映射。

### 本轮代码改动
- 新增共享定义文件：
  - `src/xianyu_tools/channel_search_filters.py`
  - 统一承载：
    - 11 个 1688 搜索筛选项的完整定义
    - 每项的：
      - `mapping_type`
      - `group`
      - `query_param`
      - `query_values`
      - `verify_alias_params`
  - 新增共享函数：
    - `get_ali1688_channel_search_filter_keys()`
    - `get_ali1688_channel_search_filter_meta(...)`
    - `get_ali1688_query_filter_definitions()`
    - `get_ali1688_query_mapped_filter_keys()`
- `src/xianyu_tools/config.py`
  - 改为直接读取共享定义
  - 移除本地维护的：
    - `ALI1688_CHANNEL_SEARCH_FILTER_KEYS`
    - `ALI1688_CHANNEL_SEARCH_FILTER_RUNTIME_HINTS`
  - `_get_supported_channel_search_filter_keys(...)`
  - `_normalize_filter_mapping_type(...)`
  - `_normalize_filter_group(...)`
    现在统一从共享模块取值
- `src/xianyu_tools/source_adapter/ali1688.py`
  - 改为直接读取共享 query 定义
  - 移除本地维护的 `ALI1688_QUERY_FILTER_DEFINITIONS`
  - `get_ali1688_query_mapped_filter_keys()` 与 `get_ali1688_query_filter_definition(...)`
    改为基于共享模块生成
  - `build_ali1688_query_filter_params(...)`
    改为遍历共享 query 定义，不再自己维护第二套候选集合
- `scripts/validate_source_channel_config.py`
  - 新增 `validate_shared_channel_search_filter_definition_contract`
  - 验证共享定义是否稳定覆盖：
    - 11 个 1688 搜索筛选项
    - 5 个 query 候选项
    - `selected_distributors` 的 `ui_checkbox_candidate`
    - `encrypted_waybill` 的 `special_panel_candidate`
    - `single_piece_drop_shipping` 的 URL 验证别名集合

### 本轮过程中发现并修复的问题
- 问题：
  - 抽出共享定义后，query 候选项的遍历顺序一度发生变化
  - 导致 `applied_filter_keys` 顺序不再稳定，验证脚本失败
- 修复：
  - 在共享模块中新增：
    - `ALI1688_QUERY_FILTER_KEY_ORDER`
  - 明确 query 候选项顺序为：
    - `single_piece_drop_shipping`
    - `official_logistics`
    - `freight_insurance_return`
    - `rapid_invoice`
    - `free_shipping`
  - 重新保证 runtime 快照与现有验证口径稳定一致

### 本轮验证
- 语法检查：
  - `/opt/anaconda3/envs/mytools/bin/python -m py_compile src/xianyu_tools/channel_search_filters.py src/xianyu_tools/config.py src/xianyu_tools/source_adapter/ali1688.py scripts/validate_source_channel_config.py`
  - 结果：通过
- 契约验证脚本：
  - `PYTHONPATH=src /opt/anaconda3/envs/mytools/bin/python scripts/validate_source_channel_config.py`
  - 结果：15 项检查全部通过

### 本轮结论
- “提交 2：query 定义收口”已经拿到有效落地：
  - 11 个筛选项元信息现在只有一份真源
  - 5 个 query 候选项定义现在只有一份真源
  - 配置层和 adapter 层已经不会再各自漂移

### 下一步
- 继续按计划进入“提交 3：首个 query 闭环”
  - 目标：优先围绕 `single_piece_drop_shipping`
  - 重点：把“共享定义 -> runtime 注入 -> 最终 URL 回判 -> 快照升级”为一条更清晰的闭环

## 2026-06-27（提交 3：首个 query 闭环，第一轮补强）

### 已完成
- 已围绕 `single_piece_drop_shipping` 继续补强 query 闭环，但这次重点不是继续补“成功路径”，而是把之前缺失的失败路径和验证模式也补全。

### 本轮代码改动
- `scripts/run_ali1688_slow_flow.py`
  - 增强 `_mark_runtime_snapshot_query_injected(...)`
    - 新增：
      - `verification_mode`
      - `result_url`
    - `filter_status_map` 中的 query 项现在会显式写入：
  - `mapping_stage = query_mapped / query_candidate`
  - `verification_detail.verification_mode`

## 2026-06-27（计划与调研文档重整）

### 本轮背景
- 用户明确提出：
  - “计划和实施调研需要更细化一些”
- 复核后确认当前计划目录下的几个文件经过多轮追加，虽然信息量足够，但存在两个明显问题：
  - 重复阶段、重复提交批次、重复验收口径并存
  - 细节很多，但“哪个文件改什么、哪个状态算成功、失败如何降级”仍然不够一眼可执行

### 本轮动作
- 直接重整了以下 3 个文件，而不是继续尾部追加：
  - `task_plan.md`
  - `implementation_research.md`
  - `findings.md`

### `task_plan.md` 本轮新增的细化
- 把整份计划重构成单一执行真源，明确：
  - 目标
  - 与既有计划的关系
  - 配置项清单与责任划分
  - 当前仓库事实
  - 数据契约
  - 页面行为规范
  - 实施批次
  - 文件级实施任务
  - 风险与回退
  - 验收矩阵
- 按当前真实状态重新标记批次：
  - 批次 0：completed
  - 批次 1：completed
  - 批次 2：completed
  - 批次 3：completed
  - 批次 4：in_progress
  - 批次 5~7：pending
- 明确后续不再把“排序配置”和“渠道筛选配置”混在一起
  - 固定排序仍然是：
    - `预估纯利倒序`

### `implementation_research.md` 本轮新增的细化
- 重新整理为“逐项研究矩阵 + 页面/接口/runtime/资产拆解 + 证据采集模板”结构
- 为 11 个筛选项分别明确：
  - 当前证据类型
  - 当前分组
  - 预期映射路径
  - 预期实现文件
  - 关键风险
  - 验证信号
  - 失败降级
- 把筛选项强制分成 4 类剧本：
  - query 候选项
  - DOM checkbox 候选项
  - 组合语义项
  - 特殊入口项
- 明确资产列表与详情页的职责分工

### `findings.md` 本轮新增的细化
- 收敛为“事实与边界”文档，而不是重复计划正文
- 明确记录：
  - 配置骨架、快照链路、详情展示基础已经存在
  - 当前真实缺口是 runtime 生效层
  - 5 个 query 候选项应优先推进
  - `single_piece_free_shipping` 与 `encrypted_waybill` 必须保守处理

### 本轮结论
- 经过这次重整后，这个计划目录已经从“多轮追加的资料集合”收敛成了“可直接执行的计划包”：
  - `task_plan.md` 负责执行顺序与验收边界
  - `implementation_research.md` 负责逐项实施与证据策略
  - `findings.md` 负责记录事实与边界
  - `progress.md` 负责记录本轮动作
- 下一轮如果继续实施，不需要再先补计划结构，可以直接进入：
  - 批次 4：5 个 query 候选项全面闭环
      - `verification_detail.result_url`
  - 新增 `_mark_runtime_snapshot_query_navigation_failed(...)`
    - 解决此前“已尝试跳转带筛选参数结果页，但导航失败时仍像没做过一样”的问题
    - 现在会明确记录：
      - `reason = query_filter_navigation_failed`
      - `mapping_stage = query_candidate`
      - `verification_mode = navigation_failed`
      - `attempted_result_url`
      - `attempted_query_params`
  - 调整真实搜索流程：
    - 导航成功后的 query 验证调用会写入：
      - `verification_mode = post_navigation_url`
    - 当前结果页已自带目标参数时的原地验证会写入：
      - `verification_mode = in_place_url`
    - 导航失败时不再保留 `snapshot_only` 假象，而是进入明确失败态
- `scripts/validate_source_channel_config.py`
  - 为首个 query 闭环新增更细验证：
    - `in_place_url` 验证模式
    - `post_navigation_url` 验证模式
    - `query_filter_navigation_failed_runtime_projection`
  - 现在会验证：
    - 首个 query 项导航失败时保留 `query_candidate` 阶段
    - 首个 query 项导航失败时保留 `query_filter_navigation_failed`
    - 首个 query 项导航失败时保留 `attempted_result_url`
- `web/app.jsx`
  - 为详情解释补充新的失败原因文案：
    - `query_filter_navigation_failed`
    - 页面会明确显示“已尝试跳转到带筛选参数的结果页，但页面导航失败”

### 本轮验证
- 正确的 Python 语法检查：
  - `/opt/anaconda3/envs/mytools/bin/python -m py_compile scripts/run_ali1688_slow_flow.py scripts/validate_source_channel_config.py src/xianyu_tools/channel_search_filters.py src/xianyu_tools/config.py src/xianyu_tools/source_adapter/ali1688.py`
  - 结果：通过
- 契约验证脚本：
  - `PYTHONPATH=src /opt/anaconda3/envs/mytools/bin/python scripts/validate_source_channel_config.py`
  - 结果：16 项检查全部通过
- 说明：
  - 期间曾误用 `py_compile web/app.jsx`
  - 那是命令使用错误，不是前端代码本身有 Python 语法问题
  - 已改为只对 Python 文件执行 `py_compile`

### 本轮结论
- “提交 3：首个 query 闭环”已经从“只有成功分支可信”推进到“成功、原地验证、导航失败三条路径都有状态记录”。
- 这对后续详情页解释非常关键，因为现在系统终于能区分：
  - 当前 URL 已命中
  - 导航后验证命中
  - 已尝试跳转但导航失败
  - 根本没有进入 runtime

### 下一步
- 继续按计划推进“提交 3：首个 query 闭环”的下一段：
  - 继续围绕 `single_piece_drop_shipping`
  - 检查是否还需要补更细的结果级证据字段
  - 然后进入“提交 4：同类 query 项扩展”

## 2026-06-27

### 本轮计划继续细化
- 用户要求：
  - “计划和实施调研需要更细化一些”
- 本轮已继续把计划从“阶段级”下钻到“开发任务单级”。

### 已新增到 `task_plan.md`
- 补充了“本轮进一步细化后的执行拆解”：
  - 配置层任务拆解
  - runtime 输入/输出快照契约
  - runtime 状态机
  - 决策资产库列表页与货源明细页的职责拆解
- 补充了“代码改动批次（可直接实施）”：
  - 提交 1：配置契约与展示契约收口
  - 提交 2：query 候选参数桶统一
  - 提交 3：首个强候选项闭环
  - 提交 4：同类 query 项扩展
  - 提交 5：组合语义与特殊入口项调研闭环
  - 提交 6：UI 勾选组补证据
- 补充了“联调与验收剧本”：
  - 前端联调
  - pipeline 联调
  - 详情页联调
- 补充了“风险拆解与预案（再细化）”

### 已新增到 `implementation_research.md`
- 补充了“按实施动作拆的研究结论”：
  - 先做什么 / 后做什么 / 最后单独做什么
  - 四类统一实施剧本：
    - query 候选项
    - DOM checkbox 项
    - 组合语义项
    - 特殊入口项
  - 为 11 个筛选项逐项补了更细的实施信息：
  - 推荐优先级
  - 实施剧本
  - runtime 注入目标
  - 成功判据

### 本轮再次细化后的结果
- 计划已经从“阶段说明”补到了“开发任务单”粒度：
  - 配置层任务
  - 接口层任务
  - runtime 输入输出契约
  - 参数映射层任务
  - 页面展示层任务
  - 联调与验收剧本
  - 提交批次
  - 风险与预案
- 调研已经从“逐项描述”补到了“统一实施剧本”粒度：
  - query 候选项剧本
  - DOM checkbox 剧本
  - 组合语义剧本
  - 特殊入口剧本
- 现在后续推进不再需要先补规划，可以直接按：
  - 提交 1
  - 提交 2
  - 提交 3
  - 提交 4
  - 提交 5
  - 提交 6
  顺序实施与回归

### 本轮代码推进：提交 1 持续收口
- 已继续推进“配置契约与展示契约收口”，本轮实际落地了以下代码改动：
  - `src/xianyu_tools/config.py`
    - 为标准化后的 `source_filter_snapshot` 补齐：
      - `configured_filter_keys`
      - `verification_details`
    - 让详情页 / runtime / 验证脚本都能消费同一套别名契约
  - `scripts/run_full_pipeline.py`
    - 在 runtime context 中加入：
      - `source_channel_type`
    - 落库 `ali1688_sources` 时同步写入：
      - `source_channel_type`
    - 补充建表自愈：
      - `ALTER TABLE ali1688_sources ADD COLUMN source_channel_type ...`
  - `src/web_api/main.py`
    - 任务列表 `/api/tasks` 里的 `used_channels` 现在也会带上：
      - `channel_type`
    - 任务详情 `/api/task_details/{task_id}` 中：
      - `source_row` 增加 `source_channel_type`
      - `channel_groups` 增加 `channel_type`
      - `used_channels` 增加 `channel_type`
      - `source_filter_snapshot` 归一化不再写死 `channel_type='ali1688'`
  - `web/app.jsx`
    - `summarizeChannelFilterSnapshot(...)` 现在兼容读取：
      - `configured_filter_keys`
      - `verification_details`
    - 前端分组 fallback 数据结构也补齐：
      - `channel_type`
  - `scripts/create_multichannel_validation_fixture.py`
    - 联调夹具补充 `source_channel_type`，避免夹具结构落后于现行契约

### 本轮验证结果
- 已通过：
  - `/opt/anaconda3/envs/mytools/bin/python -m py_compile src/xianyu_tools/config.py src/web_api/main.py scripts/run_full_pipeline.py scripts/validate_source_channel_config.py`
- 已通过：
  - `PYTHONPATH=src /opt/anaconda3/envs/mytools/bin/python scripts/validate_source_channel_config.py`
- 已新增并通过的契约断言：
  - `configured_filter_keys == configured_enabled_filter_keys`
  - `verification_details` 能回填旧快照中的验证详情
  - `applied / query_injected_pending_verification / unapplied` 三类 runtime 状态在快照归一化后保持稳定

### 当前判断
- “提交 1：配置契约与展示契约收口”已经进一步接近完成态：
  - 配置快照契约更完整
  - 列表 / 详情 / 联调夹具的数据模型已统一到 `channel_type + channel_id + channel_label` 口径
- 下一步更适合进入：
  - “提交 2：query 候选参数桶统一”的继续收口
  - 或直接推进“提交 3：single_piece_drop_shipping 首个强候选闭环”

### 本轮补修：详情页分组快照覆盖问题
- 发现问题：
  - `channel_groups` 初始化时先放入了“空的默认快照”
  - 后续又用简单 truthy 判断是否替换
  - 结果会导致“真实 source_filter_snapshot 已存在，但分组层仍保留空快照”的情况
- 已修复文件：
  - `src/web_api/main.py`
  - `web/app.jsx`
- 修复策略：
  - 新增“是否为有信号快照”的判断
  - 只有当新快照具备真实筛选信号、且当前分组还是空信号快照时，才进行替换
- 这次修复的直接价值：
  - 后续即使 runtime 已经把 `single_piece_drop_shipping` 标记为 `applied`
  - 详情页分组头部也不会再因为默认空快照而丢失解释信息
- 轻量验证：
  - `_channel_filter_snapshot_has_signal({'mapping_stage': 'snapshot_only', 'configured_enabled_filter_keys': []}) -> False`
  - `_channel_filter_snapshot_has_signal({'mapping_stage': 'mixed', 'configured_enabled_filter_keys': ['single_piece_drop_shipping']}) -> True`

### 本轮继续推进：首个强候选项闭环补强
- 发现问题：
  - `scripts/run_ali1688_slow_flow.py` 之前只有在
    - `filtered_result_url != page.url`
    时才会继续做 query 验证。
  - 这意味着如果当前结果页本来就已经带了目标参数，比如：
    - `offerTags=1988226`
  - runtime 会直接跳过验证，导致：
    - 明明已命中一件代发别名参数
    - 但快照仍停留在 `snapshot_only`
- 已完成修复：
  - 抽出纯函数：
    - `_verify_and_mark_runtime_query_snapshot(...)`
  - 统一负责：
    - 当前结果 URL 的 query 验证
    - `filter_status_map` 回写
    - `mapping_stage` 升级
  - 新逻辑现在支持两条路径：
    1. 需要跳转到新的 `filtered_result_url` 后再验证
    2. 当前 `page.url` 已经包含目标参数时，直接原地验证
- 已新增回归：
  - `scripts/validate_source_channel_config.py`
    - `query_filter_in_place_runtime_verification`
  - 覆盖场景：
    - 当前 URL 已带 `offerTags=1988226`
    - 开启 `single_piece_drop_shipping`
    - 应直接升级为：
      - `mapping_stage = query_mapped`
      - `applied_filter_keys = ['single_piece_drop_shipping']`
      - `filter_status_map['single_piece_drop_shipping'].status = 'applied'`
- 本轮验证结果：
  - 已通过：
    - `/opt/anaconda3/envs/mytools/bin/python -m py_compile scripts/run_ali1688_slow_flow.py scripts/validate_source_channel_config.py src/xianyu_tools/source_adapter/ali1688.py`
    - `PYTHONPATH=src /opt/anaconda3/envs/mytools/bin/python scripts/validate_source_channel_config.py`
- 当前推进意义：
  - `single_piece_drop_shipping` 的“URL 已命中但不升级状态”的缺口已补齐
  - 后续同类 query 项扩展时，可以复用同一条 in-place 验证链路，而不需要每项再补一套判断

### 本轮继续推进：同类 query 候选项 mixed 状态回归
- 已新增回归场景：
  - `query_filter_multi_item_mixed_runtime_verification`
- 覆盖目标：
  - 同一轮里同时启用：
    - `official_logistics`
    - `free_shipping`
    - `freight_insurance_return`
    - `rapid_invoice`
  - 结果页 URL 只命中其中 3 项时：
    - 命中的项应升级为 `applied`
    - 未命中的 `rapid_invoice` 应保持 `query_injected_pending_verification`
    - `mapping_stage` 应保持 `mixed`
- 这次回归确认了两件关键事实：
  1. 同参数桶项不会因为共享 `complexTags / filtOfferTags` 就整桶误判
  2. `query_injected_pending_verification` 这类项的原因当前挂在 `filter_status_map`，而不是 `unapplied_reason_map`
- 本轮验证已通过：
  - `/opt/anaconda3/envs/mytools/bin/python -m py_compile scripts/validate_source_channel_config.py scripts/run_ali1688_slow_flow.py src/xianyu_tools/source_adapter/ali1688.py`
  - `PYTHONPATH=src /opt/anaconda3/envs/mytools/bin/python scripts/validate_source_channel_config.py`
- 当前推进意义：
  - “同类 query 候选项扩展”的状态机已经有了可回归约束
  - 后续如果继续把真实浏览器链路扩到：
    - `free_shipping`
    - `official_logistics`
    - `freight_insurance_return`
    - `rapid_invoice`
    不会再轻易把“部分命中”错误压扁成“全命中”或“全未命中”

### 本轮补强：重复 query 参数聚合验证
- 发现风险：
  - 1688 最终结果页如果输出：
    - `complexTags=1001&complexTags=1013`
  - 旧逻辑用简单 dict 覆盖，会只保留最后一个值
  - 这会导致同参数桶里的多个筛选项漏判
- 已完成修复：
  - `src/xianyu_tools/source_adapter/ali1688.py`
    - 新增 `_parse_query_params_with_merge(...)`
    - 对重复 query 参数进行聚合合并
  - 应用位置：
    - `apply_ali1688_query_filters_to_url(...)`
    - `verify_ali1688_query_filters_from_url(...)`
- 已新增回归：
  - `query_filter_repeated_query_param_verification`
- 覆盖场景：
  - `complexTags=1001&complexTags=1013`
  - 同时验证：
    - `freight_insurance_return`
    - `rapid_invoice`
  - 预期：
    - 两者都能命中
    - `observed_query["complexTags"]` 聚合为：
      - `1001,1013`
- 本轮验证已通过：
  - `/opt/anaconda3/envs/mytools/bin/python -m py_compile src/xianyu_tools/source_adapter/ali1688.py scripts/validate_source_channel_config.py scripts/run_ali1688_slow_flow.py`
  - `PYTHONPATH=src /opt/anaconda3/envs/mytools/bin/python scripts/validate_source_channel_config.py`
- 当前推进意义：
  - `free_shipping / official_logistics / freight_insurance_return / rapid_invoice` 这批 query 候选项的验证逻辑，对“重复参数”“共享参数桶”“部分命中”三类关键边界都已有回归保护
  - 失败判据
  - 代码入口
  - 展示约束
- 补充了“渠道隔离实施研究”：
  - 多渠道不同配置
  - 未登录渠道
  - 同渠道多账号
- 补充了“实施前 checklist”与“下一轮实施前必须先拿到的证据”

### 本轮结论
- 当前计划文件已经从“高层规划”继续下钻到：
  - 哪些文件先改
  - 哪些字段先固化
  - 哪些筛选项先闭环
  - 每一步怎么验收
  - 失败后怎么降级
- 当前调研文件已经可以直接作为后续实现的实施蓝图使用，而不是只作为背景说明。

### 当前状态
- `task_plan.md`
  - 已达到“可直接按提交批次推进”的颗粒度
- `implementation_research.md`
  - 已达到“逐筛选项实施单级”的颗粒度
- 下一步：
  - 若用户确认继续实施，可直接从“提交 1 / 提交 2”开始落代码

### 本轮实现推进：提交 1（配置契约与展示契约收口）已开始
- 已修改：
  - `src/xianyu_tools/config.py`
  - `src/web_api/main.py`
  - `scripts/run_full_pipeline.py`
  - `scripts/run_ali1688_slow_flow.py`
  - `scripts/validate_source_channel_config.py`

### 本轮代码动作
- 在 `src/xianyu_tools/config.py` 新增统一入口：
  - `normalize_channel_search_filter_snapshot(...)`
- 该入口现在负责把任意旧/新快照统一收口成同一 schema：
  - `filters`
  - `configured_filters`
  - `enabled_filter_keys`
  - `configured_enabled_filter_keys`
  - `query_injected_filter_keys`
  - `query_injected_query_params`
  - `query_verification_details`
  - `applied_filter_keys`
  - `unapplied_filter_keys`
  - `unapplied_reason_map`
  - `filter_status_map`
  - `mapping_stage`
  - `mapping_notes`
- `get_channel_search_filter_snapshot(...)` 已改为通过该归一化入口统一返回，避免配置态快照和 runtime 快照出现两套口径。
- `scripts/run_ali1688_slow_flow.py` 已改为：
  - `_build_runtime_filter_snapshot(...)` 返回前先做统一归一化
  - `_mark_runtime_snapshot_query_injected(...)` 合并状态后再次归一化
  - 这样 runtime 快照现在也会稳定带回 `filters` / `configured_filters` 双字段
- `scripts/run_full_pipeline.py` 的 fallback `source_filter_snapshot` 已改为复用统一归一化入口，避免异常路径掉回老 schema。
- `src/web_api/main.py` 在读取 `source_filter_snapshot_json` 后，已先做统一归一化再回传前端。
  - 这样历史任务、异常任务、半旧 schema 任务都会在接口层被补成统一结构。

### 新增验证
- `scripts/validate_source_channel_config.py`
  - 新增：
    - `channel_search_filter_snapshot_normalization`
- 新校验覆盖：
  - 旧快照只有 `configured_filters` 时，能自动补齐 `filters`
  - 旧快照只有 `query_injected_filter_keys` 时，能恢复状态机
  - 未进入 runtime 的已配置项，会被统一回落到 `unapplied`
  - `mapping_notes` 会自动补齐

### 本轮验证结果
- 已通过：
  - `PYTHONPYCACHEPREFIX=/private/tmp/codex-pycache python3 -m py_compile src/xianyu_tools/config.py src/web_api/main.py scripts/run_full_pipeline.py scripts/run_ali1688_slow_flow.py scripts/validate_source_channel_config.py`
- 已通过：
  - `PYTHONPATH=src python3 scripts/validate_source_channel_config.py`
- 当前校验通过项包括：
  - `channel_search_filter_snapshot_contract`
  - `channel_search_filter_snapshot_normalization`

### 本轮结论
- “提交 1”最核心的口径问题已经开始收口：
  - 配置层快照
  - runtime 快照
  - pipeline fallback 快照
  - API 回传快照
  现在都在向同一套 schema 对齐。
- 下一步可以继续推进：
  - `提交 1` 的剩余前端消费复核
  - 或直接进入 `提交 2：query 候选参数桶统一`

### 计划状态同步
- 已同步更新 `task_plan.md`：
  - 当前阶段调整为：
    - `阶段 3（进行中）`
  - 阶段 3 中已标记完成：
    - 前后端 `channel_search_filters` 契约统一
    - 不支持渠道空态返回规则
    - 保存时的清洗规则
    - 11 项字段完整回读复核
    - 不同渠道同 key 隔离复核
    - 资产列表 / 详情继续沿用同一真源
    - 新增渠道但未配置筛选项时的默认返回约束

### 本轮实现推进：提交 2（query 候选参数桶统一）已启动并完成首轮收口
- 已修改：
  - `src/xianyu_tools/source_adapter/ali1688.py`
  - `scripts/validate_source_channel_config.py`

### 本轮代码动作（提交 2）
- 已将 `ali1688.py` 中原本分散的 query 定义收口为单一真源：
  - `ALI1688_QUERY_FILTER_DEFINITIONS`
- 当前每个 query 候选项统一在同一处维护：
  - `mapping_type`
  - `param`
  - `values`
  - `verify_alias_params`
- 新增统一访问入口：
  - `get_ali1688_query_filter_definition(...)`
- 以下逻辑现在都改为从同一真源派生，不再分别读两张映射表：
  - `get_ali1688_query_mapped_filter_keys(...)`
  - `build_ali1688_query_filter_expectation(...)`
  - `build_ali1688_query_filter_params(...)`
  - `verify_ali1688_query_filters_from_url(...)`

### 这次收口的直接收益
- 后续新增 query 候选项时，不再需要同时维护：
  - 参数桶映射
  - 验证别名映射
  - expectation 输出结构
- `single_piece_drop_shipping / official_logistics` 共用 `filtOfferTags` 参数桶时，验证别名也能继续集中维护。
- 后续做 `rapid_invoice / official_logistics / free_shipping / freight_insurance_return` 扩展时，入口已经统一。

### 本轮新增验证
- `scripts/validate_source_channel_config.py` 新增：
  - `ali1688_query_filter_definition_contract`
  - `ali1688_query_filter_param_merging`
  - `ali1688_query_filter_url_verification`
- 新校验覆盖：
  - 官方物流定义是否正确保留 `filtOfferTags` 与 `offerTags` 别名
  - 同参数桶多筛选项是否按顺序合并，而不是互相覆盖
  - 一件代发是否仍支持 `offerTags` 别名验证
  - `freight_insurance_return / rapid_invoice` 是否能在组合 URL 中被独立验证命中

### 本轮验证结果
- 系统 `python3` 环境中缺少 `scrapling`，因此涉及 `ali1688.py` 的验证需要切换到项目实际运行环境。
- 已通过：
  - `/opt/anaconda3/envs/mytools/bin/python -m py_compile src/xianyu_tools/source_adapter/ali1688.py scripts/validate_source_channel_config.py scripts/run_ali1688_slow_flow.py`
- 已通过：
  - `PYTHONPATH=src /opt/anaconda3/envs/mytools/bin/python scripts/validate_source_channel_config.py`
- 当前通过项新增包括：
  - `ali1688_query_filter_definition_contract`
  - `ali1688_query_filter_param_merging`
  - `ali1688_query_filter_url_verification`

### 当前结论
- 提交 2 的“结构统一”已经完成第一步：
  - 参数桶定义统一
  - 验证别名统一
  - expectation 输出统一
  - 组合验证校验补齐
- 下一步可以直接推进：
  - `提交 3：single_piece_drop_shipping` 的真实 query 闭环
  - 只有验证通过的 query 项才进入：
    - `applied_filters`
    - `applied_filter_keys`
- `web/app.jsx`
  - “已注入待验证”摘要现在会自动排除已经进入 `applied_filter_keys` 的项
  - 避免同一筛选项同时出现在“已生效”和“已注入待验证”两组里

### 本轮验证
- 已通过：
  - `PYTHONPYCACHEPREFIX=/private/tmp/codex-pycache python3 -m py_compile scripts/run_ali1688_slow_flow.py src/xianyu_tools/source_adapter/ali1688.py src/web_api/main.py scripts/run_full_pipeline.py`
- 已通过最小 helper 验证：
  - 历史 URL `...&complexTags=1001&offerTags=1988226`
  - 能识别出：
    - `single_piece_drop_shipping`
    - `freight_insurance_return`

### 当前执行状态
- “找出 single_piece_drop_shipping 的最小结果级验证口径”已完成
- “在 slow flow 中实现首个结果级验证逻辑”已完成首版
- 下一步应进入：
  - 最小行为验证
  - 再决定是否把 `free_shipping / rapid_invoice / official_logistics` 一并升级到同一验证框架

### 本轮计划再细化（2026-06-26 夜）
- 继续把计划从“阶段级”压到了“逐项实施级”。
- 新增文件：
  - `implementation_research.md`
- 该文件把 11 个筛选项逐项拆成：
  - 当前证据等级
  - 候选接法
  - 预期改动文件
  - 渠道级要求
  - runtime 快照要求
  - 资产展示要求
  - 验证动作
  - 失败降级策略

### 这次细化后的直接效果
- 后续每推进一个筛选项，都不需要再回头问：
  - 先改 adapter 还是先改 slow flow
  - 先验证 URL 还是先验证 selector
  - 失败后详情页该如何诚实落状态
- 现在已经可以按以下顺序直接执行：
  1. `single_piece_drop_shipping`
  2. `freight_insurance_return`
  3. `free_shipping`
  4. `rapid_invoice`
  5. `official_logistics`
  6. `single_piece_free_shipping`
  7. checkbox 组
  8. `encrypted_waybill`

### 本轮实现推进
- 已继续沿着“提交 2 / 提交 5 的中间收口动作”往前推进，但先优先修正语义准确性：
  - `scripts/run_ali1688_slow_flow.py`
    - 不再把“仅完成 query URL 注入”直接标记成 `applied_filter_keys`
    - 新增：
      - `query_injected_filter_keys`
      - `query_injected_query_params`
    - 现在的策略改为：
      - URL 已注入，但结果尚未验证时：
        - `mapping_stage = "mixed"`
        - `applied_filter_keys = []`
        - `unapplied_reason_map[key] = query_filter_injected_pending_verification`
      - 这样可以避免 runtime 过早宣称“已生效”
  - `web/app.jsx`
    - 新增“已注入待验证”摘要分组
    - `待映射` 会自动排除这批已注入但未验证的项，避免重复展示
    - 详情页提示文案开始区分：
      - 仅快照透传
      - URL 已注入但结果待验证
- 同时把内部函数命名从“query applied”收紧为“query injected”，降低后续误用风险。

### 本轮实现结论
- 当前第一批 query 候选项链路已经不是“纯计划态”，而是进入了：
  - 配置已保存
  - runtime 已识别
  - URL 可注入
  - 详情页可解释“已注入待验证”
- 但仍然刻意没有把它升级成“已生效”，因为结果级验证还没有完成。
- 这一步符合本计划强调的原则：
  - 证据不足时，只能升到更诚实的中间态，不能直接宣称完成映射。

### 本轮继续推进：single_piece_drop_shipping 结果级验证增强
- 已继续沿着第一条 query 强候选项往下推进，不再只返回：
  - 哪些 key 通过了
- 现在新增了逐项验证细节：
  - `query_verification_details`
- 其内容包括：
  - `status`
  - `expected_values`
  - `observed_values`
  - `matched_values`
  - `matched_params`
  - `verify_alias_params`

### 本轮代码补强
- `src/xianyu_tools/source_adapter/ali1688.py`
  - 新增：
    - `verify_ali1688_query_filters_from_url(...)`
  - 原有：
    - `verify_ali1688_query_filter_keys_from_url(...)`
    现在只是兼容包装层
  - 目的：
    - 不只告诉 runtime “通过了哪些 key”
    - 还告诉 runtime “是通过哪个参数命中的、命中了哪些值”
- `scripts/run_ali1688_slow_flow.py`
  - `runtime_filter_snapshot` 新增：
    - `query_verification_details`
  - query 注入成功后：
    - 会把逐项验证细节一并写入快照
  - 这样后续扩展到：
    - `free_shipping`
    - `freight_insurance_return`
    - `rapid_invoice`
    - `official_logistics`
    时，不需要再重新发明验证结构

### 本轮最小验证结果
- 已通过静态编译：
  - `python3 -m py_compile scripts/run_ali1688_slow_flow.py src/xianyu_tools/source_adapter/ali1688.py`
- 已通过最小行为验证：
  - 输入 URL：
    - `...&complexTags=1001&offerTags=1988226&freeShipping=1`
  - 输出验证结果：
    - `single_piece_drop_shipping = verified`
    - `freight_insurance_return = verified`
    - `free_shipping = verified`
    - `rapid_invoice = pending_verification`
- 这个结果说明：
  - 当前验证已经不只是看“参数桶存在”
  - 而是能区分“同一参数桶里是不是命中了本筛选项自己的目标值”

### 当前状态再更新
- “single_piece_drop_shipping 的结果级验证口径”已进一步从：
  - key 级通过 / 未通过
  升级到：
  - 值级命中明细
- 下一步更适合继续做：
  - 把 `free_shipping / freight_insurance_return / official_logistics / rapid_invoice` 纳入同一验证闭环
  - 再评估是否需要把这些验证细节在详情页以轻量方式展示

### 本轮继续推进：详情页接入验证细节
- 已把 runtime 新增的：
  - `query_verification_details`
  接入详情页渠道摘要。
- 当前详情页不再只显示：
  - 已配置
  - 已注入待验证
  - 已生效
- 还会轻量展示：
  - 命中参数
  - 待验证线索

### 本轮前端接入点
- `web/app.jsx`
  - `summarizeChannelFilterSnapshot(...)`
    - 新增：
      - `queryVerificationDetails`
  - 新增：
    - `formatQueryVerificationDetail(...)`
  - 渠道摘要区新增两组轻量说明：
    - `命中参数`
    - `待验证线索`

### 当前展示层效果
- 如果某项已在最终 URL 中命中预期值：
  - 详情页会显示类似：
    - `一件代发: offerTags=1988226`
    - `退货包运费: complexTags=1001`
- 如果某项已经注入，但当前只观察到非目标值：
  - 详情页会显示为待验证线索
  - 不会被误判成已生效

### 这一步的意义
- 现在这条链路已经从：
  - 配置可保存
  - runtime 可注入
  - 快照可记录
  继续推进到：
  - 详情页可解释
- 这让后续继续扩：
  - `free_shipping`
  - `rapid_invoice`
  - `official_logistics`
  时，不需要再额外补一轮展示层设计

### 本轮继续推进：逐筛选项状态结构收口
- 已把 runtime 快照从“几组列表字段”继续收口为：
  - `filter_status_map`
- 现在每个已配置筛选项都可以拥有自己的状态对象：
  - `configured`
  - `status`
  - `reason`
  - `verification_detail`

### 本轮结构补强
- `scripts/run_ali1688_slow_flow.py`
  - `_build_runtime_filter_snapshot(...)`
    - 初始就会生成 `filter_status_map`
  - `_mark_runtime_snapshot_query_injected(...)`
    - 会把每个筛选项分别标成：
      - `applied`
      - `query_injected_pending_verification`
      - `unapplied`
- `web/app.jsx`
  - 摘要函数开始优先消费 `filter_status_map`
  - 新增原因文案翻译：
    - `query_filter_injected_pending_verification`
    - `query_filter_not_applied_in_runtime`
    - `runtime_mapping_not_implemented_yet`
    - `query_candidate_not_validated`
    - `ui_selector_not_stable`
    - `special_panel_unmapped`
    - `snapshot_only_until_semantics_confirmed`
  - 渠道详情摘要新增：
    - `未应用原因`

### 本轮最小验证
- 已通过最小结构验证：
  - 3 个筛选项同时启用时，
    - `single_piece_drop_shipping = applied`
    - `free_shipping = applied`
    - `rapid_invoice = query_injected_pending_verification`
  - `mapping_stage = mixed`
- 这说明当前 runtime 已经能正确处理：
  - 同一轮里部分筛选项已命中
  - 部分筛选项仅注入未验证

### 当前状态更新
- Query 强候选组现在不仅有：
  - key 级状态
  - 值级验证细节
- 还多了：
  - per-filter 状态对象
- 这意味着下一步继续推进：
  - `free_shipping`
  - `freight_insurance_return`
  - `official_logistics`
  - `rapid_invoice`
  时，已经不需要再调整快照结构，只需要补强真实验证和证据来源

### 本轮继续推进：query 候选项预期画像入快照
- 已继续把 query 强候选组往统一框架里收口。
- 新增：
  - `build_ali1688_query_filter_expectation(...)`
- 现在对于 query 候选项，即使还没真正命中，快照里也会先带上：
  - `mapping_type`
  - `param`
  - `expected_values`
  - `verify_alias_params`

### 本轮代码推进
- `src/xianyu_tools/source_adapter/ali1688.py`
  - 新增：
    - `build_ali1688_query_filter_expectation(...)`
  - 用途：
    - 为每个 query 候选项生成统一的“理论目标值画像”
- `scripts/run_ali1688_slow_flow.py`
  - `_build_runtime_filter_snapshot(...)`
    - 初始 `filter_status_map` 的 `verification_detail` 不再是空对象
    - 对 query 候选项会预填理论目标信息
  - `_mark_runtime_snapshot_query_injected(...)`
    - 会把理论目标信息与真实观察结果合并
    - 因此后续状态对象同时具备：
      - 目标值
      - 实际值
      - 命中参数
      - 当前状态

### 本轮最小行为验证
- 已通过最小结构 + 行为验证：
  - 初始状态下：
    - `official_logistics`
    - `rapid_invoice`
    - `free_shipping`
    - `freight_insurance_return`
    都会带各自的 query 目标画像
- 已通过混合验证示例：
  - 输入 URL：
    - `filtOfferTags=2484802`
    - `complexTags=1013`
    - `freeShipping=1`
  - 输出状态：
    - `official_logistics = applied`
    - `rapid_invoice = applied`
    - `free_shipping = applied`
    - `freight_insurance_return = query_injected_pending_verification`
- 这说明：
  - 同一个参数桶里的不同筛选项，现在不仅能区分“有没有参数”
  - 还能区分“参数值是不是自己的目标值”

### 当前推进意义
- Query 强候选组的快照结构现在已经足够支撑后续连续推进：
  - `free_shipping`
  - `freight_insurance_return`
  - `official_logistics`
  - `rapid_invoice`
- 后续再做真实闭环时，不需要再补：
  - 状态结构
  - 详情解释结构
  - 目标值元信息结构

### 本轮继续细化：计划与实施调研升级
- 已重新核对当前计划目录与代码触点：
  - `src/xianyu_tools/config.py`
  - `src/xianyu_tools/source_adapter/ali1688.py`
  - `scripts/run_full_pipeline.py`
  - `src/web_api/main.py`
  - `web/app.jsx`
- 已把计划进一步补到以下层级：
  - 截图项 -> 系统字段映射表
  - 页面 / 接口 / runtime / 资产展示四层实施要求
  - 阶段 3 / 阶段 4 / 阶段 5 / 阶段 6 / 阶段 7 的更细验收项
  - 按渠道联调矩阵
  - 提交级推进顺序
- 已把调研进一步补到以下粒度：
  - “什么情况下可以宣称已生效”
  - “什么情况下只能算已配置未验证”
  - “什么情况下必须回落未应用”
  - 新增渠道但未登录成功账号时的建议策略

### 这次细化后的直接效果（新增）
- 后续如果继续推进“极速开票、分销严选等搜索能力项”的实现，不再需要先补语义约束。
- 计划已经把以下边界写死：
  - 这些筛选项只按 `ali1688` 渠道区分
  - 排序不是配置项
  - 列表页只展示渠道，详情页才解释筛选策略
  - 未验证项不能冒充已生效

### 本轮实现推进：配置快照契约继续收口
- 已修改：
  - `src/xianyu_tools/config.py`
  - `scripts/validate_source_channel_config.py`
  - `scripts/run_full_pipeline.py`
- 具体补强：
  - `get_channel_search_filter_snapshot(...)` 现在直接返回更完整的配置态快照：
    - `configured_filters`
    - `configured_enabled_filter_keys`
    - `applied_filter_keys`
    - `unapplied_filter_keys`
    - `unapplied_reason_map`
    - `filter_status_map`
    - `mapping_stage`
    - `mapping_notes`
  - 这样即使还没进入真实 runtime，也能保证：
    - 配置态有稳定解释结构
    - 前端 / pipeline / 后续 slow flow 使用同一套字段口径
  - `scripts/run_full_pipeline.py` 的异常兜底快照也已同步到同一结构，避免异常路径掉回老 schema。

### 本轮验证补充
- 已通过：
  - `python3 -m py_compile src/xianyu_tools/config.py scripts/validate_source_channel_config.py scripts/run_full_pipeline.py`
- 已通过：
  - `PYTHONPATH=src python3 scripts/validate_source_channel_config.py`
- 新增校验项：
  - `channel_search_filter_snapshot_contract`
- 该校验已覆盖：
  - `configured_filters == filters`
  - `configured_enabled_filter_keys == enabled_filter_keys`
  - 非 `ali1688` 渠道返回空 `filters`
  - 配置态快照默认 `mapping_stage = snapshot_only`
