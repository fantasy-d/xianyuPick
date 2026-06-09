# xianyu-tools

gemini --resume                           │
│  a39eef35-af98-41f9-b32b-aeee5a3696d5

一个面向选品的自动化工具链。

## 🚀 H5 可视化管理系统 (推荐)

本项目现在提供了一个高审美的 H5 选品决策中枢，支持多端适配、任务队列管理和历史结果持久化。

### 1. 数据库配置

系统使用 MySQL 存储任务。请按照以下步骤配置：

1.  进入 `config/` 目录。
2.  参考 `database.json.example` 创建 `database.json`。
3.  填入您本地的 MySQL 连接信息（系统会自动为您创建 `xianyu_tools` 数据库）。

### 2. 快速启动

在 macOS 下，直接在 Finder 中 **双击** 根目录下的：
- `start_h5.command`

系统将自动启动后台服务并打开浏览器访问 `http://localhost:8000`。

---

## 5 分钟命令行上手

1. 在闲鱼按关键词搜索商品。
2. 勾选 `超赞鱼小铺`。
3. 按 `想要人数` 倒序取前 `10` 条热品。
4. 保留每条热品的主图 `image_url`。
5. 用主图去 `1688` 做以图搜。
6. 在 `1688` 图片搜索结果页勾选：
   - `退货包运费`
   - `一件代发`
   - `1件代发包邮`
7. 解析 `1688` 结果列表，筛掉与原始闲鱼关键词不相关的候选。
8. 用闲鱼售价和 `1688` 成本做利润测算。
9. 输出最终 `Excel + JSON` 结果。

当前主线已经工程化到一个统一入口脚本：

- [run_keyword_pipeline.py](/Users/mac/PycharmProjects/mytools/xianyu-tools/scripts/run_keyword_pipeline.py)

## 5 分钟上手

如果你只想尽快跑通一次，按这 4 步做：

1. 准备闲鱼登录态文件：
   [xianyu_state.json](/Users/mac/PycharmProjects/mytools/xianyu-tools/xianyu_state.json)
2. 用专用目录手动登录一次 `1688`：
   [ali1688_chrome_profile](/Users/mac/PycharmProjects/mytools/xianyu-tools/profiles/ali1688_chrome_profile)
3. 先检查 `1688` 当前状态：

```bash
PYTHONPATH=src python3 scripts/inspect_ali1688_session.py \
  --user-data-dir ./profiles/ali1688_chrome_profile \
  --browser-channel chrome \
  --launch-arg=--start-maximized
```

4. 直接跑完整流程：

```bash
PYTHONPATH=src python3 scripts/run_keyword_pipeline.py \
  --keyword 纸巾 \
  --state-file ./xianyu_state.json \
  --browser-channel chrome \
  --ali1688-user-data-dir ./profiles/ali1688_chrome_profile \
  --launch-arg=--start-maximized
```

跑完后优先看：

- [summary.json](/Users/mac/PycharmProjects/mytools/xianyu-tools/outputs/纸巾_20260404/summary.json)
- [filtering_report.xlsx](/Users/mac/PycharmProjects/mytools/xianyu-tools/outputs/纸巾_20260404/filtering_report.xlsx)

## 当前主流程

### 输入

- 一个闲鱼关键词，例如：`纸巾`、`蚊帐`
- 一份可用的闲鱼登录态文件：
  [xianyu_state.json](/Users/mac/PycharmProjects/mytools/xianyu-tools/xianyu_state.json)
- 一套可用的 `1688` 专用浏览器目录：
  [ali1688_chrome_profile](/Users/mac/PycharmProjects/mytools/xianyu-tools/profiles/ali1688_chrome_profile)

### 输出

统一输出到：

- `outputs/搜索词_YYYYMMDD/`

例如：

- [纸巾_20260404](/Users/mac/PycharmProjects/mytools/xianyu-tools/outputs/纸巾_20260404)

同一天同一个关键词再次运行时，直接覆盖同目录。

## 目录结构

### 关键代码

- [run_keyword_pipeline.py](/Users/mac/PycharmProjects/mytools/xianyu-tools/scripts/run_keyword_pipeline.py)
  统一入口，串整个流程。
- [xianyu_market_scan.py](/Users/mac/PycharmProjects/mytools/xianyu-tools/src/xianyu_tools/xianyu_market_scan.py)
  闲鱼热品扫描，输出 `Top 10 hot_items`。
- [run_ali1688_slow_flow.py](/Users/mac/PycharmProjects/mytools/xianyu-tools/scripts/run_ali1688_slow_flow.py)
  `1688` 浏览器图搜流程、主体切换、结果页筛选。
- [ali1688_session.py](/Users/mac/PycharmProjects/mytools/xianyu-tools/src/xianyu_tools/ali1688_session.py)
  `1688` 会话预检。
- [source_resolution.py](/Users/mac/PycharmProjects/mytools/xianyu-tools/src/xianyu_tools/source_resolution.py)
  货源候选收敛、过滤、匹配结果。
- [profit_analysis.py](/Users/mac/PycharmProjects/mytools/xianyu-tools/src/xianyu_tools/profit_analysis.py)
  利润测算。
- [listing_decision.py](/Users/mac/PycharmProjects/mytools/xianyu-tools/src/xianyu_tools/listing_decision.py)
  最终上架候选判定。
- [export_pipeline_excel.py](/Users/mac/PycharmProjects/mytools/xianyu-tools/scripts/export_pipeline_excel.py)
  导出中文 Excel。

### 关键设计文档

- [xianguanjia_openapi_guide.md](/Users/mac/PycharmProjects/mytools/xianyu-tools/docs/xianguanjia_openapi_guide.md)
  闲管家开放平台（Goofish OpenAPI）接口规范及本项目的多规格 SKU 自愈、自动分类匹配规则。
- [source_adapter_contract.md](/Users/mac/PycharmProjects/mytools/xianyu-tools/docs/source_adapter_contract.md)
  货源适配器契约规范。

### 关键目录

- [src/xianyu_tools](/Users/mac/PycharmProjects/mytools/xianyu-tools/src/xianyu_tools)
  核心实现。
- [scripts](/Users/mac/PycharmProjects/mytools/xianyu-tools/scripts)
  命令行入口。
- [profiles](/Users/mac/PycharmProjects/mytools/xianyu-tools/profiles)
  专用浏览器目录。
- [outputs](/Users/mac/PycharmProjects/mytools/xianyu-tools/outputs)
  最终结果目录。

## 环境要求

- Python `>= 3.11`
- 已安装 `Google Chrome`
- 已安装 `Playwright`

项目元信息在：

- [pyproject.toml](/Users/mac/PycharmProjects/mytools/xianyu-tools/pyproject.toml)

## 安装

### 1. 安装 Python 依赖

```bash
python3 -m pip install -e .
python3 -m pip install playwright openpyxl
python3 -m playwright install chromium
```

### 2. 准备闲鱼登录态

如果没有现成的 [xianyu_state.json](/Users/mac/PycharmProjects/mytools/xianyu-tools/xianyu_state.json)，可以导出：

```bash
PYTHONPATH=src python3 scripts/export_xianyu_state.py \
  --output-file ./xianyu_state.json \
  --browser-channel chrome \
  --prompt-for-login
```

检查状态文件：

```bash
PYTHONPATH=src python3 scripts/inspect_xianyu_state.py \
  --state-file ./xianyu_state.json \
  --strict
```

### 3. 准备 1688 专用浏览器目录

当前专用目录是：

- [ali1688_chrome_profile](/Users/mac/PycharmProjects/mytools/xianyu-tools/profiles/ali1688_chrome_profile)

如需手动打开并登录：

```bash
/Applications/Google\ Chrome.app/Contents/MacOS/Google\ Chrome \
  --user-data-dir=/Users/mac/PycharmProjects/mytools/xianyu-tools/profiles/ali1688_chrome_profile \
  https://www.1688.com
```

说明：

- 这是项目专用目录，不是你平时 Chrome 的默认目录。
- 它不会覆盖你的个人书签和默认浏览器环境。

## 一条命令跑完整流程

```bash
PYTHONPATH=src python3 scripts/run_keyword_pipeline.py \
  --keyword 纸巾 \
  --state-file ./xianyu_state.json \
  --browser-channel chrome \
  --ali1688-user-data-dir ./profiles/ali1688_chrome_profile \
  --launch-arg=--start-maximized
```

默认行为：

- 闲鱼最多抓 `2` 页。
- 过滤掉 `image_url` 为空的热品。
- 取 `Top 10 hot_items`。
- 每个热品只尝试前 `3` 个图片主体。
- 复用同一个 `1688` 浏览器会话。
- 相邻两个热品之间随机等待 `30s-60s`。
- 结果直接写到：
  - `outputs/搜索词_YYYYMMDD/`

## 统一入口参数

统一入口帮助：

```bash
PYTHONPATH=src python3 scripts/run_keyword_pipeline.py --help
```

常用参数：

- `--keyword`
  闲鱼关键词。
- `--state-file`
  闲鱼登录态文件。
- `--browser-channel`
  一般用 `chrome`。
- `--ali1688-user-data-dir`
  `1688` 专用浏览器目录。
- `--output-root`
  输出根目录，默认 `outputs`。
- `--output-dir`
  手动指定本次输出目录。
- `--xianyu-max-pages`
  闲鱼抓取页数。
- `--top-n`
  保留多少条热品。
- `--max-subjects`
  每个热品最多尝试多少个图片主体。
- `--min-wait-seconds`
  两个热品之间最小等待秒数。
- `--max-wait-seconds`
  两个热品之间最大等待秒数。
- `--limit-per-item`
  每个热品最多保留多少条 `1688` 候选。
- `--packaging-cost`
- `--platform-fee-rate`
- `--payment-fee-rate`
- `--aftersale-reserve-rate`
  利润测算参数。
- `--min-margin`
- `--min-margin-rate`
- `--max-risk-flags`
  最终候选筛选阈值。
- `--launch-arg=...`
  额外浏览器启动参数，可重复传入。

## 输出文件说明

每次完整运行后，输出目录里会包含：

- `hot_items.json`
- `ali1688_session.json`
- `result_url_map.json`
- `source_bundle.json`
- `profit_analysis.json`
- `listing_candidates.json`
- `summary.json`
- `filtering_report.xlsx`
- `manifest.json`
- `logs/`
- `browser_runs/`

### hot_items.json

闲鱼热品列表。

每条热品当前核心字段：

- `hot_item_id`
- `title`
- `price`
- `want_count`
- `seller_name`
- `area`
- `image_url`
- `item_url`

### ali1688_session.json

本次运行前 `1688` 专用会话预检结果。

典型状态：

- `search`
- `slider`
- `login`
- `profile_locked`
- `unknown`

说明：

- `slider` 不再被当成硬阻塞，会继续进入正式流程处理验证码。
- `login/profile_locked/unknown` 才是更强的阻塞信号。

### source_bundle.json

包含三部分：

- `hot_items`
- `source_items`
- `source_resolution`

其中：

- `source_items`
  是 `1688` 以图搜结果页解析到的货源候选。
- 同时保留“已保留”和“已过滤”的候选。

### profit_analysis.json

利润测算结果。

当前无歧义字段：

- `estimated_margin`
- `gross_margin_rate`
- `cost_profit_rate`

口径：

- `毛利率 = (售价 - 成本) / 售价`
- `成本利润率 = (售价 - 成本) / 成本`

当前利润对比基准是：

- `hot_item.price`

### listing_candidates.json

最终上架候选。

当前第一版规则：

- 每个 `hot_item` 最多输出 `1` 条最终候选。
- 从该热品的 `Top 5 source_items` 中选利润最优的一条。

### summary.json

给人快速看的汇总文件，包含：

- 闲鱼市场统计
- 各阶段数量
- `resolution_reason_counts`
- `blocked_reason_counts`
- 最终推荐的候选摘要

### filtering_report.xlsx

最终人工查看用的中文 Excel。

当前主要 sheet：

- `汇总`
- `筛选总览`
- `闲鱼热品`
- `货源匹配结果`
- `1688货源候选`
- `利润测算`
- `最终上架候选`

Excel 当前已经做了这些规范：

- 中文 sheet 名
- 中文字段名
- 表头底色
- 放大字体
- `1688货源候选` 中保留被过滤项
- `过滤原因` 使用中文

## 当前规则

### 闲鱼侧

- 搜索原始关键词。
- 勾选 `超赞鱼小铺`。
- 按 `想要人数` 倒序。
- 先过滤 `image_url` 为空。
- 再取前 `10` 条。
- 当前暂不额外评估“竞争情况”。

### 1688 侧

- 只用 `image_url` 做以图搜。
- 不再走标题搜。
- 不打开商品详情页。
- 只解析结果列表。
- 每条热品最多尝试前 `3` 个图片主体。
- 结果页固定勾选：
  - `退货包运费`
  - `一件代发`
  - `1件代发包邮`
- 若当前主体结果都不相关，则尝试切换到下一个主体。
- 若没有更多主体，则记为无有效货源。

### 相关性过滤

`1688` 候选会校验是否与原始闲鱼关键词相关。

例如：

- 闲鱼关键词是 `蚊帐`
- `1688` 候选标题却是 `桌子`

这类候选不会丢失，而是会保留在原始候选表里，并标记为：

- `候选状态 = 已过滤`
- `过滤原因 = 商品标题与原始搜索词不相关`

### 利润测算

当前默认成本项：

- `1688` 商品价格
- 运费
- 包装成本
- 平台费
- 支付费
- 售后预留

当前第一版里：

- 运费默认按 `0.0`
- `source_item.price <= 0` 直接丢弃

## 当前已知限制

1. `1688` 会话仍然存在波动

- 专用 profile 在同一会话内可用性较好。
- 但跨重启后首页仍可能回到验证码页或登录链路。

2. `1688` 图搜结果不稳定

- 某些图片会退化为非预期页面。
- 某些主体结果全都不相关。

3. 验证码处理并非 100% 成功

- 目前已有滑块/验证码处理逻辑。
- 但不是每次都能稳定自动通过。

4. 结果依赖当次页面状态

- 同一关键词不同时间跑，`1688` 候选可能波动。
- 最终推荐结果不是严格稳定不变的。

## 调试入口

### 只跑闲鱼热品

```bash
PYTHONPATH=src python3 scripts/run_xianyu_hot_items.py \
  --keyword 纸巾 \
  --state-file ./xianyu_state.json \
  --browser-channel chrome
```

### 只检查 1688 会话

```bash
PYTHONPATH=src python3 scripts/inspect_ali1688_session.py \
  --user-data-dir ./profiles/ali1688_chrome_profile \
  --browser-channel chrome \
  --launch-arg=--start-maximized
```

### 运行测试

```bash
python3 -m pytest
```

## 常见阻塞

### 1. `ali1688_session.json` 显示 `slider`

含义：

- `1688` 首页进了验证码页

当前处理方式：

- 统一入口不会直接把它当硬失败
- 会继续进入正式图搜流程，由现有验证码适配逻辑继续处理

### 2. `ali1688_session.json` 显示 `login`

含义：

- 当前专用浏览器目录没有稳定可用的 `1688/淘宝` 登录态

处理方式：

- 手动用专用目录打开并登录一次：

```bash
/Applications/Google\ Chrome.app/Contents/MacOS/Google\ Chrome \
  --user-data-dir=/Users/mac/PycharmProjects/mytools/xianyu-tools/profiles/ali1688_chrome_profile \
  https://www.1688.com
```

### 3. `ali1688_session.json` 显示 `profile_locked`

含义：

- 专用浏览器目录当前正被另一个 Chrome 实例占用

处理方式：

- 关闭那个正在占用同一目录的 Chrome 窗口后再跑

### 4. 最终结果里 `ali1688_parse_error` 偏多

常见原因：

- 图片没有真正进入 `1688` 图搜结果页
- 页面状态异常
- 图搜过程中被打回非预期页面

先看：

- `browser_runs/`
- `logs/03_ali1688_browser_session.log`

### 5. `1688货源候选` 里大多是 `已过滤`

含义：

- 候选取到了
- 但标题和原始闲鱼关键词不相关

这不等于没拿到数据，而是说明：

- 图搜候选质量不足
- 或当前图片主体选得不对

## 当前定位

这个项目当前已经不是单纯的闲鱼搜索脚本，而是一条可落盘、可回看、可批量运行的选品流水线。

当前最推荐的使用方式就是：

1. 准备好闲鱼登录态。
2. 准备好 `1688` 专用浏览器目录并登录。
3. 用 [run_keyword_pipeline.py](/Users/mac/PycharmProjects/mytools/xianyu-tools/scripts/run_keyword_pipeline.py) 直接跑关键词。
4. 优先看：
   - `summary.json`
   - `filtering_report.xlsx`

如果后面继续扩展，优先级最高的还是：

- 提升 `1688` 会话稳定性
- 提高图片主体切换成功率
- 降低 `ali1688_parse_error`
