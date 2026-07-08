# MCP 能力封装调研记录

## 现有系统初步观察
- 项目是 Python 包 `xianyu-tools`，源码位于 `src/`。
- 当前 `pyproject.toml` 依赖中没有 MCP SDK。
- Web API 集中在 `src/web_api/main.py`，已有大量可复用业务端点。
- 闲管家 OpenAPI 适配器位于 `src/xianyu_tools/xianyu_adapter/publisher_v3.py`，已包含订单列表、订单详情、物流发货、修改价格等能力。
- 当前工作区有本地未跟踪配置/debug/scratch/state 文件，本计划不纳入提交。

## 候选 MCP tools
- `list_tasks`：读取任务队列。
- `get_task_detail`：读取任务详情、决策资产、货源分组。
- `list_selection_items`：读取选品管理列表。
- `sync_selection_status`：同步选品状态，低风险但会写本地状态。
- `list_orders`：查询订单列表。
- `get_order_detail`：查询订单详情。
- `ship_order`：订单物流发货，高风险，必须限制待发货状态。
- `modify_order_price`：订单改价，高风险，必须限制待付款状态。
- `get_system_status`：系统状态、token 统计等只读能力。

## 初步设计判断
- MCP 层不应直接依赖前端组件。
- 最小实现可以复用现有 Python 函数/数据库逻辑；若复用 FastAPI 路由函数，需要注意 async/sync 混用和默认参数。
- 如果引入官方 `mcp` SDK，需要更新依赖并确认目标运行环境可安装。
- 如果不引入新依赖，可实现 JSON-RPC stdio，但维护成本更高，不建议作为首选。

## 实现结果
- 使用官方 Python MCP SDK：`mcp>=1.0.0,<2`。
- 新增 stdio MCP server：`src/xianyu_tools/mcp_server.py`。
- 首版仅暴露只读/低风险工具，不暴露物流发货、修改价格等会改变外部状态的动作。
- MCP server 复用 `web_api.main` 中已有函数；导入时会执行 DB schema 自愈初始化，但不会启动 FastAPI startup worker。

## 已实现 tools
- `xianyu_system_status`
- `xianyu_list_tasks`
- `xianyu_get_task_detail`
- `xianyu_start_scan_task`
- `xianyu_list_selection_items`
- `xianyu_list_orders`
- `xianyu_get_order_detail`
- `xianyu_token_stats`

## 启动扫描任务设计
- MCP tool 复用现有 `Task.add` 与 `build_task_crawl_config_snapshot`，不新增独立任务执行路径。
- `crawl_config` 是可选对象；不传时使用系统默认商品爬取与筛选配置，传入时只作为该任务快照，不写回 `system_configs`。
- 返回值包含 `task_id`、`task_status=排队中` 和归一化后的 `crawl_config_snapshot`，便于调用方确认实际配置。

## 环境风险
- 安装 MCP SDK 时，pip 将 `h11` 升级到 `0.16.0`。
- 当前环境中的 `mitmproxy 11.0.2` 声明依赖 `h11<=0.14.0`，因此如果后续依赖 mitmproxy，建议单独创建 MCP 运行环境或重新协调依赖版本。
