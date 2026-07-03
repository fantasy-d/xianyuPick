# 联调验证清单：1688 搜索能力筛选项按渠道配置

## 目标
用于验证以下 4 类能力已经打通：
- 系统设置页中的“商品爬取与筛选配置 -> 当前渠道货源筛选项”保存正确
- runtime 快照能区分“已配置 / 已应用 / 未应用 / 当前映射阶段”
- 决策资产库与货源明细能按渠道解释本次筛选策略
- 11 个筛选项不会因为证据不足而被误报成“已真实生效”

## 最近一次完整契约与页面验收

时间：2026-07-02

本地契约命令：

```bash
PYTHONPATH=src /opt/anaconda3/envs/mytools/bin/python -c 'from scripts.validate_source_channel_config import validate_detail_filter_runtime_diagnostics_label_contract, validate_detail_channel_filter_summary_contract, validate_detail_source_filter_summary_contract, validate_task_channel_summary_contract; validate_detail_filter_runtime_diagnostics_label_contract(); validate_detail_channel_filter_summary_contract(); validate_detail_source_filter_summary_contract(); validate_task_channel_summary_contract(); print("batch7-detail-contracts-ok")'
```

结果：
- `status = passed`
- 输出：`batch7-detail-contracts-ok`

覆盖边界：
- 已覆盖 API 摘要、前端解释文案与 runtime 快照契约
- 已使用真实审计样本 `scratch/channel_filter_real_audit_manual_20260702_full_closure`
- 已将真实审计结果入库为 `cf20260702`
- 已完成页面级验收：
  - `决策资产库`
  - `1688筛选闭环页面验收样本`
  - 商品详情页
- 页面验收结果：
  - `scratch/page_validate_cf20260702_result.json`
  - `all_passed = true`

当前闭环项：
- `selected_distributors`
- `single_piece_drop_shipping`
- `single_piece_free_shipping`
- `free_shipping`
- `encrypted_waybill`

当前仍需按模板推进但不属于本次已闭环范围的候选项：
- `rapid_invoice`
- `seven_day_return`
- `freight_insurance_return`
- `real_factory_verified`
- `strength_verified`
- `official_logistics`

## 真实运行审计产物判定

真实慢爬跑完后，需要用下面命令检查输出目录中的筛选审计产物：

```bash
PYTHONPATH=src /opt/anaconda3/envs/mytools/bin/python scripts/inspect_channel_filter_runtime_audit.py <output-dir>
```

或直接传入审计文件：

```bash
PYTHONPATH=src /opt/anaconda3/envs/mytools/bin/python scripts/inspect_channel_filter_runtime_audit.py <output-dir>/_channel_filter_runtime_snapshot.json
```

如果一次真实跑数产生多个输出目录，可以批量或递归扫描：

```bash
PYTHONPATH=src /opt/anaconda3/envs/mytools/bin/python scripts/inspect_channel_filter_runtime_audit.py --recursive outputs scratch
```

批量扫描报告必须包含：
- `strong_evidence_filter_keys`
  - 全局强证据 key 汇总，用于快速判断本次是否出现过某项强证据
- `strong_evidence_filter_keys_by_channel`
  - 渠道级强证据索引，用于判断每个 `channel_id` 自己形成了哪些强证据
- `pending_filters[*].channel_id`
  - 待验证项必须保留来源渠道，方便详情页和计划验收按渠道解释缺口
- `pending_filters_by_channel`
  - 渠道级待验证项索引，用于判断每个 `channel_id` 自己还有哪些未闭环项
  - 每条待验证项必须保留 `audit_file`，方便回查真实运行输出目录

如果需要判断某些筛选项是否已经满足本计划的真实站点强证据门槛，可以传入 required filters：

```bash
PYTHONPATH=src /opt/anaconda3/envs/mytools/bin/python scripts/inspect_channel_filter_runtime_audit.py --recursive --required-filter single_piece_free_shipping --required-filter encrypted_waybill outputs scratch
```

如果需要让自动化脚本在门槛不通过时直接失败，可以增加 `--strict-exit`：

```bash
PYTHONPATH=src /opt/anaconda3/envs/mytools/bin/python scripts/inspect_channel_filter_runtime_audit.py --recursive --required-filter single_piece_free_shipping --required-filter encrypted_waybill --strict-exit outputs scratch
```

如果需要避免旧审计文件被误当成本轮真实运行证据，可以增加新鲜度门槛：

```bash
PYTHONPATH=src /opt/anaconda3/envs/mytools/bin/python scripts/inspect_channel_filter_runtime_audit.py --recursive --required-filter encrypted_waybill --max-age-minutes 120 --strict-exit outputs scratch
```

如果需要避免多个真实运行批次之间互相串证据，可以限定本次运行的 `audit_run_id`：

```bash
PYTHONPATH=src /opt/anaconda3/envs/mytools/bin/python scripts/inspect_channel_filter_runtime_audit.py --recursive --required-filter encrypted_waybill --require-audit-run-id <audit_run_id> --strict-exit outputs scratch
```

如果只想验收扫描结果中最新的真实运行批次，可以自动选择最新 `audit_run_id`：

```bash
PYTHONPATH=src /opt/anaconda3/envs/mytools/bin/python scripts/inspect_channel_filter_runtime_audit.py --recursive --required-filter encrypted_waybill --latest-audit-run --strict-exit outputs scratch
```

如果只需要给 CI 或人工复盘输出可执行缺口待办，可以增加 `--todo-report`：

```bash
PYTHONPATH=src /opt/anaconda3/envs/mytools/bin/python scripts/inspect_channel_filter_runtime_audit.py --recursive --required-filter encrypted_waybill --todo-report outputs scratch
```

也可以按当前系统配置中某个渠道启用的筛选项自动生成 required filters：

```bash
PYTHONPATH=src /opt/anaconda3/envs/mytools/bin/python scripts/inspect_channel_filter_runtime_audit.py --recursive --require-configured-channel ali1688 outputs scratch
```

当前补充规则：
- `--require-configured-channel` 会按指定 `channel_id` 读取当前配置中已启用的渠道筛选项
- 该路径必须证明不同 1688 渠道之间不会串值
- 即使当前渠道没有启用任何筛选项，也必须输出门槛报告
- 如果输出 `required_filter_keys = []`，则 `passed` 必须为 `false`
- 使用 `--require-configured-channel` 时，门槛报告必须进入渠道作用域：
  - `required_channel_id` 必须等于传入的渠道 ID
  - `scoped_strong_evidence_filter_keys` 只能来自该渠道自己的审计文件
  - 其他渠道的同名强证据不能满足当前渠道 required filters
  - 指定渠道没有审计文件时，`scoped_audit_file_count = 0` 且 `passed = false`
- 当前本地 `ali1688` 配置实测结果为：
  - `audit_file_count = 0`
  - `required_channel_id = "ali1688"`
  - `scoped_audit_file_count = 0`
  - `required_filter_keys = []`
  - `passed = false`
  - 这只能证明当前配置没有可验收筛选项，不能关闭真实站点缺口

### 2026-06-30 真实站点阻断审计样本

本轮已经生成真实运行审计样本：

```bash
PYTHONPATH=src /opt/anaconda3/envs/mytools/bin/python scripts/inspect_channel_filter_runtime_audit.py scratch/channel_filter_real_audit_20260630_retry
```

当前样本关键结论：

- `runtime_audit_stage = "image_search_home_failed"`
- `mapping_stage = "navigation_blocked"`
- `configured_enabled_filter_keys` 包含：
  - `selected_distributors`
  - `single_piece_drop_shipping`
  - `single_piece_free_shipping`
  - `free_shipping`
  - `encrypted_waybill`
- 所有已配置筛选项仍为待验证：

### 2026-07-01 人工验证码后真实站点审计样本

本轮已经生成可见浏览器真实运行审计样本：

```bash
PYTHONPATH=src /opt/anaconda3/envs/mytools/bin/python scripts/inspect_channel_filter_runtime_audit.py scratch/channel_filter_real_audit_manual_20260701_restart2
```

关键输出：

- 审计文件：`scratch/channel_filter_real_audit_manual_20260701_restart2/_channel_filter_runtime_snapshot.json`
- 日志文件：`scratch/channel_filter_real_audit_manual_20260701_restart2/run.log`
- `runtime_audit_stage = "summary_written"`
- `mapping_stage = "query_mapped"`
- 已验证强证据：
  - `single_piece_drop_shipping`
  - `free_shipping`
- 仍需补强证据：
  - `selected_distributors`
  - `single_piece_free_shipping`
  - `encrypted_waybill`

本轮显式 gate 命令：

```bash
PYTHONPATH=src /opt/anaconda3/envs/mytools/bin/python scripts/inspect_channel_filter_runtime_audit.py --required-filter selected_distributors --required-filter single_piece_drop_shipping --required-filter single_piece_free_shipping --required-filter free_shipping --required-filter encrypted_waybill --todo-report scratch/channel_filter_real_audit_manual_20260701_restart2/_channel_filter_runtime_snapshot.json
```

当前 gate 结论：

- `passed = false`
- `closure_blockers = ["missing_strong_evidence"]`
- `required_filter_gap_todos` 指向：
  - `selected_distributors`
  - `single_piece_free_shipping`
  - `encrypted_waybill`
  - `reason = "navigation_blocked_by_verification"`

required filter gate：

```bash
PYTHONPATH=src /opt/anaconda3/envs/mytools/bin/python scripts/inspect_channel_filter_runtime_audit.py --required-filter single_piece_free_shipping --required-filter encrypted_waybill --max-age-minutes 120 --latest-audit-run --todo-report scratch/channel_filter_real_audit_20260630_retry
```

当前 gate 期望：

- `passed = false`
- `closure_blockers = ["missing_strong_evidence"]`
- `latest_audit_run_id = "1782834455-ali1688-image_search_home_failed"`

验收口径：

- 该样本可以证明真实 runtime 已收到渠道筛选配置
- 该样本可以证明真实站点验证码阻断已经被写入审计文件
- 该样本不能关闭 `single_piece_free_shipping` / `encrypted_waybill` 的真实强证据缺口

验收规则：
- 只有进入 `strong_evidence_filter_keys` 的筛选项，才允许作为“真实站点强证据”
- `can_close_real_site_gap = true` 才允许关闭对应筛选项的真实站点缺口
- 批量扫描时，`audit_file_count = 0` 表示当前没有任何可判定的真实运行审计产物，不能关闭缺口
- 审计报告必须声明报告形态与结构版本：
  - 单文件报告：`report_type = single_runtime_audit`
  - 批量报告：`report_type = runtime_audit_batch`
  - gate 报告：`report_type = runtime_audit_gate`
  - 三类报告都必须提供 `report_schema_version`
- 真实运行写出的 `_channel_filter_runtime_snapshot.json` 必须提供运行上下文：
  - 顶层 `audit_generated_at_epoch`
  - 顶层 `audit_run_id`
  - 事件流 `_channel_filter_runtime_events.jsonl` 中的每条事件也必须保留同一个 `audit_run_id`
  - 单文件审计报告必须透出 `audit_run_id` 与 `audit_generated_at_epoch`
  - 批量审计报告必须聚合 `audit_run_ids` 与 `audit_generated_at_epochs`
- 使用 `--require-audit-run-id` 时，批量 / gate 报告必须提供运行批次过滤信息：
  - `required_audit_run_id`
  - `matched_audit_run_file_count`
  - `matched_stale_audit_run_file_count`
  - `unmatched_audit_run_file_count`
  - `unmatched_audit_run_files`
  - `reports[*].audit_run_id_matched`
- 使用 `--require-audit-run-id` 时，非匹配运行批次的审计文件不能贡献 strong / pending gate 证据
- 使用 `--require-audit-run-id` 时，如果当前 gate 作用域内只有非匹配运行批次审计文件，必须失败：
  - 全局 gate：`audit_run_id_not_found`
  - 渠道作用域 gate：`scoped_audit_run_id_not_found`
  - `scoped_unmatched_audit_run_file_count` 表示当前作用域内非匹配运行批次审计文件数
- 使用 `--require-audit-run-id` 或 `--latest-audit-run` 且同时使用 `--max-age-minutes` 时，如果匹配运行批次存在但该批次审计文件都已超龄，必须失败：
  - 全局 gate：`audit_run_files_stale`
  - 渠道作用域 gate：`scoped_audit_run_files_stale`
  - `matched_stale_audit_run_file_count` 表示全局匹配运行批次中的超龄审计文件数
  - `scoped_matched_stale_audit_run_file_count` 表示渠道作用域内匹配运行批次中的超龄审计文件数
- 使用 `--latest-audit-run` 时，批量 / gate 报告必须自动选择最新可识别运行批次：
  - `latest_audit_run_only`
  - `latest_audit_run_channel_id`
  - `latest_audit_run_id`
  - `latest_audit_run_available`
  - `latest_audit_file`
  - `latest_audit_generated_at_epoch`
  - 自动选中的 `latest_audit_run_id` 必须同步写入 `required_audit_run_id`
- 使用 `--latest-audit-run --require-configured-channel <channel_id>` 时，最新运行批次必须按指定渠道选择：
  - `latest_audit_run_channel_id` 必须等于传入渠道 ID
  - 其他渠道中更新的 `audit_run_id` 不能覆盖当前渠道自己的最新批次
  - 其他渠道的 strong / pending 证据不能进入当前渠道 gate 范围
- 使用 `--latest-audit-run` 时，只有最新 `audit_run_id` 对应的审计文件能贡献 strong / pending gate 证据
- 使用 `--latest-audit-run` 时，如果审计文件存在但都缺少 `audit_run_id`，必须失败：
  - `latest_audit_run_id_missing`
- `--latest-audit-run` 与 `--require-audit-run-id` 互斥，不能同时传入
- 使用 `--max-age-minutes` 时，批量 / gate 报告必须提供审计文件新鲜度信息：
  - `freshness_check.enabled`
  - `freshness_check.max_age_seconds`
  - `fresh_audit_file_count`
  - `stale_audit_file_count`
  - `stale_audit_files`
  - `reports[*].audit_file_mtime_epoch`
  - `reports[*].audit_file_age_seconds`
  - `reports[*].audit_file_fresh`
- 使用 `--max-age-minutes` 时，超龄审计文件不能贡献 strong / pending gate 证据
- 使用 `--max-age-minutes` 时，如果当前 gate 作用域内只有超龄审计文件，必须失败：
  - 全局 gate：`stale_audit_files_only`
  - 渠道作用域 gate：`scoped_audit_files_stale`
  - `scoped_audit_file_count` 表示可用于 gate 的新鲜审计文件数
  - `scoped_total_audit_file_count` 表示当前作用域总审计文件数
  - `scoped_stale_audit_file_count` 表示当前作用域超龄审计文件数
- 使用 required filters 时，只有 `passed = true` 且 `missing_strong_filter_keys = []` 才允许关闭对应 required filters 的验收缺口
- 使用 required filters 时，报告必须声明 required filters 来源：
  - `required_filter_source = manual`：来自 CLI 显式 `--required-filter`
  - `required_filter_source = config`：来自 `--require-configured-channel`
  - `required_filter_source = manual_and_config`：CLI 显式项与配置项合并
  - `required_filter_config_channel_id`：配置驱动时必须保留来源渠道 ID
- 使用 required filters 时，失败报告必须提供 `missing_filter_diagnostics`
  - `pending_without_strong_evidence`：该项已在审计中出现，但只形成 pending / 弱证据
  - `not_observed_in_audit`：该项在当前审计产物中完全没有出现
  - pending 诊断应尽量带出 `evidence_level / pending_reason / audit_file / channel_id`
- 使用 required filters 时，报告必须提供 `required_filter_status_map`
  - `strong`：该 required filter 已形成强站点证据
  - `pending`：该 required filter 已出现，但强证据不足
  - `missing`：该 required filter 在当前审计产物中没有出现
- 使用 required filters 时，报告必须提供 `required_filter_status_counts`
  - 用于快速判断本轮 required filters 中 `strong / pending / missing` 的数量
- 使用 required filters 时，报告必须提供 `required_filter_next_actions`
  - `strong` 项建议动作为 `none`
  - `pending` 项建议动作为 `inspect_pending_audit_file`
  - `missing` 项建议动作为 `run_real_crawl_and_generate_audit`
- 使用 required filters 时，报告必须提供 `gate_failure_reasons`
  - `required_filters_empty`：显式请求门槛但没有解析到 required filters
  - `audit_files_empty`：未找到任何审计文件
  - `scoped_audit_files_empty`：指定渠道下没有审计文件
  - `stale_audit_files_only`：全局作用域只有超龄审计文件
  - `scoped_audit_files_stale`：指定渠道作用域只有超龄审计文件
  - `audit_run_id_not_found`：全局作用域只有非匹配运行批次审计文件
  - `scoped_audit_run_id_not_found`：指定渠道作用域只有非匹配运行批次审计文件
  - `audit_run_files_stale`：匹配运行批次存在，但该批次审计文件全部超龄
  - `scoped_audit_run_files_stale`：指定渠道作用域内匹配运行批次存在，但该批次审计文件全部超龄
  - `latest_audit_run_id_missing`：请求自动选择最新运行批次，但审计文件都没有 `audit_run_id`
  - `missing_strong_evidence`：required filters 缺少强站点证据
- 使用 required filters 时，报告必须提供机器可消费的缺口关闭判断：
  - `can_close_required_filter_gaps`：只有 required filters 全部形成强证据且审计文件存在时为 `true`
  - `closure_blockers`：直接复用当前阻塞关闭的原因列表
  - `closure_summary.can_close_required_filter_gaps`
  - `closure_summary.strong_required_filter_keys`
  - `closure_summary.pending_required_filter_keys`
  - `closure_summary.missing_required_filter_keys`
- 使用 required filters 时，报告必须提供可执行缺口待办：
  - `required_filter_gap_todos`
  - 已经形成强证据的筛选项不应生成待办
  - `pending` 项待办动作为 `inspect_pending_audit_file`
  - `missing` 项待办动作为 `run_real_crawl_and_generate_audit`
  - 渠道作用域报告中的待办必须保留 `required_channel_id`
  - 如果 pending 记录带审计文件路径，待办中必须保留 `pending_audit_files`
- 使用 `--todo-report` 时，CLI 必须输出精简待办报告：
  - `report_type = runtime_audit_gate_todos`
  - `passed`
  - `can_close_required_filter_gaps`
  - `required_filter_source`
  - `required_filter_config_channel_id`
  - `required_filter_keys`
  - `required_filter_labels`
  - `closure_blockers`
  - `freshness_check`
  - `fresh_audit_file_count`
  - `stale_audit_file_count`
  - `stale_audit_files`
  - `required_audit_run_id`
  - `latest_audit_run_only`
  - `latest_audit_run_channel_id`
  - `latest_audit_run_id`
  - `latest_audit_run_available`
  - `latest_audit_file`
  - `latest_audit_generated_at_epoch`
  - `matched_audit_run_file_count`
  - `matched_stale_audit_run_file_count`
  - `unmatched_audit_run_file_count`
  - `unmatched_audit_run_files`
  - `scoped_audit_file_count`
  - `scoped_total_audit_file_count`
  - `scoped_stale_audit_file_count`
  - `scoped_matched_audit_run_file_count`
  - `scoped_matched_stale_audit_run_file_count`
  - `scoped_unmatched_audit_run_file_count`
  - `required_filter_gap_todos`
  - `--todo-report` 必须与 `--required-filter` 或 `--require-configured-channel` 搭配使用
  - 未搭配 `--required-filter` 或 `--require-configured-channel` 时必须返回非 0，并输出明确 parser 错误
  - 搭配 `--strict-exit` 时，精简待办报告不能绕过 gate 失败退出码；`passed = false` 必须返回非 0
  - 搭配 `--max-age-minutes` 时，精简待办报告必须带出超龄审计文件列表，避免 CI 只看到失败原因但无法定位旧证据
  - 搭配 `--require-audit-run-id` 时，精简待办报告必须带出运行批次限定条件和非匹配审计文件数量
  - 搭配 `--latest-audit-run` 时，精简待办报告必须带出自动选择的最新运行批次
- 共享筛选定义必须提供 11 个用户可见中文标签，并在以下位置保持一致：
  - `get_ali1688_channel_search_filter_meta(filter_key).label`
  - `normalize_channel_search_filter_snapshot(...).filter_labels`
  - `filter_status_map[filter_key].label`
  - `inspect_channel_filter_runtime_audit.py` 输出的 `filter_labels` 与 `filters[].label`
- 使用 required filters 时，gate 缺口报告必须提供用户可读标签：
  - `required_filter_labels`
  - `missing_strong_filter_labels`
  - `missing_filter_diagnostics[].label`
  - `required_filter_status_map[filter_key].label`
  - `required_filter_next_actions[].label`
  - 即使当前没有任何审计文件，也应从共享筛选定义回退得到中文标签
- 未传 `--strict-exit` 时，CLI 保持兼容，仅打印报告
- 传入 `--strict-exit` 时，`passed = false` 必须返回非 0，供 CI / 自动脚本拦截
- 使用 `--require-configured-channel` 时，如果当前渠道配置解析出来的 required filters 为空，不能视为通过
- 使用 `--require-configured-channel` 扫描多个渠道审计文件时，只能由同一 `channel_id` 的审计文件关闭该渠道缺口
- 以下情况不能算完成：
  - 仅看到筛选入口
  - 仅点击过入口
  - 仅选中但没有观察到结果签名变化
  - 仅 query 注入但没有后续结果验证

## 一、配置层验证

### 0. 顶部筛选项按渠道隔离的基础检查
步骤：
1. 准备两个 `ali1688` 渠道，例如：
   - `1688 货源渠道`
   - `义乌渠道`
2. 为两个渠道分别勾选不同顶部筛选项，例如：
   - 渠道 A：`single_piece_drop_shipping`、`free_shipping`
   - 渠道 B：`rapid_invoice`、`official_logistics`
3. 保存后重新打开系统配置页

预期：
- 渠道 A 只回显自己的筛选项
- 渠道 B 只回显自己的筛选项
- 两个渠道不会共享同一套顶部筛选勾选状态
- 当前活动渠道切换后，页面展示应跟着渠道切换，而不是跟着“最后编辑过的账号”

### 1. 保存合法的 1688 渠道筛选项
步骤：
1. 打开“系统参数配置 -> 商品爬取与筛选配置”
2. 选中一个 `ali1688` 渠道
3. 勾选若干筛选项，例如：
   - `single_piece_drop_shipping`
   - `free_shipping`
4. 点击保存

预期：
- `/api/system/configs` 返回：
  - `crawl.channel_search_filters` 中存在对应 `channel_id`
  - `filters` 中仅包含已知 key
  - 所有值均为布尔值

### 2. 非 1688 渠道返回空 filters
步骤：
1. 配置一个非 `ali1688` 渠道
2. 读取 `/api/system/configs`

预期：
- 该渠道可以保留 `channel_id`
- 但 `filters` 必须是：

```json
{}
```

### 3. 未知 key 被清洗
输入样例：

```json
{
  "channel_id": "ali1688-default",
  "filters": {
    "free_shipping": true,
    "mystery_flag": true
  }
}
```

预期：
- 回包中仅保留：
  - `free_shipping`
- `mystery_flag` 被剔除

## 二、runtime 快照验证

### 1. `snapshot_only` 基础快照
前提：
- 当前尚未为某筛选项接入真实映射

预期 `source_filter_snapshot` 至少包含：
- `channel_id`
- `channel_type`
- `supported_filter_keys`
- `configured_filters`
- `configured_enabled_filter_keys`
- `applied_filter_keys`
- `unapplied_filter_keys`
- `unapplied_reason_map`
- `mapping_stage`

并满足：
- `mapping_stage = "snapshot_only"`
- `applied_filter_keys = []`
- `unapplied_filter_keys = configured_enabled_filter_keys`

### 2. query 候选项验证模板
适用项：
- `rapid_invoice`
- `single_piece_drop_shipping`
- `free_shipping`
- `freight_insurance_return`
- `official_logistics`

每项都要记录：
1. 渠道 ID
2. 启用前的搜索 URL
3. 启用后的搜索 URL
4. 新增 / 变化的 query 参数
5. 结果页是否正常打开
6. 结果数量或结果集合是否变化
7. runtime 快照是否出现：
   - `applied_filter_keys += [当前项]`
   - 或 `unapplied_reason_map[当前项]`

只有同时满足以下条件，才能标记为 `query_mapped`：
- URL 参数变化可复现
- 页面正常出结果
- 结果确实产生筛选变化
- 快照能正确标记为已应用

### 3. checkbox 型 UI 候选验证模板
适用项：
- `selected_distributors`
- `seven_day_return`
- `real_factory_verified`
- `strength_verified`

每项都要记录：
1. 稳定 selector 是否存在
2. 勾选动作是否成功
3. 勾选后页面是否刷新 / 重绘
4. 勾选后是否能观察到：
   - URL 变化
   - DOM 状态变化
   - 结果数变化
5. runtime 快照是否正确区分：
   - 已配置未应用
   - 已配置已应用

如果上述任一项不稳定：
- 保留 `snapshot_only`
- 写入 `unapplied_reason_map`

补充渠道隔离检查：
- 若同一任务里两个渠道都启用了 checkbox 类项：
  - 渠道 A 的 selector 失败不能覆盖渠道 B 的动作结果
  - 渠道 B 已登录也不能替渠道 A 执行 checkbox 动作

前端解释补充：
- 详情页必须能解释 runtime 诊断字段，而不只展示“已应用 / 未应用”
- 至少覆盖：
  - `selector_candidates_tried`
  - `selector_resolution_mode`
  - `text_fallback_considered`
  - `entry_selector_strategy`
  - `page_filter_layout`
  - `result_signature_changed`
- 单条货源摘要 `source_filter_summary.query_verification_details` 也必须保留这些诊断字段，避免 source 卡片只能展示汇总状态

### 4. 特殊面板项验证模板
适用项：
- `encrypted_waybill`

验证顺序：
1. 是否存在稳定入口 selector
2. 点击后是否打开二级面板
3. 面板中是否存在真实勾选控件
4. 勾选后是否产生可观察变化
5. 快照中是否能正确标记

若二级面板无法稳定打开：
- 不进入实现阶段
- 仅记录为：
  - `mapping_stage = "snapshot_only"`
  - `unapplied_reason_map.encrypted_waybill = "special_panel_unmapped"`

若结果页已观察到 `密文面单：xxx` 已选条件条：
- 允许直接闭环为强证据：
  - `verification_mode = "dom_panel_action"`
  - `special_panel_conclusion = "panel_active_condition_observed"`
  - `panel_term_selected_via_after_action = "active_condition_text"`
- 含义：
  - 已确认当前结果页筛选条件中存在 `密文面单` 已启用状态
  - 不应继续点击普通 `密文面单` 入口，避免反向取消已启用筛选

前端解释补充：
- `encrypted_waybill` 的统一结论字段 `special_panel_conclusion` 必须有中文解释
- 至少覆盖：
  - `entry_signal_detected_pending_panel_mapping`
  - `panel_open_or_toggle_failed`
  - `panel_action_applied_no_result_shift`
  - `panel_action_result_shift_observed`
- 详情页还必须解释特殊面板诊断字段：
  - `panel_trigger_candidates`
  - `panel_visible_via`

### 5. 组合语义项验证模板
适用项：
- `single_piece_free_shipping`

验证顺序：
1. 是否观察到独立入口
2. 依赖项 `single_piece_drop_shipping + free_shipping` 是否齐备
3. 独立入口动作后是否产生可观察结果变化
4. 快照中是否写入统一结论字段：
   - `semantic_conclusion`

前端解释补充：
- `single_piece_free_shipping` 的统一结论字段 `semantic_conclusion` 必须有中文解释
- 至少覆盖：
  - `dependency_pair_incomplete`
  - `dependency_pair_ready_pending_runtime`
  - `independent_entry_observed_pending_result_validation`
  - `independent_entry_no_result_shift`
  - `independent_entry_result_shift_observed`

## 三、资产库与货源明细验证

### 1. 决策资产库列表展示使用渠道
预期：
- 列表页继续轻量展示 `used_channels`
- 不在列表页堆过多筛选细节
- 允许同一资产同时出现多个渠道标签
- 不把某个顶部筛选项的状态直接提升成列表页全局结论

### 2. 详情页按渠道分组展示
预期：
- 详情页存在 `channel_groups`
- 每组至少包含：
  - 渠道名称
  - 账号信息
  - 筛选摘要
  - 本渠道货源列表
- 若同一顶部筛选项在两个渠道上的结论不同：
  - 必须分别在各自 `channel_group` 中解释
  - 不能压成单一全局摘要

### 3. 筛选摘要解释规则
详情页必须能区分：
- 已配置但未验证
- 已验证并已应用
- 已配置但本次未应用

并补充要求：
- 详情页与任务列表优先消费接口侧 `filter_summary`
- `filter_summary` 本身应直接包含：
  - `filter_status_map`
  - `query_verification_details`
- 前端只允许在历史数据或接口缺失时，退回 `source_filter_snapshot` 做兜底推断

不能出现的错误展示：
- 仅因为用户勾选了配置项，就显示“已应用”
- 历史任务无快照时显示为空白且无解释

### 4. 固定排序与渠道筛选必须语义拆分
预期：
- 详情页存在固定排序说明：
  - `预估纯利倒序`
- 渠道筛选控件只影响展示范围
- 不存在一个同时承担“排序切换 + 渠道筛选”语义的控件
- 前端若展示排序说明，应优先消费接口返回的：
  - `source_sort_strategy`
  - `channel_group_sort_strategy`
- 静态契约应锁住：
  - 不再出现 `货源排序` 交互文案
  - `固定排序` 只作为说明展示
  - `货源渠道` 下拉只绑定渠道筛选状态
  - 页面必须说明“渠道筛选仅影响当前展示范围”

## 四、多渠道回归验证

### 1. 同一任务启用多个渠道
步骤：
1. 启用两个渠道
2. 为两个渠道设置不同筛选项
3. 跑同一个抓取任务

预期：
- `used_channels` 同时展示两个渠道
- `channel_groups` 中每个渠道只显示自己的筛选快照
- 不出现渠道之间串值

### 2. 历史任务兼容
步骤：
1. 打开旧任务详情

预期：
- 如果没有 `source_filter_snapshot`
- 页面显示“历史数据未记录渠道筛选快照”或等效降级文案
- 不应误判为新链路失败

## 五、当前推荐的最小验证顺序

### 已闭环链路的回归顺序
1. 先跑契约校验，确认 API / 前端解释字段未退化
2. 再检查最新真实审计样本：
   - `scratch/channel_filter_real_audit_manual_20260702_full_closure`
3. 再检查入库样本：
   - `task_id = cf20260702`
4. 最后做页面级验收：
   - 决策资产列表
   - 任务报告页
   - 商品详情页

### 后续新增筛选项的推进顺序
1. 先验证配置保存与回读
2. 再验证 `snapshot_only` 快照结构
3. 再补 runtime 映射或 DOM 动作证据
4. 再让真实抓取结果入库
5. 最后做 API 与页面级验收

说明：
- `selected_distributors / single_piece_drop_shipping / single_piece_free_shipping / free_shipping / encrypted_waybill` 已按上述闭环顺序完成。
- 后续只对尚未真实闭环的候选项继续套用“新增筛选项的推进顺序”。

## 六、真实运行审计文件验证

### 1. 最新运行快照
预期：
- 每次慢爬任务输出目录中应尽量生成：
  - `_channel_filter_runtime_snapshot.json`
- 文件中至少包含：
  - `stage`
  - `channel_id`
  - `configured_enabled_filter_keys`
  - `query_injected_filter_keys`
  - `applied_filter_keys`
  - `unapplied_filter_keys`
  - `filter_status_map`
  - `query_verification_details`
  - `snapshot`

### 2. 运行事件流
预期：
- 慢爬任务输出目录中应尽量生成：
  - `_channel_filter_runtime_events.jsonl`
- 事件流应能看出筛选快照从初始化到最终阶段的变化
- 解析失败样本也应能留下最后一次可用筛选证据

不能出现的错误：
- 只有成功写入 `summary.json` 时才有筛选证据
- 真实页面动作失败后没有任何可审计阶段信息

### 3. 上游入库快照优先级
预期：
- `run_full_pipeline.py` 在慢爬结束后优先读取：
  - `_channel_filter_runtime_snapshot.json.snapshot`
- 入库字段：
  - `ali1688_sources.source_filter_snapshot_json`
  应优先使用最新运行时审计快照
- 审计文件不存在时，优先回退：
  - `summary.json` 内单条货源快照
- 只有单条货源快照也不存在时，才回退：
  - 初始配置快照

不能出现的错误：
- 输出目录已有最终审计快照，但详情页仍展示初始配置态
- 输出目录无审计快照时，用初始配置快照覆盖 `summary.json` 内更晚的单条运行快照
- `summary.json` 缺失时完全无法知道筛选动作停在哪个阶段

### 4. 审计阶段进入 API 与前端解释
预期：
- `source_filter_snapshot_json` 中应保留：
  - `runtime_audit_stage`
  - `runtime_audit_source`
- `/api/task_details/{task_id}` 中应透出：
  - `channel_groups[*].filter_summary.runtime_audit_stage`
  - `sources[*].source_filter_summary.runtime_audit_stage`
- 前端详情页应在渠道组筛选摘要与单条货源筛选摘要中显示运行证据阶段

不能出现的错误：
- 审计文件有 `stage`，但入库后的 snapshot 丢失该阶段
- API 摘要丢失审计阶段，导致前端无法解释证据来源
- 前端只显示“未应用/待验证”，但不说明快照停在哪个运行阶段
