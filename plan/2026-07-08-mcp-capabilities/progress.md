# MCP 能力封装进度

## 2026-07-08
- 创建计划目录 `plan/2026-07-08-mcp-capabilities/`。
- 初步检查项目依赖，确认当前没有 MCP SDK。
- 初步盘点 Web API 和 OpenAPI adapter 中适合封装的能力。
- 新增 `src/xianyu_tools/mcp_server.py`，实现首版只读 MCP tools。
- 更新 `pyproject.toml`，增加 `mcp>=1.0.0,<2` 和 `xianyu-mcp` console script。
- 新增 `docs/mcp.md`，包含安装、运行和 MCP 客户端配置示例。
- 执行 `python -m pip install -e .`，安装 MCP SDK 成功，但出现 `mitmproxy` 与 `h11` 版本约束冲突提示。
- 执行 Python 编译与 `git diff --check`，通过。
- 使用 MCP Python client 完成 `initialize`、`tools/list`、`xianyu_system_status` 调用验证。
- 重新安装 editable 包生成 `xianyu-mcp` console script，并用该命令完成 `tools/list` smoke test。
- 按新需求新增 MCP tool `xianyu_start_scan_task`，支持传入 `keyword` 与单次任务 `crawl_config`，不修改系统默认配置。
- 更新 `docs/mcp.md`，补充启动扫描任务的配置示例。
- 执行 Python 编译、MCP `tools/list` schema 验证、`Task.add` monkeypatch dry run；确认新增工具可见，`crawl_config` 是可选 object，返回结构包含任务 ID 与配置快照。
- 新增 `mcp/` 配置模板，覆盖通用 MCP、Python module、OpenClaw、harness 示例。
- 新增 `scripts/install_mcp.sh` 与 `scripts/smoke_mcp.sh`，用于安装 editable 包并验证 MCP tools/list。
- 更新 `docs/mcp.md`，增加模板位置和 smoke test 说明。
