# Xianyu Tools Framework And Plan

## Goal

这个项目当前的真实目标是：

1. 输入一个商品品类
2. 在闲鱼搜索该品类，并勾选 `超赞鱼小铺`
3. 获取该搜索条件下的全部商品结果
4. 按 `想要人数` 倒序排序，取 `Top 10`
5. 统计这 10 个商品的市场价格和竞争情况
6. 用这 10 个商品的主图 `image_url` 去 1688 以图搜查对应上游货源，并勾选：
   - `退货包运费`
   - `一件代发`
7. 对比 1688 成本和闲鱼售价，测算利润空间
8. 最终筛出值得上架闲鱼的商品

当前主链路已经明确为：

`category -> xianyu market scan -> top10 hot items(with image_url) -> 1688 image source validation -> profit analysis -> listing candidates`

当前不再采用“先找多平台热卖榜”的主线。  
热卖榜相关探索保留为备选研究方向，不再作为当前版本前提。


## Key Decisions

### A. Entry Decision

当前唯一主入口是“商品品类”，不是热卖榜。

这意味着：

- 用户输入一个品类词
- 系统直接去闲鱼执行搜索
- 不依赖外部热卖榜或第三方榜单来源


### B. Xianyu Market Rule

闲鱼市场扫描必须固定执行以下规则：

- 搜索指定品类
- 勾选 `超赞鱼小铺`
- 获取当前条件下的全部结果
- 按 `想要人数` 倒序排序
- 取 `Top 10`

这 10 条商品是当前版本的 `hot_items`。


### C. Source Validation Rule

上游货源当前固定使用 `1688`，并且只走 `以图搜`。

1688 流程必须固定如下：

- 使用 `hot_item.image_url`
- 将图片链接输入 1688 首页搜索框
- 不点击静态 `以图搜款`
- 使用搜索框右侧动态变成的主按钮 `图搜`
- 进入图片搜索结果页后，再附加筛选条件

1688 结果页必须固定附加筛选条件：

- `退货包运费`
- `一件代发`

当前参考结果页形态：

- `https://s.1688.com/youyuan/index.htm?tab=imageSearch&imageId=...`

这意味着：

- 第一版不再走 1688 标题搜
- 第一版不再打开 1688 详情页，只解析结果列表


### D. Top 10 Decision

当前版本只对闲鱼结果中的 `Top 10` 商品继续做后续分析。

排序规则：

- 主排序字段：`想要人数`
- 排序方向：降序

如果后面有同分处理，再补充次排序规则；当前先不扩大范围。


### E. Output Priority Decision

最终输出主语明确如下：

- 中间层保留 `hot_items`
- 最终层以 `listing_candidates` 为主

其中：

- `hot_items`
  是闲鱼 `超赞鱼小铺` 搜索结果中，按想要人数排序后的 `Top 10`
- `listing_candidates`
  是完成 1688 货源验证和利润分析后，值得上架闲鱼的商品


### F. Threshold Configuration Decision

第一版判定规则采用“阈值可调”方式，不要求频繁改代码。

至少应配置化：

- 最低利润额
- 最低利润率
- 最大竞争强度
- 最大商家盘占比
- 最大可接受风险等级


## Target Architecture

项目当前按 4 层组织。

### 1. Xianyu Market Scan

职责：按品类扫描闲鱼市场，并产出 `Top 10 hot_items`。

固定动作：

- 搜索品类
- 勾选 `超赞鱼小铺`
- 获取全部结果
- 按 `想要人数` 倒序
- 取 `Top 10`

目标输出：

- `hot_items`
- `xianyu_market`

`hot_items` 每条至少包含：

- `hot_item_id`
- `platform`
- `title`
- `price`
- `want_count`
- `seller_name`
- `image_url`
- `item_url`
- `source_snapshot`

字段含义：

- `hot_item_id`
  当前热品记录的稳定唯一标识。第一版建议直接使用闲鱼 `item_id`。
- `platform`
  数据来源平台。当前固定为 `xianyu`。
- `title`
  闲鱼商品标题，用于人工判断、后续货源搜索词生成和最终展示。
- `price`
  当前闲鱼展示售价，单位为人民币元。
- `want_count`
  闲鱼“想要”人数，是当前版本的主排序字段。
- `seller_name`
  商品卖家昵称，用于辅助判断店铺类型和商家盘特征。
- `image_url`
  闲鱼主图链接。当前是 1688 以图搜的必备输入字段，后续不能丢。
- `item_url`
  商品短链接，要求尽量去掉追踪参数。
- `source_snapshot`
  原始闲鱼搜索结果快照，用于排错和字段回溯。

`xianyu_market` 至少包含：

- `category_keyword`
- `result_count`
- `filtered_by`
- `sorted_by`
- `top_n`
- `sample_items`

字段含义：

- `category_keyword`
  本次用户输入并实际用于闲鱼搜索的品类词。
- `result_count`
  当前搜索条件下拉取到的商品总数。
- `filtered_by`
  当前固定筛选条件，第一版至少包含 `超赞鱼小铺`。
- `sorted_by`
  当前固定排序规则，第一版为 `want_count desc`。
- `top_n`
  当前最终进入后续流程的商品数量，第一版固定为 `10`。
- `sample_items`
  用于人工复核的结果样本，默认来自排序后的前若干条。


### 2. Source Validation

职责：对 `Top 10 hot_items` 用主图去 1688 以图搜找可拿货货源。

固定要求：

- 使用 1688 首页图片搜索
- 输入 `hot_item.image_url`
- 通过右侧主按钮 `图搜` 进入图片搜索结果页
- 固定筛选 `退货包运费`
- 固定筛选 `一件代发`
- 只解析结果页列表，不打开详情页

输出：

- `source_items`
- `source_resolution`

`source_item` 至少包含：

- `source_item_id`
- `source_platform`
- `title`
- `price`
- `shipping_fee`
- `item_url`
- `shop_name`
- `sales`
- `metadata`

字段含义：

- `source_item_id`
  1688 商品唯一标识。
- `source_platform`
  上游平台标识，当前固定为 `1688`。
- `title`
  1688 商品标题。
- `price`
  1688 当前供货价，单位为人民币元。
- `shipping_fee`
  1688 该商品运费；未知时允许为空或按规则补默认值。
- `item_url`
  1688 商品详情链接，只作为结果字段保留；当前流程不主动打开它。
- `shop_name`
  1688 店铺名，用于人工判断店铺质量。
- `sales`
  1688 销量或成交量字段，用于辅助判断货源稳定性。
- `metadata`
  1688 图片搜索结果原始字段和固定筛选命中信息。

`source_resolution` 至少包含：

- `hot_item_id`
- `resolved`
- `source_item_ids`
- `resolution_reason`

字段含义：

- `hot_item_id`
  对应的闲鱼热品 ID。
- `resolved`
  是否成功匹配到至少一个 1688 货源。
- `source_item_ids`
  当前匹配到的 1688 货源 ID 列表。
- `resolution_reason`
  匹配结果原因，例如 `matched_source_items`、`no_source_items_found`。


### 3. Profit Analysis

职责：对比 1688 成本和闲鱼售价，计算利润空间。

输出：

- `profit_analysis`

至少包含：

- `hot_item_id`
- `source_item_id`
- `source_cost`
- `target_xianyu_price`
- `estimated_margin`
- `estimated_margin_rate`
- `risk_flags`

字段含义：

- `hot_item_id`
  对应的闲鱼热品 ID。
- `source_item_id`
  当前采用的 1688 货源 ID。
- `source_cost`
  货源成本，至少包含供货价和必要运费后的结果。
- `target_xianyu_price`
  用于测算利润的闲鱼目标售价。第一版可直接取当前闲鱼售价或保守价格。
- `estimated_margin`
  预计利润额，单位为人民币元。
- `estimated_margin_rate`
  预计利润率。
- `risk_flags`
  风险标签列表，例如竞争高、货源弱、利润过低等。


### 4. Listing Decision

职责：输出最终值得上架闲鱼的商品。

输出：

- `listing_candidates`

每条至少包含：

- `hot_item`
- `source_item`
- `profit_analysis`
- `decision`

其中 `decision` 至少包含：

- `is_recommended`
- `reasons`
- `blocked_by`

字段含义：

- `hot_item`
  被纳入评估的闲鱼热门商品对象。
- `source_item`
  当前选定的 1688 货源对象。
- `profit_analysis`
  当前组合下的利润分析结果。
- `decision`
  最终推荐判断结果。
- `is_recommended`
  是否推荐作为上架候选。
- `reasons`
  推荐原因列表。
- `blocked_by`
  拦截原因列表；若为空表示未被规则阻断。


## Current Status

当前仓库里已经有的能力：

- 闲鱼登录态导出和校验
- 闲鱼搜索
- 上游货源基础适配能力
- 利润计算与候选摘要的一部分基础能力

当前仓库里还没有的关键能力：

- 闲鱼搜索结果里的 `超赞鱼小铺` 固定筛选
- 闲鱼结果按 `想要人数` 排序并取 `Top 10`
- 1688 固定筛选 `退货包运费 + 一件代发`
- 以当前新主链路为核心的单一 workflow


## Execution Flow

最终正确的业务执行顺序应该是：

1. 输入品类词
2. 在闲鱼搜索该品类
3. 勾选 `超赞鱼小铺`
4. 拉取全部结果
5. 按 `想要人数` 倒序并取 `Top 10`
6. 对这 `Top 10` 去 1688 找货源
7. 固定筛选 `退货包运费 + 一件代发`
8. 计算利润空间
9. 输出最终可上架商品


## Roadmap

### Phase 1: Xianyu Market Scan

目标：把“品类 -> 闲鱼 Top 10 热门商品”跑通。

计划：

- 固化闲鱼搜索入口
- 固化 `超赞鱼小铺` 筛选
- 获取全部结果
- 支持按 `想要人数` 排序
- 输出 `Top 10 hot_items`

完成标准：

- 给一个品类词，能稳定输出 `Top 10 hot_items`


### Phase 2: 1688 Source Validation

目标：给 `Top 10 hot_items` 找到可拿货的 1688 上游货源。

计划：

- 建立 1688 搜索适配层
- 固定筛选 `退货包运费 + 一件代发`
- 输出 `source_items` 和 `source_resolution`

完成标准：

- 每个 `hot_item` 都能找到货源，或明确记录无货源


### Phase 3: Profit Analysis

目标：计算每个候选的利润空间。

计划：

- 统一成本项
- 固定利润公式
- 配置化阈值

完成标准：

- 每个候选都有稳定利润分析结果


### Phase 4: Listing Decision

目标：筛出值得上架闲鱼的商品。

计划：

- 输出 `listing_candidates`
- 记录推荐原因和拦截原因
- 支持批量执行

完成标准：

- 可以稳定输出 `listing_candidates`


## Immediate Priorities

短期优先级应当是：

1. 固化闲鱼 `超赞鱼小铺` 搜索与排序链路
2. 产出按 `想要人数` 排序的 `Top 10 hot_items`
3. 接 1688 搜索与固定筛选
4. 再做利润分析和最终决策


## Success Criteria

项目进入正确方向后的判定标准：

1. 给一个品类词，能稳定拿到闲鱼 `Top 10 hot_items`
2. 每个 `hot_item` 都能找到 1688 货源或明确判定无货源
3. 能输出利润空间
4. 最终得到一批可直接用于上架决策的商品
