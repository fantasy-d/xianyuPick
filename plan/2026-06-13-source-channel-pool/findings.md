# 发现与决策：货源渠道号池

> 计划状态：已完成

## 需求
- 在“系统参数配置”中新增一项配置能力，名称为“货源渠道号池”。
- 该能力要把 `1688` 账号的 Session 状态做成配置。
- 需要满足：
  - 区分不同渠道
  - 每个渠道支持多账号
  - 每个账号可以展示/识别 Session 状态
- 本轮只要求创建详细计划，不直接实现。
- 从现在开始，新计划统一存放到 `plan/` 目录下，不能与旧计划冲突。

## 代码现状

### 系统配置页
- 前端系统设置页入口在：
  - `web/app.jsx`
  - 组件：`SystemSettingsView`
- 当前系统设置页已经包含：
  - LLM API 配置
  - 闲鱼 OpenAPI 多账号配置
  - 商品爬取与筛选配置
- 页面保存逻辑已经统一走：
  - `GET /api/system/configs`
  - `POST /api/system/configs`

### 现有多账号配置可复用模式
- 后端已存在 OpenAPI 多账号归一化逻辑：
  - `src/web_api/main.py`
  - `normalize_openapi_multi_account(...)`
  - `get_openapi_account(...)`
- 这套模式可以直接借鉴到“货源渠道号池”：
  - 配置归一化
  - 激活账号选择
  - 账号列表回显

### 1688 Session 相关入口
- 当前代码里 1688 会话主要围绕以下内容：
  - `state/ali1688/storage_state.json`
  - `profiles/ali1688_chrome_profile`
  - `scripts/run_ali1688_slow_flow.py`
  - `scripts/inspect_ali1688_session.py`
- `scripts/run_ali1688_slow_flow.py` 的默认常量：
  - `DEFAULT_ALI1688_STATE_FILE = "state/ali1688/storage_state.json"`
  - `DEFAULT_ALI1688_USER_DATA_DIR = profiles/ali1688_chrome_profile`
- 当前 1688 慢流程会主动处理 cookie 注入与登录/风控识别。
- 当前主流程显然存在“登录态依赖”，但没有“系统配置里的多账号渠道池”。

### 当前系统状态区
- 左侧边栏底部已有全局状态：
  - `1688_login`
- 该状态来源仍是系统级单值，不是“渠道 -> 账号”的细粒度结构。
- 如果后续要和“货源渠道号池”联动，这里可能要从单值升级为聚合态。

## 设计推断
- “货源渠道号池”不应塞进现有 `openapi` 配置：
  - `openapi` 面向闲鱼发布与会员配置
  - 渠道池面向货源抓取与渠道登录态
- 更合理的结构是新增系统配置段，例如：
  - `source_channels`
  - 或 `channel_pool`
- 更合理的配置边界是：
  - 配置层只保留账号语义字段
  - 运行时层托管状态文件路径与浏览器目录
- 配置层级建议：
  - 渠道列表
  - 渠道下账号列表
  - 渠道级激活账号或优先级
  - 每个账号的登录状态与派生结果

## 细化结构建议

### 建议顶层字段
- `source_channels`

### 建议顶层结构
- `active_channel_id`
- `channels`

### 建议渠道字段
- `channel_id`
- `channel_type`
- `label`
- `enabled`
- `active_account_id`
- `accounts`

### 建议账号字段
- `account_id`
- `label`
- `enabled`
- `notes`

### 建议运行时字段
- `state_file`
- `user_data_dir`
- `profile_directory`
- `cookies_source`

说明：
- 以上字段应由系统根据 `channel_id + account_id` 自动生成与维护
- 不建议继续作为用户可编辑字段长期暴露在配置页
- 页面更应关注“账号是否登录、识别到的账号名、最近检测结果”

### 建议状态字段
- `session_report.is_usable`
- `session_report.account_name`
- `session_report.status_text`
- `session_report.last_checked_at`
- `session_report.error_message`
- `session_report.meta`

## 接口草案建议
- 继续使用：
  - `GET /api/system/configs`
  - `POST /api/system/configs`
- 建议新增：
  - `POST /api/system/source_channel_status/check`
  - `GET /api/system/source_channels/active`

## 函数拆分建议

### config.py
- `get_source_channels_raw_config()`
- `get_source_channel_config(channel_id=None)`
- `get_source_channel_account(channel_id=None, account_id=None)`

### main.py
- `normalize_source_channels_config(raw_cfg)`
- `normalize_source_channel(raw_channel, idx)`
- `normalize_source_channel_account(raw_account, channel_type, idx)`
- `get_source_channel(raw_cfg, channel_id=None)`
- `get_source_channel_account(raw_cfg, channel_id=None, account_id=None)`
- `inspect_source_channel_account(channel_type, account_cfg)`

## 风险与边界
- `1688` 的会话“来源”本身不止一种：
  - 存储态文件
  - 持久化浏览器目录
  - 运行时新登录
- 如果配置结构只支持其中一种，后续容易再次返工。
- 如果把 `state_file / user_data_dir / profile_directory` 暴露给用户编辑，会把实现细节泄漏到配置层，后续改路径规则时迁移成本会很高。
- 首期若直接做“多账号自动轮换”，业务复杂度会显著上升。
- 更稳妥的首期方案应是：
  - 先做“多渠道、多账号配置与状态可视化”
  - 再做“单渠道激活账号接入实际流程”

## 首期建议边界
- 支持多渠道结构，但首期只内建 `ali1688`
- 支持多账号配置，但首期运行时只使用“激活账号”
- 支持状态检测和状态展示，但不做自动账号轮换
- 支持扩展字段，但不实现跨渠道统一登录编排
- 配置页只关注账号和登录状态，不让用户手工维护状态文件路径与浏览器目录

## 前端布局建议
- 卡片标题：`货源渠道号池`
- 一级区域：渠道切换条
- 二级区域：当前渠道基础信息
- 三级区域：账号列表编辑区
- 四级区域：Session 状态展示区
- 状态区建议展示：
  - 状态点
  - 状态文案
  - 账号名
  - 最近检查时间
  - 错误文案

## 运行时接入建议
- 不再让业务代码直接硬编码读取：
  - `state/ali1688/storage_state.json`
  - `profiles/ali1688_chrome_profile`
- 也不应让前端配置直接长期持有这些路径
- 改为：
  - 先从系统配置取得当前激活渠道与账号
  - 再由系统内部统一解析该账号的 `state_file / user_data_dir / profile_directory`
  - 最后把解析结果透传到慢流程脚本或运行模块

## 技术决策
| 决策 | 理由 |
|------|------|
| 新计划独立存放在 `plan/` 子目录 | 用户明确要求避免与旧计划冲突 |
| 货源渠道号池按“渠道 -> 多账号”设计 | 直接满足用户需求，并且利于后续扩展 |
| 优先借鉴 OpenAPI 多账号模式 | 现有代码里已有成熟的多账号归一化逻辑 |
| 首期重点打通 `1688` | 现有主抓取链路首先依赖它 |
| 先做状态配置化，再考虑轮换调度 | 避免一开始把范围做得过大 |
| 配置页不暴露 1688 运行时路径字段 | 路径和浏览器目录属于系统内部实现细节，应由系统托管 |
| 旧配置不再保留，统一切到新配置结构 | 用户已明确不再需要旧配置兼容路径，后续实现以新结构为唯一真源 |

## 当前结论
1. 渠道池继续支持“多渠道 + 多账号”的新结构。
2. `state_file / user_data_dir / profile_directory` 仍由系统托管，不再作为旧配置兼容点保留。
3. 后续清理代码时，可以主动移除遗留的旧配置回退逻辑，而不需要为它们保留长期兼容行为。
4. “当前激活账号”应只展示并勾选已登录成功、可实际投入抓取链路的账号；新建但未登录的账号只在账号页签中编辑，不自动进入激活池。
5. 页面刷新后的系统设置回显应以服务端返回的 `source_channels` 为准，不能依赖前端临时 state 残留。
6. 1688 实际抓取前的账号读取已经统一收口到激活账号解析链路，当前 API 与页面回归都指向 `ali1688-account-1` 的系统托管运行时目录。

## 相关文件
- `web/app.jsx`
- `src/web_api/main.py`
- `src/xianyu_tools/config.py`
- `scripts/run_ali1688_slow_flow.py`
- `scripts/inspect_ali1688_session.py`

---
*本文件只记录发现与决策，不写入执行指令。*
