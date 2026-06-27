# 联调验证清单：1688 搜索能力筛选项按渠道配置

## 目标
用于验证以下 4 类能力已经打通：
- 系统设置页中的“商品爬取与筛选配置 -> 当前渠道货源筛选项”保存正确
- runtime 快照能区分“已配置 / 已应用 / 未应用 / 当前映射阶段”
- 决策资产库与货源明细能按渠道解释本次筛选策略
- 11 个筛选项不会因为证据不足而被误报成“已真实生效”

## 一、配置层验证

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

## 三、资产库与货源明细验证

### 1. 决策资产库列表展示使用渠道
预期：
- 列表页继续轻量展示 `used_channels`
- 不在列表页堆过多筛选细节

### 2. 详情页按渠道分组展示
预期：
- 详情页存在 `channel_groups`
- 每组至少包含：
  - 渠道名称
  - 账号信息
  - 筛选摘要
  - 本渠道货源列表

### 3. 筛选摘要解释规则
详情页必须能区分：
- 已配置但未验证
- 已验证并已应用
- 已配置但本次未应用

不能出现的错误展示：
- 仅因为用户勾选了配置项，就显示“已应用”
- 历史任务无快照时显示为空白且无解释

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
1. 先验证配置保存与回读
2. 再验证 `snapshot_only` 快照结构
3. 再逐个推进 5 个 query 候选项
4. 再验证 checkbox 型 UI 候选
5. 最后验证 `encrypted_waybill` 的特殊面板流程
