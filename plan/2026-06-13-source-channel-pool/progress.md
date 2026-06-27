# 进度日志：货源渠道号池

> 计划状态：已完成

## 会话：2026-06-13

### 阶段 1：范围确认与现状梳理
- **状态：** complete
- **开始时间：** 2026-06-13
- 执行的操作：
  - 读取 `planning-with-files-zh` 技能说明
  - 检查项目根目录是否已有旧计划文件
  - 确认不能继续复用根目录计划文件，需单独隔离
  - 检索 1688 Session、系统配置读写、多账号配置相关代码入口
  - 建立新的 `plan/` 目录规划约定
- 创建/修改的文件：
  - `plan/README.md`
  - `plan/2026-06-13-source-channel-pool/task_plan.md`
  - `plan/2026-06-13-source-channel-pool/findings.md`
  - `plan/2026-06-13-source-channel-pool/progress.md`

### 阶段 2：计划建模
- **状态：** complete
- 执行的操作：
  - 将“货源渠道号池”拆成配置模型、后端抽象、1688 接入、前端扩展、流程接入、测试迁移等阶段
  - 明确不与旧 `openapi` 多账号配置混合
  - 明确首期以 `1688` 为主，但结构上按多渠道设计
  - 补充目标配置草案、后端接口草案、函数拆分建议、前端交互草案
  - 补充实现顺序建议和首期边界说明
- 创建/修改的文件：
  - `plan/2026-06-13-source-channel-pool/task_plan.md`
  - `plan/2026-06-13-source-channel-pool/findings.md`
  - `plan/2026-06-13-source-channel-pool/progress.md`

### 阶段 3：配置与页面打通
- **状态：** complete
- 执行的操作：
  - 在 `src/xianyu_tools/config.py` 新增 `source_channels` 配置读取接口
  - 在 `src/xianyu_tools/config.py` 继续补充渠道/账号选择接口，统一激活账号解析逻辑
  - 在 `src/web_api/main.py` 新增渠道池归一化、1688 状态快速检测和主动检测接口
  - 在 `src/web_api/main.py` 新增当前激活渠道运行时查询接口，供任务前校验和前端复用
  - 扩展 `/api/system/configs` 的 GET/POST，加入 `source_channels`
  - 将 `/api/sys/status` 的 `1688_login` 改为读取激活 1688 账号的快速状态
  - 在 `web/app.jsx` 的 `SystemSettingsView` 中新增“货源渠道号池”卡片
  - 接入渠道/账号切换、新增、删除、状态检测和保存 payload
  - 在 `scripts/run_full_pipeline.py` 中让 1688 慢流程读取激活账号的 `state_file`
  - 在 `scripts/run_full_pipeline.py` 中增加激活 1688 账号的运行前校验，不可用时直接阻止任务
  - 在 `scripts/dashboard.py` 中同步改为读取激活 1688 账号的 `state_file`
  - 在 `scripts/run_keyword_pipeline.py` 中改为读取激活 1688 账号的 `user_data_dir / profile_directory`
  - 在 `scripts/refresh_1688_state.py` 中补充参数化能力，支持按账号传入 `state_file / user_data_dir / profile_directory`
  - 在 `src/web_api/main.py` 中新增渠道账号登录触发和登录状态查询接口
  - 在 `web/app.jsx` 中为 `ali1688` 账号补充“立即登录/重新登录”按钮和轮询状态逻辑
  - 在 `web/app.jsx` 中补充渠道能力分支，按 `channel_type` 控制专属字段和状态按钮显示
  - 在 `web/app.jsx` 中补充 `profile_directory` 配置输入项
  - 在 `scripts/run_ali1688_slow_flow.py` 中将默认 `state_file` 收口到激活 1688 账号运行时配置
  - 在 `src/web_api/main.py` 中新增运行时路径剥离与托管逻辑，保存配置时不再把 1688 路径类字段作为持久配置真源
  - 在 `src/xianyu_tools/config.py` 中新增渠道账号运行时路径生成能力
  - 在 `web/app.jsx` 中移除 1688 路径类字段编辑入口，配置页改为只维护账号语义字段和登录态
  - 在 `scripts/run_full_pipeline.py`、`scripts/run_keyword_pipeline.py` 以及若干 1688 调试脚本中统一切换到系统托管运行时路径
- 创建/修改的文件：
  - `src/xianyu_tools/config.py`
  - `src/web_api/main.py`
  - `web/app.jsx`
  - `scripts/run_full_pipeline.py`
  - `scripts/dashboard.py`
  - `scripts/run_keyword_pipeline.py`
  - `scripts/refresh_1688_state.py`
  - `scripts/run_ali1688_slow_flow.py`
  - `scripts/debug_1688_download.py`
  - `scripts/probe_1688_ui.py`
  - `scripts/debug_1688_raw_data.py`
  - `plan/2026-06-13-source-channel-pool/progress.md`

### 阶段 6：多渠道扩展骨架
- **状态：** complete
- 执行的操作：
  - 在前端显式定义首期渠道枚举：`ali1688 / taobao / pdd / custom`
  - 将渠道能力抽象为登录触发、状态检测、`state_file`、`user_data_dir`、`profile_directory` 等能力开关
  - 让系统配置页按渠道能力渲染专属字段，避免所有渠道共用一套 1688 字段
  - 为未接入的渠道保留账号池、激活账号和备注骨架，并在操作区显示“待接入”
- 创建/修改的文件：
  - `web/app.jsx`

### 阶段 7：流程接入与业务生效
- **状态：** complete
- 执行的操作：
  - 明确首期运行时回退策略：激活 1688 账号无效时阻止抓取链路继续执行
  - 将 `run_ali1688_slow_flow.py` 的默认登录态来源收口到激活渠道账号配置，减少脚本级硬编码回退
  - 追加新的计划决策：后续要进一步把 `state_file / user_data_dir / profile_directory / cookies_source` 从配置层收回到系统托管运行时层
  - 将 1688 运行时路径规则固定为基于 `channel_id + account_id` 的系统托管目录
  - 将主链路、登录触发接口和调试脚本统一改为通过运行时解析获取 `state_file / user_data_dir / profile_directory`
  - 将配置持久化时的 `source_channels` 结构收敛为账号语义字段，避免把运行时路径写回数据库真源
- 创建/修改的文件：
  - `scripts/run_ali1688_slow_flow.py`
  - `scripts/run_full_pipeline.py`
  - `scripts/run_keyword_pipeline.py`
  - `scripts/refresh_1688_state.py`
  - `scripts/debug_1688_download.py`
  - `scripts/probe_1688_ui.py`
  - `scripts/debug_1688_raw_data.py`
  - `src/web_api/main.py`
  - `src/xianyu_tools/config.py`
  - `web/app.jsx`
  - `plan/2026-06-13-source-channel-pool/task_plan.md`
  - `plan/2026-06-13-source-channel-pool/findings.md`
  - `plan/2026-06-13-source-channel-pool/progress.md`

### 阶段 8：校验、测试与迁移
- **状态：** complete
- 执行的操作：
  - 根据最新决策更新计划基线：旧配置不再保留，后续统一以新配置结构为唯一真源
  - 清理 `src/xianyu_tools/config.py` 中 `database.json / llm.json / openapi.json` 的 legacy 文件回退入口
  - 调整 `get_openapi_config()`，当前仅接受多账号新结构，缺少 `accounts` 时直接返回空配置
  - 清理 `src/xianyu_tools/xianyu_adapter/publisher_v3.py` 对物理 `config/openapi.json` 的运行时回退，统一改为读取统一配置
  - 同步更新 `tests/test_config.py`，将旧单账号结构断言改为“缺少多账号新结构时返回空配置”
  - 将 `PublisherV3` 的默认配置路径名从 `config/openapi.json` 改为中性占位，避免继续暴露旧配置入口语义
  - 清理 `tests/test_publisher.py` 中关于 `openapi.json` 的旧注释，统一改为“模拟统一配置读取”
  - 新增 `tests/test_source_channels.py`，覆盖货源渠道号池的核心纯函数校验
  - 为配置默认结构补测试，确认配置层不会持久化 `state_file / user_data_dir / profile_directory / cookies_source`
  - 为激活 1688 账号运行时解析补测试，确认运行时目录按 `channel_id + account_id` 自动生成
  - 为 `normalize_source_channels_config(...)` 补测试，确认后端回显前会补全运行时字段
  - 为 `strip_source_channel_runtime_fields(...)` 补测试，确认保存前会剥离运行时字段与 `session_report`
  - 为 `inspect_ali1688_state_file_quick(...)` 补测试，覆盖有效登录识别与状态文件缺失两类结果
  - 为 `src/xianyu_tools/config.py` 与 `src/web_api/main.py` 补 `from __future__ import annotations`，以便在当前 Python 3.9 校验环境中完成基础导入测试，同时不改变 3.11 运行行为
  - 在真实本地服务上完成接口级联调，验证 `/api/system/configs`、`/api/system/source_channels/active` 与 `/api/sys/status`
  - 使用伪造运行时路径字段执行一次真实保存，再次读取回包与本地 `config/config.json`，确认服务端会剥离运行时字段并恢复为系统托管路径
  - 完成联调后恢复原始系统配置，避免污染当前使用中的账号配置
  - 触发真实 `1688` 登录流程，确认 `POST /api/system/source_channel_login_trigger` 会把登录脚本指向 `state/source_channels/ali1688/ali1688-account-1/storage_state.json`
  - 通过登录日志确认浏览器登录、业务域名预热与状态导出均完成，且状态文件已写入托管目录
  - 再次读取 `/api/system/source_channel_login_status`、`/api/system/source_channels/active` 与 `/api/sys/status`，确认系统已识别托管状态文件且 `1688_login` 变为“有效”
  - 在系统设置页首次展开“货源渠道号池”卡片时，确认页面已回显“登录正常”“账号名：未识别”和新的最近检测时间
  - 尝试继续做刷新后二次页面展开验证时，受到当前 in-app browser 的本地页面安全策略限制，后续页面级自动点击未继续执行
  - 收紧激活渠道/账号解析逻辑，当前只会选择“启用中的渠道 + 启用中的账号”，不会再把禁用账号误判为激活账号
  - 调整 `get_active_ali1688_runtime_config()`，当没有可用账号时不再回退伪造运行时路径，而是返回明确的 `error_message`
  - 为 `/api/system/source_channel_status/check`、`/api/system/source_channel_login_status`、`/api/system/source_channel_login_trigger` 补充“未配置可用账号 / 已停用”类明确反馈
  - 收紧 `scripts/run_full_pipeline.py` 的 1688 前置校验，当前若没有可用账号会直接阻止主流程继续执行
  - 为“禁用账号自动跳过”“无可用账号时返回明确错误”“不可用账号报告结构稳定”补充自动测试
  - 在 `web/app.jsx` 中收紧货源渠道登录态轮询，仅对支持会话检测的渠道执行轮询，避免自定义渠道把 1688 登录态误显示到本地未保存账号上
  - 在 `src/web_api/main.py` 中为未接入会话检测的渠道统一返回“待接入”占位报告，不再把非 `ali1688` 渠道回退到 1688 状态检查
  - 在 `src/web_api/main.py` 中为静态页面资源追加 `Cache-Control: no-store` 等响应头，避免 in-app browser 持续使用旧版 `app.jsx` 缓存
  - 通过本地接口联调确认 `/` 与 `/app.jsx?v=SOURCE_CHANNEL_POOL_V7` 已返回无缓存响应头，并确认自定义渠道状态检测接口会稳定返回“待接入”
- 创建/修改的文件：
  - `tests/test_source_channels.py`
  - `tests/test_config.py`
  - `src/xianyu_tools/config.py`
  - `src/xianyu_tools/xianyu_adapter/publisher_v3.py`
  - `src/web_api/main.py`
  - `web/app.jsx`
  - `scripts/run_full_pipeline.py`
  - `plan/2026-06-13-source-channel-pool/task_plan.md`
  - `plan/2026-06-13-source-channel-pool/progress.md`

### 阶段 8：人工回归补齐（2026-06-24）
- **状态：** complete
- 执行的操作：
  - 重新启动本地 `uvicorn` 服务，并在 `http://127.0.0.1:8000/` 中进入“系统设置 -> 货源渠道号池”
  - 实际展开 `1688 货源渠道` 卡片，确认当前页面稳定回显：
    - `当前激活账号：1688 账号 1`
    - `登录正常`
    - `真实账号名：tb4884575_2012`
    - `识别来源：runtime_cookie:__cn_logon_id__`
  - 实际点击一次“新增账号”，确认：
    - 页面会立即切换到新建账号页签
    - “当前激活账号”区域不会把未登录的新账号自动加入并勾选
  - 点击“放弃更改”恢复现场，再刷新页面并重新进入“货源渠道号池”
  - 刷新后再次确认当前激活账号、真实用户名和登录状态仍然正确回显
  - 通过本地接口再次校验：
    - `GET /api/system/source_channels/active`
    - `GET /api/sys/status`
  - 确认运行时读取到的仍是：
    - `channel_id=ali1688`
    - `account_id=ali1688-account-1`
    - 系统托管 `state/source_channels/.../storage_state.json`
    - 全局状态 `1688_login=有效`
- 创建/修改的文件：
  - `plan/2026-06-13-source-channel-pool/task_plan.md`
  - `plan/2026-06-13-source-channel-pool/progress.md`
  - `plan/2026-06-13-source-channel-pool/findings.md`

### 阶段 9：交付与后续演进收口（2026-06-24）
- **状态：** complete
- 执行的操作：
  - 基于已完成实现与回归结果，收口“货源渠道号池”的字段结构、默认值和运行时边界说明
  - 明确该配置与 `openapi.accounts` 的职责分离：
    - `openapi.accounts` 只负责闲鱼发布侧
    - `source_channels.channels[*].accounts[*]` 只负责货源抓取侧
  - 明确与 1688 抓取链路的衔接方式：
    - 抓取前统一经 `/api/system/source_channels/active` 或配置解析函数读取激活账号
    - 运行时路径由系统按 `channel_id + account_id` 生成，不从前端配置直接取值
  - 汇总后续演进方向，保留“同渠道账号轮换 / 定时健康检查 / 渠道路由策略”作为后续项
- 创建/修改的文件：
  - `plan/2026-06-13-source-channel-pool/task_plan.md`
  - `plan/2026-06-13-source-channel-pool/progress.md`
  - `plan/2026-06-13-source-channel-pool/findings.md`

## 测试结果
| 测试 | 输入 | 预期结果 | 实际结果 | 状态 |
|------|------|---------|---------|------|
| 旧计划隔离检查 | 检查根目录 `task_plan.md / findings.md / progress.md` | 不覆盖旧计划 | 已确认新计划改存 `plan/` | 通过 |
| 配置入口定位 | 检查 `SystemSettingsView` 与 `/api/system/configs` | 找到系统配置落点 | 已定位 | 通过 |
| 1688 Session 入口定位 | 检查 `run_ali1688_slow_flow.py` / `inspect_ali1688_session.py` | 找到可接入状态检查点 | 已定位 | 通过 |
| 多账号模式参考 | 检查 `normalize_openapi_multi_account(...)` | 找到可复用模式 | 已定位 | 通过 |
| 计划细化检查 | 检查计划是否具备直接开工粒度 | 补齐字段、接口、函数、交互和顺序 | 已补齐 | 通过 |
| Python 语法检查 | `py_compile` 检查后端与脚本 | 无语法错误 | 通过临时 pycache 已通过 | 通过 |
| 1688 登录触发接口语法检查 | `py_compile` 检查 `src/web_api/main.py` 与 `scripts/refresh_1688_state.py` | 无语法错误 | 已通过 | 通过 |
| 运行时默认配置语法检查 | `py_compile` 检查 `run_ali1688_slow_flow.py / refresh_1688_state.py / main.py / config.py` | 无语法错误 | 已通过 | 通过 |
| 路径托管改造语法检查 | `py_compile` 检查 `config.py / main.py / run_ali1688_slow_flow.py / refresh_1688_state.py` | 无语法错误 | 已通过 | 通过 |
| 路径托管链路语法检查 | `py_compile` 检查主链路与 1688 调试脚本 | 无语法错误 | 已通过 | 通过 |
| 旧硬编码路径残留检查 | `rg` 检查 `state/ali1688/storage_state.json` 与 `profiles/ali1688_chrome_profile` | 主链路不再残留旧硬编码路径 | 已确认无残留匹配 | 通过 |
| 货源渠道号池纯函数测试 | `python3 -m unittest tests.test_source_channels -v` | 配置默认结构、激活账号运行时解析、归一化、保存剥离、无可用账号提示与 1688 状态检查均通过 | 9 个测试全部通过 | 通过 |
| 货源渠道号池语法检查 | `python3 -m py_compile tests/test_source_channels.py src/xianyu_tools/config.py src/web_api/main.py` | 无语法错误 | 已通过 | 通过 |
| 货源渠道号池读取联调 | `GET /api/system/configs`、`GET /api/system/source_channels/active`、`GET /api/sys/status` | 能返回 `source_channels`、激活账号运行时配置与系统状态 | 已返回托管路径、激活账号与 `1688_login=无效` | 通过 |
| 货源渠道号池保存剥离联调 | 伪造 `state_file / user_data_dir / profile_directory / cookies_source / session_report` 后调用 `POST /api/system/configs` | 服务端保存时剥离运行时字段，读取时重新注入托管路径 | 已验证伪造字段未持久化，`config/config.json` 只保留账号语义字段，且原配置已恢复 | 通过 |
| 货源渠道号池登录触发联调 | `POST /api/system/source_channel_login_trigger` + 登录日志 + `GET /api/system/source_channel_login_status` | 登录脚本写入托管 `state_file`，系统能识别新状态文件 | 已写入 `state/source_channels/ali1688/ali1688-account-1/storage_state.json`，`is_logging_in=false` 后状态变为“登录正常” | 通过 |
| 货源渠道系统状态联调 | `GET /api/sys/status` | 托管状态文件生效后 `1688_login` 应切换为“有效” | 已返回 `1688_login=有效` | 通过 |
| 系统设置页状态回显联调 | 首次展开系统设置页中的“货源渠道号池”卡片 | 页面显示当前账号登录状态与最近检测时间 | 已看到“登录正常”“账号名：未识别”与新的检测时间 | 通过 |
| 系统设置页刷新后二次展开联调 | 刷新后重新进入系统设置并再次展开“货源渠道号池”卡片 | 再次确认页面回显稳定 | 进入系统设置成功，但后续展开动作被当前 in-app browser 本地页面安全策略拦截 | 阻塞 |
| 静态资源无缓存联调 | `GET /`、`GET /app.jsx?v=SOURCE_CHANNEL_POOL_V7` | 页面与脚本返回 `no-store`，避免浏览器继续复用旧 bundle | 已确认两个入口都返回 `Cache-Control: no-store, no-cache, must-revalidate` | 通过 |
| 自定义渠道待接入联调 | `POST /api/system/source_channel_status/check`，传入 `channel_type=custom` | 返回“待接入”，且不再回退成 1688 登录态 | 已返回 `status_text=待接入`、`error_message=当前渠道暂未接入会话状态检测` | 通过 |
| JSX 静态解析检查 | 使用本地 Node/Babel 检查 `web/app.jsx` | 能完成 JSX 解析 | 当前环境无 `node`，未执行 | 阻塞 |
| 新配置读取收口测试 | `python3 -m pytest tests/test_config.py tests/test_publisher.py -q` | 统一配置读取、Publisher 初始化与新结构断言通过 | 16 个测试全部通过 | 通过 |
| 旧入口痕迹清理校验 | `rg -n "openapi\\.json|database\\.json|llm\\.json|config/openapi.json"` | 代码与测试中不再残留误导性旧入口引用 | 仅计划进度记录中保留本次清理说明 | 通过 |

## 错误日志
| 时间戳 | 错误 | 尝试次数 | 解决方案 |
|--------|------|---------|---------|
| 2026-06-13 | 项目根目录已有旧计划文件，若继续复用会与历史任务混写 | 1 | 新增 `plan/` 目录，并为新任务建立独立子目录 |

## 五问重启检查
| 问题 | 答案 |
|------|------|
| 我在哪里？ | 阶段 8：已完成配置模型、后端读写、1688 状态检测、登录触发、多渠道扩展骨架和主流程首轮接入 |
| 我要去哪里？ | 阶段 8：继续补状态检测与联调验证，完成剩余人工回归项 |
| 目标是什么？ | 将 1688 账号 Session 状态配置化为“货源渠道号池”，支持多渠道、多账号 |
| 我学到了什么？ | 现有代码已有 OpenAPI 多账号模式和 1688 Session 检查入口，可直接借鉴；实际检测需要区分“轻量回显”和“主动检测”两层；运行时入口如果不统一，配置化会被硬编码绕过；多渠道 UI 也不能把 1688 字段硬塞给所有渠道；路径和浏览器目录这类字段不应暴露给配置层长期维护 |
| 我做了什么？ | 已完成 `source_channels` 的配置读写、状态检测接口、登录触发接口、系统设置页卡片、多渠道能力分支，以及主抓取链路、旧 dashboard、关键词流水线对激活 1688 账号配置的透传与校验；同时补齐了配置默认结构、激活账号运行时解析、归一化与保存剥离逻辑的自动测试，并完成了真实接口级联调、保存回写验证以及 1688 登录触发写入托管状态文件的实测闭环 |

---
*后续开始真正实现前，先重新读取本目录下三份文件。*
