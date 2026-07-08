# MCP 能力封装计划

## 目标
将现有系统中适合被外部 Agent 调用的能力封装为 MCP tools，优先做到可本地运行、可配置、低侵入，不改动现有 Web 端业务行为。

## 边界与假设
- 不把整个 Web UI 改造成 MCP。
- MCP server 应作为独立入口，复用现有业务模块或 Web API 数据访问逻辑。
- 首批 tools 以只读/低风险能力为主；会改变外部状态的能力必须显式命名并保留业务校验。
- 不提交 `tests/` 目录内容。

## 阶段
1. 调研现有能力与依赖
   - 状态：complete
   - 验证：列出候选 tools、依赖策略、入口设计。

2. 设计 MCP server 架构
   - 状态：complete
   - 验证：明确 stdio 入口、工具命名、输入输出 schema、配置方式。

3. 实现首批 MCP tools
   - 状态：complete
   - 验证：本地命令可列出/调用 tools。

4. 加入运行说明与客户端配置示例
   - 状态：complete
   - 验证：文档说明如何在 Claude/Codex/其他 MCP 客户端中配置。

5. 校验与提交
   - 状态：complete
   - 验证：Python 编译通过，必要的 smoke test 通过，git diff 只包含目标文件。

6. 增加 MCP 启动扫描任务能力
   - 状态：complete
   - 验证：`tools/list` 能看到 `xianyu_start_scan_task`；调用时可传入 `keyword` 与可选 `crawl_config`；返回排队任务 ID 与本次任务配置快照。

7. 补齐外部 Agent 快速接入材料
   - 状态：complete
   - 验证：提供通用 MCP 配置模板、OpenClaw/harness 示例、安装脚本和 smoke test 脚本；模板 JSON 可解析，smoke test 能列出 tools。
