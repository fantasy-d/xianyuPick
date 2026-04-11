# Xianyu Tools Tasks

## Purpose

这个文档是当前执行清单。


Python环境在/opt/anaconda3/envs/mytools/

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
7. 获取 1688 结果页里的 `7天代发数量` 与 `月代发数量`
8. 按 `7天代发数量 desc -> 月代发数量 desc` 排序并取详情候选
9. 计算利润
10. 输出 `listing_candidates`


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


## Current To-Do: 1688 图搜 + SKU 导出收尾

### Current Progress

- `1688` 主流程已经切到“首页输入图片 URL -> 以图搜结果页 -> 详情页 -> 插件导出 SKU”。
- `image_url` 现在只接受合法的 `http/https` 图片 URL。
- 非法 URL 或不支持的图片后缀会直接丢弃，不再继续图搜。
- 1688 结果页排序规则已经明确并已接入代码：
  `7天代发数量 desc -> 月代发数量 desc`
- 详情候选目前固定取 `Top 3`。
- 状态文件逻辑已经接入 [run_ali1688_slow_flow.py](/Users/mac/PycharmProjects/mytools/xianyu-tools/scripts/run_ali1688_slow_flow.py)。
- 状态文件固定位置已经迁到 [storage_state.json](/Users/mac/PycharmProjects/mytools/xianyu-tools/state/ali1688/storage_state.json)，不再放 `tmp`。
- 状态文件里的 cookies 会在启动时加载到浏览器上下文，结束时会回写最新状态。
- 插件目录参数已经接入主脚本，当前默认扩展目录仍是项目内解压目录。
- 1688 插件欢迎引导层的处理逻辑已经从之前成功样本抽回到脚本里，不再只靠页面文案试错。
- 已确认 `.J_MIDDLEWARE_FRAME_WIDGET` 可能是多层叠加，必须逐层关闭到 `0`。
- 已确认 `复制sku` 的真实触发链路来自插件，而不是 1688 原生页面 DOM。
- 已确认工具栏 `copySku` 点击后，插件实际先走：
  `sendMessageToBackground({name:"copy-sku", payload:{offerId}})`
- 已确认真正打开弹窗的是插件事件：
  `copy-sku-modal`
- 已确认“复制 SKU 已打开”的稳定判定信号不是 `序号/复制导出` 文案，而是：
  - `#consign-sku-fullscreen-drawer` 变为可见
  - `#fullscreen-drawer-iframe` 的 `src` 去掉 `#hidden`
- 这套 drawer 判定逻辑已经接回主脚本。
- 当前脚本在工具栏点击失败时，已经增加插件事件兜底：
  `window.__1688_EXTENSION?.events?.emit("copy-sku-modal", { offerId })`
- 手工实测已经打通过一条完整链路：
  `复制sku -> 序号左侧全选 -> 复制导出 -> 导出Excel`
- 目标商品 `904776936832` 的手工链路已经成功下载 Excel。


### Current Problems

- 主脚本的“结构化逻辑”已经比较接近真实页面，但还没有用这版代码做一次稳定的端到端成功复跑。
- `复制sku` 打开弹层这一步存在波动。
  同一商品页上，有时点击工具栏后 drawer 会展开，有时保持隐藏态。
- 之前失败的根因已经基本定位：
  不是“按钮没点到”，而是插件弹层未从隐藏态切到展示态。
- 之前脚本有一段错误判定：
  把“是否出现 `序号/复制导出` 文案”当成成功标准。
  这会误判，因为插件弹层内容不一定能直接从主页面文本读到。
- 当前虽然已改成 drawer 判定，但还没在真实浏览器里验证“工具栏点击 + 事件兜底”这套组合是否足够稳定。
- 状态文件能带上登录态，但真实运行时仍然可能触发风控；当前策略是接受风控，但必须保证风控或引导层最终能收口，不要卡死流程。
- 插件扩展目录当前默认还指向 `tmp/1688-extension`。
  这不是状态文件问题，但从项目长期结构看，后面可能需要迁到更稳定的位置。
- 详情页导出链虽然已被手工验证，但主脚本还没有把“导出成功后的文件路径、失败时的页面状态、失败时的 HTML 快照”收口到足够稳定。


### Verified Facts

- 插件欢迎引导层是插件自己注入的，不是 1688 原生页面弹窗。
- 插件源码已经确认存在专门的新手引导事件：
  - `show-install-guide`
  - `onboarding-mode-switch`
- `show-install-guide` 是主动拉起“功能引导”的入口，不是页面自己推断出来的。
- `onboarding-mode-switch` 是当前页面是否进入 onboarding 模式的运行态开关。
- popup 里的“功能引导”按钮会显式触发：
  `sendMessageToBackground({ name: "show-install-guide" })`
- 这说明插件新手引导至少有两类入口：
  - 手动入口：用户从 popup 主动点“功能引导”
  - 自动入口：插件初始化时根据持久化状态决定是否进入 onboarding 模式
- 插件源码里已经确认存在 3 个与 onboarding 直接相关的持久化/参数标识：
  - `_1688_EXTENSION_ONBOARDING_FEATURE`
  - `_1688_EXTENSION_SHOW_GUIDANCE_REASON`
  - `pcPluginOnboardingFeature`
- 当前最稳的源码结论是：
  “正常只弹一次”主要不是靠页面 DOM，而是靠插件自身 `chrome.storage.local` 里的 onboarding 状态控制。
- 其中：
  - `_1688_EXTENSION_ONBOARDING_FEATURE`
    更像“是否仍需要 onboarding / 当前 onboarding feature 状态”
  - `_1688_EXTENSION_SHOW_GUIDANCE_REASON`
    更像“本次为什么要弹出引导”
  - `pcPluginOnboardingFeature`
    更像 URL 参数级别的强制入口，可能绕过正常的“只弹一次”路径
- `.J_MIDDLEWARE_FRAME_WIDGET` 的关闭逻辑在插件代码里已经证实：
  点关闭图标后就是把对应层从 DOM 移除。
- 失败样本里：
  `#consign-sku-fullscreen-drawer` 是 `display: none`
  且 iframe URL 带 `#hidden`
- 成功样本里：
  `#consign-sku-fullscreen-drawer` 可见
  且 iframe URL 不带 `#hidden`
- 因此后续所有自动化判定都必须优先看 drawer DOM 状态，不再优先看文案。
- `复制导出` 这一步最终要走的是菜单里的 `导出Excel`，不是单纯复制到剪贴板。
- 当前还没有从压缩 bundle 中精确定位到：
  - 自动弹引导时，究竟哪段代码读取了 `_1688_EXTENSION_ONBOARDING_FEATURE`
  - 点击 `我知道了` / `开始使用` 后，究竟哪段代码把“已看过引导”写回 storage
- 因此，页面层反复关遮罩只能治标，真正的源头仍是插件内部 onboarding 状态。


### Next Actions

#### T1 Re-run The Real End-To-End Flow With The New Drawer Logic

Purpose:

- 用当前代码再次真实跑通：
  `首页图搜 -> 结果页取 Top 3 -> 详情页 -> 复制sku -> 全选 -> 复制导出 -> 导出Excel`

Action:

- 使用固定状态文件
- 使用插件扩展
- 用当前已验证过的详情页和图片 URL 先做定点复跑
- 先验证 `904776936832`
- 再验证图搜选出来的真实候选详情页

Output:

- `summary.json`
- 每个详情页的导出状态
- 成功下载的 Excel 路径

Done When:

- 至少一个详情页通过主脚本稳定导出 Excel


#### T2 Stabilize Copy SKU Open Detection

Purpose:

- 把 `复制sku` 的打开成功判断彻底稳定下来

Action:

- 以 `drawer visible + iframe src without #hidden` 作为唯一主判断
- 工具栏点击失败时继续保留 `copy-sku-modal` 事件兜底
- 失败时固定保存：
  - 主页面 HTML
  - drawer 对应 HTML 状态
  - 关键截图

Output:

- `copy_sku_open_rule`
- `copy_sku_failure_snapshot`

Done When:

- 不再依赖 `序号/复制导出` 文案作为成功标准


#### T3 Stabilize Export Excel Step

Purpose:

- 把最后一段 `全选 -> 复制导出 -> 导出Excel` 收口

Action:

- 固定按 `序号` 左侧复选框做全选
- 固定点击 `复制导出`
- 固定选择 `导出Excel`
- 等待浏览器下载完成并保存到输出目录

Output:

- `downloaded_excel`
- `download_path`

Done When:

- 下载文件稳定落盘
- `summary` 里能记录成功路径


#### T4 Persist Failure Diagnostics

Purpose:

- 避免以后再重复人工回放同一类问题

Action:

- 导出失败时固定保存：
  - 详情页 HTML
  - drawer 可见态信息
  - iframe src
  - 截图
  - overlay close history

Output:

- `failure_bundle`

Done When:

- 任一失败样本都能离线复盘“是遮罩问题、drawer 未展开，还是导出菜单未点击成功”


#### T5 Finish Onboarding Source Trace

Purpose:

- 把插件新手引导“为什么弹、为什么只弹一次”的源码链补齐

Action:

- 定位 `show-install-guide` 的消费方
- 定位 `_1688_EXTENSION_ONBOARDING_FEATURE` 的读取点
- 定位 `_1688_EXTENSION_SHOW_GUIDANCE_REASON` 的读取点
- 定位点击 `我知道了` / `开始使用` 后的 `chrome.storage.local.set/remove` 写回点
- 验证 `pcPluginOnboardingFeature` 是否会强制重新进入 onboarding

Output:

- `onboarding_trigger_chain`
- `onboarding_storage_rule`

Done When:

- 能明确区分：
  - 手动打开引导
  - 自动弹引导
  - 只弹一次的持久化条件


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
- 新增详情增强流程时，不在结果页附加筛选条件
- 结果页需要提取 `7天代发数量` 与 `月代发数量`
- 详情增强流程按 `7天代发数量 desc -> 月代发数量 desc` 取 `Top 3` 进入详情页
- 详情增强流程需要导出每个候选详情页里的 SKU 信息，作为后续人工复核产物

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


#### P2-2 Capture Dispatch Metrics From Result Page

Purpose:

- 固定结果页排序依据所需字段

Action:

- 从图片搜索结果页提取 `7天代发数量`
- 从图片搜索结果页提取 `月代发数量`
- 统一数量字段格式，转成可排序数值

Output:

- `ali1688_dispatch_metric_rule`

Done When:

- 每条候选结果都能输出稳定可比较的代发数量字段


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


#### P2-4 Add Sales-Sorted Top3 Detail Expansion

Purpose:

- 在结果页筛选完成后，补充详情级别的 SKU 采集流程

Action:

- 从 1688 图片搜索结果页读取 `7天代发数量`
- 从 1688 图片搜索结果页读取 `月代发数量`
- 按 `7天代发数量` 倒序排序
- 如 `7天代发数量` 相同，再按 `月代发数量` 倒序排序
- 取排序后的 `Top 3`
- 保留进入详情页前的候选快照
- 输出待进入详情页的候选列表

Output:

- `detail_candidate_items`
- `detail_candidate_snapshot`

Done When:

- 每个结果页都能稳定得到按 `7天代发数量 desc -> 月代发数量 desc` 排序后的 `Top 3` 候选

Depends On:

- 已进入 1688 图片搜索结果页
- 已能提取结果页代发数量字段

Risk:

- 结果页 `7天代发数量` 与 `月代发数量` 字段可能有缺失或格式波动
- 两个字段可能存在不同文案或单位缩写


#### P2-5 Export SKU From Detail Pages Via Procurement Assistant

Purpose:

- 从 1688 详情页导出可直接复核的 SKU 信息

Action:

- 逐个打开 `detail_candidate_items`
- 在详情页点击 `1688采购助手`
- 点击 `复制SKU`
- 等待 SKU 弹窗出现
- 勾选序号左侧的全部 SKU
- 点击 `复制导出`
- 保存导出的 SKU 文件；若下载失败则至少保存弹窗文本快照和失败原因
- 记录每个详情页的导出状态

Output:

- `sku_export_files`
- `sku_export_summary`

Done When:

- 每个 `Top 3` 详情页都有成功导出的 SKU 文件，或有明确的失败记录和页面快照

Depends On:

- 已拿到按 `7天代发数量 desc -> 月代发数量 desc` 排序后的 `Top 3` 详情候选

Risk:

- `1688采购助手` 可能需要登录态或插件态
- `复制导出` 可能触发浏览器下载权限、弹窗拦截或剪贴板权限问题
- SKU 弹窗的全选控件可能不是标准 checkbox


### Phase Completion

- 已有 1688 图片搜索适配层
- 已能提取结果页 `7天代发数量` 与 `月代发数量`
- 每个 `hot_item` 都有货源结果或无货源记录
- 已能在结果页按 `7天代发数量 desc -> 月代发数量 desc` 取 `Top 3` 进入详情页
- 已能从详情页通过 `1688采购助手` 导出 SKU 信息


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
