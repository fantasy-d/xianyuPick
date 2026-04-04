# Xianyu Tools Tasks

## Purpose

这个文档是当前执行清单。

目标：

- 任务要能直接转成实现动作
- 任务依赖关系要清楚
- 中间产物要固定
- 不再围绕热卖榜主线展开


## Global Rules

### Business Order

固定业务顺序：

1. 输入商品品类
2. 闲鱼搜索该品类
3. 勾选 `超赞鱼小铺`
4. 获取全部结果
5. 按 `想要人数` 倒序，取 `Top 10 hot_items`
6. 用 `hot_items.image_url` 去 1688 以图搜上游货源
7. 在 1688 图片搜索结果页固定筛选 `退货包运费 + 一件代发`
8. 计算利润
9. 输出 `listing_candidates`


### Output Priority

固定输出优先级：

- 中间层保留 `hot_items`
- 最终层以 `listing_candidates` 为主


### Config Rule

涉及业务阈值的地方必须配置化。

包括但不限于：

- 最低利润额
- 最低利润率
- 最大竞争强度
- 最大商家盘占比
- 最大可接受风险等级


## Standard Task Template

下面每个任务默认都遵守这个模板：

- `Purpose`
- `Input`
- `Action`
- `Output`
- `Done When`
- `Depends On`
- `Risk`


## Phase 1: Xianyu Market Scan

### Goal

把“品类 -> 闲鱼 Top 10 热门商品”跑通。

### Input

- `category_keyword`

### Output

- `hot_items`
- `xianyu_market`

### Output Contract

`hot_items` 是列表，固定最多 `10` 条。每条至少包含：

- `hot_item_id`
- `platform`
- `title`
- `price`
- `want_count`
- `seller_name`
- `area`
- `image_url`
- `item_url`
- `source_snapshot`

字段规则：

- `hot_item_id`
  当前热品记录的稳定唯一标识；第一版建议直接复用闲鱼 `item_id`
- `platform`
  固定为 `xianyu`
- `title`
  闲鱼商品标题，用于人工判断和后续货源搜索
- `price`
  当前闲鱼展示售价，单位为人民币元
- `want_count`
  必须是数值；没有时按 `0` 处理
- `seller_name`
  卖家昵称，用于辅助判断店铺类型
- `area`
  商品所在地区，用于辅助判断供给分布
- `image_url`
  闲鱼主图链接。当前是 1688 以图搜的必备输入字段，不能为空。
- `item_url`
  商品链接，尽量使用短链
- `source_snapshot`
  保留原始闲鱼搜索字段，方便排错

`xianyu_market` 至少包含：

- `category_keyword`
- `result_count`
- `filtered_by`
- `sorted_by`
- `top_n`
- `top10_price_stats`
- `sample_items`

字段规则：

- `category_keyword`
  当前输入并实际用于闲鱼搜索的品类词
- `result_count`
  当前筛选条件下的总结果数量
- `filtered_by`
  当前固定筛选条件，第一版至少包含 `超赞鱼小铺`
- `sorted_by`
  当前固定排序规则，第一版为 `want_count desc`
- `top_n`
  当前进入后续流程的商品数，第一版固定为 `10`
- `top10_price_stats`
  过滤后进入后续流程的 `Top 10 hot_items` 价格统计信息，用于描述当前市场售价区间；第一版至少保留 `min/max/median`
- `sample_items`
  用于人工复核的样本商品

### Tasks

#### P1-1 Xianyu Search Rule

##### P1-1.1 Fix Category Search Input

Purpose:

- 固定当前主入口为“商品品类”

Action:

- 定义输入字段
- 统一品类词进入闲鱼搜索

Output:

- `category_search_rule`

Done When:

- 所有后续流程都以品类词为起点


##### P1-1.2 Add 超赞鱼小铺 Filter

Purpose:

- 固定闲鱼搜索筛选条件

Action:

- 找到并实现 `超赞鱼小铺` 勾选逻辑

Output:

- `xianyu_filter_rule`

Done When:

- 每次搜索都能稳定附加 `超赞鱼小铺`

Risk:

- 页面结构可能变化


##### P1-1.3 Fetch All Results

Purpose:

- 获取当前筛选条件下的全部结果

Action:

- 支持分页或滚动拉取
- 汇总完整结果集

Output:

- `full_xianyu_result_set`

Done When:

- 不只返回第一页结果


##### P1-1.4 Sort By Want Count

Purpose:

- 统一爆品筛选标准

Action:

- 提取 `想要人数`
- 按 `想要人数` 倒序排序

Output:

- `sorted_xianyu_result_set`

Done When:

- 排序字段固定为 `want_count desc`


##### P1-1.5 Build Top 10 Hot Items

Purpose:

- 固定第一层中间产物

Action:

- 先按 `want_count` 对完整结果集倒序排序
- 过滤掉 `image_url` 为空的条目
- 取排序后的前 `10` 条
- 映射成标准 `hot_items`
- 保留 `image_url`

Output:

- `hot_items`

Done When:

- 给一个品类词，能稳定输出 `Top 10 hot_items`
- `image_url` 为空的条目不会进入后续流程


### Phase Completion

- 已固定 `超赞鱼小铺` 搜索链路
- 已拿到全部搜索结果
- 已能按 `想要人数` 排序
- 已能稳定输出 `Top 10 hot_items`


## Phase 2: 1688 Source Validation

### Goal

给 `Top 10 hot_items` 通过 1688 以图搜找到上游货源。

### Input

- `hot_items`

### Output

- `source_items`
- `source_resolution`

### Output Contract

`source_items` 每条至少包含：

- `source_item_id`
- `source_platform`
- `title`
- `price`
- `shipping_fee`
- `item_url`
- `shop_name`
- `sales`
- `metadata`

`source_resolution` 每条至少包含：

- `hot_item_id`
- `resolved`
- `source_item_ids`
- `resolution_reason`

字段规则：

- `source_item_id`
  1688 商品唯一标识
- `source_platform`
  当前固定为 `1688`
- `title`
  1688 商品标题
- `price`
  1688 当前供货价，单位为人民币元
- `shipping_fee`
  当前货源运费；未知时允许为空
- `item_url`
  1688 商品链接
- `shop_name`
  1688 店铺名
- `sales`
  1688 销量或成交量字段
- `metadata`
  原始 1688 搜索字段和筛选命中信息
- `hot_item_id`
  对应的闲鱼热品 ID
- `resolved`
  是否匹配到至少一个货源
- `source_item_ids`
  当前匹配到的 1688 货源 ID 列表
- `resolution_reason`
  匹配结果原因，例如 `matched_source_items`、`no_source_items_found`

补充规则：

- 当前只接入 `1688`
- `image_url` 为空的 `hot_item` 直接丢弃，不进入 `Phase 2`
- 每个 `hot_item` 第一版最多保留 `Top 5 source_items`
- `Top 5 source_items` 第一版按 1688 图片搜索结果页原始顺序保留

### Tasks

#### P2-1 Build 1688 Image Search Adapter

Purpose:

- 建立 1688 以图搜适配层

Action:

- 新建 1688 adapter
- 固定图片搜索入口
- 输入 `hot_item.image_url`
- 不点击静态 `以图搜款`
- 使用搜索框右侧动态主按钮 `图搜`

Output:

- `src/xianyu_tools/source_adapter/ali1688.py`

Done When:

- 能用 `image_url` 进入 1688 图片搜索结果页


#### P2-2 Add 1688 Filters

Purpose:

- 固定货源筛选条件

Action:

- 在图片搜索结果页固定筛选 `退货包运费`
- 在图片搜索结果页固定筛选 `一件代发`

Output:

- `ali1688_filter_rule`

Done When:

- 每次图片搜索结果页都附带两个固定筛选


#### P2-3 Resolve Hot Items To Sources

Purpose:

- 把 `Top 10 hot_items` 逐个映射到 1688 货源

Action:

- 使用 `hot_item.image_url` 触发 1688 图片搜索
- 只解析结果列表，不打开详情页
- 丢弃 `price <= 0` 的 `source_item`
- 每个 `hot_item` 只保留前 `5` 条 `source_items`
- 输出 `source_items`
- 输出 `source_resolution`

Output:

- `source_items`
- `source_resolution`

Done When:

- 每个 `hot_item` 都能找到货源或明确记录无货源


### Phase Completion

- 已有 1688 图片搜索适配层
- 已固定 `退货包运费 + 一件代发` 筛选
- 每个 `hot_item` 都有货源结果或无货源记录


## Phase 3: Profit Analysis

### Goal

对比 1688 成本和闲鱼售价，计算利润空间。

### Input

- `hot_items`
- `source_items`
- `source_resolution`

### Output

- `profit_analysis`

### Output Contract

`profit_analysis` 每条至少包含：

- `hot_item_id`
- `source_item_id`
- `source_cost`
- `target_xianyu_price`
- `estimated_margin`
- `estimated_margin_rate`
- `risk_flags`

字段规则：

- `hot_item_id`
  对应的闲鱼热品 ID
- `source_item_id`
  当前采用的 1688 货源 ID
- `source_cost`
  当前货源总成本，至少包含供货价和必要运费；第一版运费统一先按 `0.0` 处理
- `target_xianyu_price`
  用于测算的闲鱼对比售价；第一版固定使用 `hot_item.price`
- `estimated_margin`
  预计利润额，单位为人民币元
- `estimated_margin_rate`
  预计利润率
- `risk_flags`
  风险标签列表

### Tasks

#### P3-1 Define Cost Formula

Purpose:

- 固定第一版利润公式

Action:

- 明确成本项
- 明确利润公式
- 固定利润对比基准为 `hot_item.price`
- 同时保留 `xianyu_market.top10_price_stats` 作为市场售价区间参考
- 第一版运费统一按 `0.0` 进入利润计算

Output:

- `profit_formula_v1`


#### P3-2 Build Profit Output

Purpose:

- 给每个候选输出标准利润结果

Action:

- 结合闲鱼售价和 1688 成本
- 输出 `profit_analysis`

Output:

- `profit_analysis`

Done When:

- 每条候选都有稳定利润结果


### Phase Completion

- 已固定利润公式
- 已稳定输出 `profit_analysis`


## Phase 4: Listing Decision

### Goal

筛出值得上架闲鱼的商品。

### Input

- `hot_items`
- `source_items`
- `source_resolution`
- `profit_analysis`

### Output

- `listing_candidates`

### Output Contract

`listing_candidates` 每条至少包含：

- `hot_item`
- `source_item`
- `profit_analysis`
- `decision`

`decision` 至少包含：

- `is_recommended`
- `reasons`
- `blocked_by`

字段规则：

- `hot_item`
  当前评估的闲鱼热门商品对象
- `source_item`
  当前选定的 1688 货源对象
- `profit_analysis`
  当前组合下的利润分析结果
- `decision`
  最终推荐判断结果
- `is_recommended`
  是否推荐作为上架候选
- `reasons`
  推荐原因列表
- `blocked_by`
  拦截原因列表

补充规则：

- 第一版每个 `hot_item` 最多只输出 `1` 条最终 `listing_candidate`
- 候选货源从该 `hot_item` 的 `Top 5 source_items` 中选择利润最优的一条

### Tasks

#### P4-1 Define Decision Rule

Purpose:

- 固定推荐逻辑

Action:

- 设计阈值规则
- 支持配置化

Output:

- `listing_decision_rule`


#### P4-2 Build Listing Candidates

Purpose:

- 输出最终候选

Action:

- 结合 `hot_item/source_item/profit_analysis`
- 输出 `listing_candidates`

Output:

- `listing_candidates`

Done When:

- 可以稳定输出最终候选列表


### Phase Completion

- 能稳定输出 `listing_candidates`
- 每条候选都有明确推荐或拦截原因
- 阈值可调


## Current Priority

严格按下面顺序推进：

1. `P1-1.2`
2. `P1-1.3`
3. `P1-1.4`
4. `P1-1.5`
5. `P2-1`
6. `P2-2`
7. `P2-3`
8. `P3-1`
9. `P3-2`
10. `P4-1`
11. `P4-2`

原因：

- 当前最关键的是先把闲鱼 `Top 10 hot_items` 主链路跑通
- 没有这一步，后面的 1688 货源和利润分析都没有主语
