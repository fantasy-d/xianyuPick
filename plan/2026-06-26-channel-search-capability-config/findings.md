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
5. `encrypted_waybill` 当前已经不只是一个泛化的“未映射项”：
   - 当结果页文本命中 `密文面单` 时，应该保留更细的中间证据：
     - 证据来源：`result_page_text`
     - 入口线索类型：`text_term`
     - 下一步动作：`panel_open_and_toggle`
   - 这能明确区分“完全没线索”与“入口已观测但动作未接通”。

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

## 8. 本轮补充发现（2026-06-28）

### 8.1 11 个顶部筛选项的定义真源已经稳定存在

当前从 `src/xianyu_tools/channel_search_filters.py` 可以直接确认：

1. 11 个顶部筛选项已经全部沉到统一定义表
2. 每个项至少已有一类真实元信息：
   - `query_param / query_values`
   - `probe_terms`
   - `verification_entry`
   - `semantic_dependencies`
   - `observation_scope`
3. 后续不应该再在：
   - 前端 JSX
   - API 拼装层
   - 独立脚本
   手写第二套“项定义真源”

结论：

- 这次工作的重点不是“再创建配置 schema”
- 而是把现有定义真源继续贯通到：
  - 渠道级保存
  - runtime 动作
  - 快照回流
  - 资产详情解释

### 8.2 顶部筛选项必须继续保持“渠道级”，不能退回账号级

当前最容易被后续实现破坏的点，是把顶部筛选项错误地绑到具体账号上。

需要持续坚持：

1. 顶部筛选项表达的是：
   - “这个渠道在抓取时希望尝试哪些筛选能力”
2. 账号池表达的是：
   - “这个渠道当前有哪些登录账号可用”
3. 账号是否可用会影响：
   - 能否执行真实动作
4. 但账号是否可用不应改变：
   - 渠道本身保存了哪些顶部筛选配置

结论：

- 详情页后续要能同时解释：
  - 渠道配置了什么
  - 渠道本次用了哪个账号
  - 该账号是否让这些筛选配置真实进入 runtime

### 8.3 决策资产库必须允许同一筛选项在不同渠道上得出不同结论

当前计划已经明确：

1. 列表页只轻量展示：
   - `used_channels`
2. 详情页才逐渠道解释：
   - 顶部筛选项配置态
   - 已生效项
   - 未应用项
   - 已配置未验证项

新增结论：

- 只要是同一任务多渠道并存，就必须允许两个渠道对同一个顶部筛选项得出不同结论
- 例如：
  - `1688 货源渠道` 的 `rapid_invoice = applied`
  - `义乌渠道` 的 `rapid_invoice = query_injected_pending_verification`
- 前端不能再压成一个全局结论

### 8.4 渠道筛选摘要解释必须以接口契约为准，snapshot 推断只能做兜底

本轮继续核对后发现，批次 7 最容易继续漂移的点，不是排序或分组，而是：

1. 后端已经返回了 `filter_summary`
2. 但前端一旦还要回头读取 `source_filter_snapshot`
3. 就很容易再次在 JSX 里复制第二套状态解释逻辑

因此这轮形成了一个更明确的约束：

1. `/api/tasks` 与 `/api/task_details/{task_id}` 返回的 `filter_summary`
   - 必须直接包含可解释 runtime 明细所需字段
2. 至少要稳定下沉：
   - `filter_status_map`
   - `query_verification_details`
3. 前端只允许：
   - 优先消费接口侧 `filter_summary`
   - 在历史数据或接口缺失时，才退回 `source_filter_snapshot` 做兜底推断

结论：

- 后续如果还要继续细化“待验证线索 / 配置态线索 / 命中参数”文案，应该继续补后端契约和静态校验
- 不应该再把灰区解释逻辑散落回前端 JSX

### 8.5 单条货源卡片也必须直接消费 `source_filter_summary`

继续核对详情页后发现，接口层其实已经为每条货源准备了：

- `sources[*].source_filter_summary`

但如果前端只展示 `channel_groups[*].filter_summary`，用户仍然只能看到“渠道整体结论”，看不到单条货源记录在卡片层被如何分类。

因此这轮再补出一个更细的展示约束：

1. 渠道组头部
   - 负责解释该渠道整体配置、动作证据和灰区状态
2. 单条货源卡片
   - 负责直接展示本条记录对应的筛选摘要分类
3. 单条卡片不需要再复制完整长文案
   - 但至少要直接可见：
     - `已配置未验证`
     - `已注入待验证`
     - `已生效`
     - `未应用`
     - `历史快照缺失 / 当前渠道不支持`

结论：

- 批次 7 的“详情页可直接读懂”不应只停留在 group 级别
- source 卡片也必须真正消费接口侧 `source_filter_summary`

补充结论：

- source 卡片如果只显示“已生效 2 / 未应用 1”这类数量，对用户还是不够直观
- 更好的最小展示单元是：
  - 状态标签
  - 加上对应筛选项名称

也就是至少做到：

- `已生效 -> 包邮 / 官方物流`
- `已注入待验证 -> 极速开票`
- `已配置未验证 -> 1件代发包邮`

这样即使用户不继续读渠道组头部的长解释，也能直接知道这条货源记录和哪些筛选项有关

继续补充：

- source 卡片如果只显示筛选项名称，仍然缺少“为什么是这个状态”的线索
- 在不把卡片撑得过长的前提下，最合适的做法是：
  - 保持卡片正文紧凑
  - 但给每个筛选项 chip 增加悬停线索

这样用户在 source 卡片层就能继续获得：

- verification detail
- reason text
- mapping hint

尤其对批次 5 的灰区状态有帮助，例如：

- `independent_entry_no_result_shift`
- `panel_action_applied_no_result_shift`

结论：

- 批次 7 的可读性增强，不只是“把后端字段接进来”
- 还要让这些字段在 source 卡片层有一个足够轻但可继续展开的读法

### 8.6 利润展示也必须遵循接口优先，而不是前端本地重算

继续核对详情页后发现，还存在一个容易忽略的残留分叉：

1. 渠道组排序已经优先复用接口侧：
   - `estimated_profit`
   - `best_estimated_profit`
2. 但如果单条货源卡片仍在前端直接做：
   - `闲鱼价 - min_price - 20`
3. 那就会形成“排序口径”和“展示口径”来自两套计算源

因此这轮进一步明确：

- source 卡片的利润展示，也必须优先消费接口侧 `estimated_profit`
- 只有接口缺失时，才允许退回旧公式兜底

结论：

- 批次 7 的 API-first 不只包括筛选摘要
- 也包括详情页中的利润展示口径统一

### 8.7 已写入快照的 selector / 面板诊断字段，如果前端不展示，就等于没有真正形成解释链

继续核对批次 5 / 6 后发现，当前 runtime 快照里已经有很多比较关键的诊断字段，例如：

- `selector_resolution_mode`
- `text_fallback_considered`
- `panel_trigger_candidates`
- `panel_visible_via`
- `entry_signal_type`

如果这些字段只停留在 snapshot / validation，而详情页解释层不读取它们，就会出现一个问题：

1. 我们已经有证据
2. 但用户和后续审阅者在 UI 上看不到
3. 证据链就仍然像“未闭环”

因此这轮进一步明确：

- 批次 5 / 6 的诊断字段，一旦已经进入 `verification_detail`
- 就应该尽量在详情解释层被消费出来

结论：

- 证据闭环不只是“字段存在”
- 还包括“字段已经进入可读解释链”

继续补充：

- 只展示“最终命中的 selector”还是不够
- 对批次 6 这种 selector 稳定性本身就是重点的问题，更有价值的是：
  - 系统尝试过哪些候选 selector
  - 最终在哪一步命中

因此 `selector_candidates_tried` 也不应只留在快照或 fixture 校验里。

结论：

- 只要候选定位链路已经写入 `verification_detail`
- 前端解释层就应该尽量把它消费出来
- 这样批次 6 的“稳定 selector 收口”才真正有了可审计证据

继续补充：

- query 类筛选也有类似问题
- 如果前端只展示：
  - `matched_params`
  - `expected_values`
- 但不展示：
  - `verification_mode`
  - `attempted_result_url`

那用户依旧不知道：

1. 这次是原位 URL 校验，还是跳转后 URL 校验
2. 如果失败了，本来是想跳到哪个结果页

结论：

- 批次 5 / 6 的证据消费，不应只覆盖 selector / panel 诊断
- query 类校验路径本身也应该进入前端解释链

### 8.8 `html_text_scan` 的“页面可见 / 入口线索 / 结果页 URL”如果不展示，批次 5 的中间态仍然会像黑盒

继续往下对照 `scripts/validate_source_channel_config.py` 与 `web/app.jsx` 后，发现还有一类字段已经在 runtime / 校验里存在，但前端没真正讲出来：

- `text_visible`
- `entry_signal_detected`
- `result_url`

这些字段看起来小，但对批次 5 的灰区状态尤其关键：

1. `text_visible`
   - 能说明这不是“配置里打开了但页面完全没看到”
   - 而是“页面上确实出现过这段线索”
2. `entry_signal_detected`
   - 能说明 `encrypted_waybill` 不是凭空猜出来的
   - 而是系统已经看到入口线索，只是动作链路还没完全闭环
3. `result_url`
   - 能把“这次证据到底来自哪个 1688 结果页”讲清楚
   - 对区分 query 命中、结果页文本命中、动作前后结果页是否一致都很重要

结论：

- 批次 7 的解释层收口，不应只停留在“有状态标签”
- 只要这些字段已经进了 `verification_detail`
- 前端就应该优先把它们讲出来

### 8.9 DOM 勾选动作不能只保留 `probe_mode`，还需要明确的 `verification_mode`

继续核对批次 5 / 6 的 runtime 证据后发现，普通结果页筛选项点击与组合语义独立入口点击，都会通过真实页面动作进入：

- `probe_mode = dom_toggle_action`
- `verification_mode = dom_toggle_action`

前端如果只认识 `dom_panel_action`，就会让普通 DOM 勾选动作在解释层显得像一段内部状态码。

本轮结论：

- `dom_toggle_action` 应有明确中文解释：
  - `筛选项勾选动作校验`
- 静态契约应锁住：
  - 图搜结果页 checkbox 动作成功后必须写入 `verification_mode`
  - `single_piece_free_shipping` 独立入口动作成功后必须写入 `verification_mode`
  - 单条货源 `source_filter_summary` 也必须保留该字段

这样批次 5 / 6 的动作证据链会更完整：

- 入口怎么定位
- 是否点击成功
- 选中态是否变化
- 结果签名是否变化
- 这次动作属于哪一种校验方式

### 8.10 批次 5 的“统一结论”必须和“阶段字段”一起投影，不能只投影人类结论文案

继续补批次 5 时发现，`single_piece_free_shipping` 的成功态已经有：

- `semantic_conclusion = independent_entry_result_shift_observed`
- `semantic_verification_stage = direct_entry_result_shift_observed`

前者适合给人读，后者适合给机器继续判断阶段。

因此只锁住 `semantic_conclusion` 还不够，顶层消费字段也应该稳定保留 `semantic_verification_stage`。

同理，`encrypted_waybill` 的失败态也不能只在 `filter_status_map.verification_detail` 里看到：

- `special_panel_conclusion = panel_open_or_toggle_failed`

它也需要继续投影到：

- `verification_details`
- `query_verification_details`

结论：

- 统一结论字段负责“讲清楚”
- 阶段字段负责“可继续计算”
- 批次 5 的最终收口必须同时保护这两类字段

### 8.11 真实运行时必须独立落盘筛选快照，否则失败样本无法证明卡在哪一步

继续核对慢爬链路后发现，`source_filter_snapshot` 原本主要随单条货源结果进入：

- `summary.json`
- `ali1688_sources.source_filter_snapshot_json`
- `/api/task_details/{task_id}`

这个路径对成功样本足够，但对批次 5 / 6 的真实页面调研不够：

1. query 筛选、DOM 勾选、特殊面板动作都发生在解析候选货源之前
2. 如果后续页面解析失败或验证码恢复失败，`summary.json` 可能不会包含任何货源
3. 此时仅看 DB 或详情页，无法判断：
   - query 参数是否已经注入
   - DOM 勾选是否已经执行
   - 特殊面板是否打开失败
   - HTML 文本探测是否看到入口线索

本轮结论：

- 慢爬脚本需要在真实运行过程中独立写出筛选快照审计文件
- 最新快照文件用于快速定位最终状态：
  - `_channel_filter_runtime_snapshot.json`
- 事件流文件用于回放状态变化：
  - `_channel_filter_runtime_events.jsonl`
- 这类文件不替代最终入库字段，但它是批次 5 / 6 继续做真实页面闭环的必要证据来源

### 8.12 上游入库必须优先消费运行时审计快照，否则详情页可能解释旧状态

补完 `_channel_filter_runtime_snapshot.json` 后继续检查 `run_full_pipeline.py`，发现还存在一个潜在错位：

1. 慢爬脚本会在多个阶段更新运行时筛选快照
2. `summary.json` 中每条货源也会带 `source_filter_snapshot`
3. 但如果 `summary.json` 内的快照不是最后一次审计态，入库后的详情页就可能仍展示旧状态

典型风险是：

- query / DOM / 特殊入口动作在后续阶段已经更新了最终结论
- 但单条货源入库时仍写入较早的 `source_filter_snapshot`
- 详情页看起来像“未应用 / 未验证”，实际输出目录里已经有更晚的动作证据

本轮结论：

- 上游管线应在慢爬结束后读取最新审计文件
- 入库字段 `source_filter_snapshot_json` 应优先使用：
  - `_channel_filter_runtime_snapshot.json.snapshot`
- 审计文件缺失时，第二优先级应使用：
  - `summary.json` 中的 `source_filter_snapshot`
- 只有前两者都缺失，才允许使用：
  - 运行上下文初始快照

这一步把审计文件从“调试辅助”推进为“最终状态回流的优先证据源”。

补充约束：

- fallback 初始快照不能排在 `summary.json` 单条运行快照之前
- 否则会出现“慢爬已经更新过单条快照，但入库又被初始配置态覆盖”的反向回退

### 8.13 运行时审计阶段必须进入用户可读解释，否则失败样本仍然难以复盘

继续把审计快照接入入库后，还需要多走一步：

1. 审计文件顶层有 `stage`
2. 但 DB 当前保存的是 `snapshot`
3. 如果不把 `stage` 同步进 `snapshot`
4. API 与前端仍然不知道这份快照到底来自哪个运行阶段

本轮结论：

- 快照本体需要保留：
  - `runtime_audit_stage`
  - `runtime_audit_source`
- API 摘要需要透出：
  - `filter_summary.runtime_audit_stage`
  - `source_filter_summary.runtime_audit_stage`
- 前端需要轻量展示运行证据阶段

这样用户看到某个渠道或某条货源时，可以区分：

- 只是初始化快照
- 已检查 query 参数
- 已检查可见筛选项
- 已检查特殊面板入口
- 最终解析失败但仍保留了筛选证据
- 已写入最终货源结果

这能让批次 5 / 6 的真实失败样本从“看起来没生效”变成“知道卡在哪个阶段”。

### 8.14 审计文件还必须限定时间与运行批次，否则多次跑数会串证据

继续收紧真实运行验收后发现，仅有 `_channel_filter_runtime_snapshot.json` 还不够。原因是后续真实跑数会不断产生输出目录：

1. 同一工作区可能同时存在旧审计文件与新审计文件
2. 同一渠道可能在不同时间运行过多次
3. 不同输出目录可能来自不同关键词、不同账号或不同页面结构
4. 如果 gate 只看“是否存在强证据”，就可能用旧批次或其他批次的强证据关闭本轮缺口

本轮结论：

- 审计文件必须带运行上下文：
  - `audit_generated_at_epoch`
  - `audit_run_id`
- gate 必须支持新鲜度门槛：
  - `--max-age-minutes`
  - 超龄文件不能贡献 strong / pending 证据
- gate 必须支持运行批次限定：
  - `--require-audit-run-id <audit_run_id>`
  - 非匹配批次文件只能进入诊断字段，不能关闭 required filters
- gate 必须能区分“运行批次不存在”和“运行批次存在但超龄”：
  - `audit_run_id_not_found` / `scoped_audit_run_id_not_found`
  - `audit_run_files_stale` / `scoped_audit_run_files_stale`
  - 否则后续排查会把“重新生成本轮证据”和“找错运行批次”混为一类问题
- gate 必须支持自动选择最新运行批次：
  - `--latest-audit-run`
  - 这用于减少人工复制 `audit_run_id` 的错误
  - 如果同时要求 `--require-configured-channel <channel_id>`，最新批次必须限定在该渠道内选择，不能用别的渠道的“全局最新批次”覆盖当前渠道证据范围
  - 但它不能与 `--require-audit-run-id` 同时使用
  - 如果审计文件都没有 `audit_run_id`，必须失败而不能退化成“全部文件可用”
- todo-report 必须透出这些限制条件：
  - `freshness_check`
  - `stale_audit_files`
  - `required_audit_run_id`
  - `latest_audit_run_channel_id`
  - `latest_audit_run_id`
  - `unmatched_audit_run_files`

这样批次 5 / 6 后续验收才能回答“这条强证据是不是本轮真实运行产生的”，而不只是回答“仓库里是否曾经出现过强证据”。

### 8.15 真实站点验证码阻断也必须成为审计状态，不能只停留在日志

2026-06-30 继续真实运行时确认：

1. 当前登录态可以进入 1688 首页预热
2. 进入 `https://s.1688.com/youyuan/index.htm` 时触发 1688 验证码拦截
3. 自动滑块尝试后仍未通过
4. 如果快照只停留在 `initialized`，后续复盘会误以为筛选项根本没有进入 runtime

本轮结论：

- 验证码 / 登录验证阻断必须写入 `_channel_filter_runtime_snapshot.json`
- 阻断态应明确表达：
  - `runtime_audit_stage = image_search_home_failed`
  - `mapping_stage = navigation_blocked`
  - `reason = navigation_blocked_by_verification`
  - `blocked_stage`
  - `blocked_url`
- 这类状态只能证明：
  - 配置已经进入 runtime
  - 真实页面被站点验证挡住
- 不能证明：
  - `single_piece_free_shipping` 已真实生效
  - `encrypted_waybill` 已真实生效
  - DOM checkbox 项已完成真实站点闭环

因此 gate 仍应保持失败，并输出：

- `missing_strong_evidence`

这能避免把“真实站点被验证码阻断”误标成“真实筛选项已闭环”。

### 8.16 未闭环项收口策略：语义组合可依赖强证据闭环，DOM/面板项不可伪闭环

2026-07-01 收口 `分销严选、1件代发包邮、密文面单` 时确认：

- `1件代发包邮` 的共享定义是 `semantic_combo_candidate`
  - 它不是稳定 query 参数
  - 当前合理闭环方式是：`single_piece_drop_shipping` 与 `free_shipping` 均被最终结果 URL 强验证后，将组合语义项标记为 `semantic_dependency_pair`
  - 该闭环必须记录依赖项的 `verification_mode` 与 `matched_values`
- `分销严选` 是 `ui_checkbox_candidate`
  - 不能仅凭配置启用或文案定义闭环
  - 必须在真实结果页看到入口、完成点击动作，并观察到 URL 或结果签名变化，才能成为强证据
- `密文面单` 是 `special_panel_candidate`
  - 不能仅凭“页面存在面单支持指标”闭环
  - 真实图搜页已观察到已选条件条 `密文面单：抖音面单`
  - 该条件条代表筛选项已处于启用状态，强于继续点击普通入口；继续点击 `text=密文面单` 会移除已有标签，反而可能取消筛选

因此本轮代码采用两层策略：

1. 对 `single_piece_free_shipping` 增加依赖强证据闭环。
2. 对 `selected_distributors` 与 `encrypted_waybill` 增加真实结果页解析循环内补采，避免只在登录/中间页留下失败证据。
3. 对 `encrypted_waybill` 增加 `active_condition_text` 识别，允许通过 `密文面单：xxx` 已选条件条闭环。

未做的事：

- 没有把 `分销严选` 或 `密文面单` 仅凭配置标记为 strong。
- 没有把商品列表中的 `面单支持` 等同于搜索筛选项 `密文面单`。

2026-07-02 真实站点复跑结果：

- `selected_distributors`：`dom_toggle_action + result_url_changed = true`，审计等级 `site_strong`
- `single_piece_free_shipping`：`semantic_dependency_pair + dependency_pair_strong_verified`，审计等级 `site_strong`
- `encrypted_waybill`：`dom_panel_action + panel_active_condition_observed + active_condition_text`，审计等级 `site_strong`
- 最终快照 `pending_filter_count = 0`
