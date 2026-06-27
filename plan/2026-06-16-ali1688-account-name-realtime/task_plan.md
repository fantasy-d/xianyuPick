# 任务计划：1688 账号名实时识别

> 计划状态：已完成

## 目标
将 1688 账号名识别从“读取状态文件中的昵称类 cookie”升级为“从已登录页面实时抓取真实用户名”，并为配置页提供稳定、低副作用、可回退的账号名展示链路。

## 当前阶段
已完成

## 目标交付物
- 1688 实时会话探测能力支持返回真实 `account_name`
- 登录刷新脚本支持在登录成功后抓取并持久化真实用户名
- 后端状态接口统一使用“实时结果 > 缓存 > 状态文件 > 标签兜底”的合并顺序
- 配置页“货源渠道号池”中的账号名展示优先显示真实用户名
- 覆盖实时探测、缓存回退和前端回显的测试用例

## 实施原则
- 不以继续扩展 cookie 名单作为主方案
- 优先从“已登录页面运行态”获取真实用户名
- 识别逻辑必须可回退、不可阻塞主登录流程
- 页面探测失败时，不影响现有“登录状态”判断
- 若浏览器 profile 被占用，应优先回退到缓存或标签，不做危险抢占

## 关键现状
- 当前 `inspect_ali1688_state_file_quick(...)` 只能从 `storage_state.json` 的 cookie 里猜名字
- 当前 `inspect_ali1688_session(...)` 只能识别会话状态，不能提取用户名
- 当前 `refresh_1688_state.py` 只导出 `cookies + origins`，不会记录真实用户名
- 用户已确认：同一 session 打开 1688 页面时能直接看到用户名

## 各阶段

### 阶段 1：现状分析与方案定界
- [x] 梳理前端展示链路
- [x] 梳理后端轻量识别链路
- [x] 梳理实时状态检测链路
- [x] 梳理登录刷新脚本链路
- [x] 检查当前 `storage_state.json` 中 cookie 与 localStorage 是否存在现成用户名
- [x] 明确根因：用户名存在于页面运行态，不存在于当前状态文件可直接消费的数据源中
- [x] 明确方案方向：实时页面抓取为主，缓存落盘为辅
- **状态：** complete

### 阶段 2：提取策略设计
- [x] 列出 1688 首页 / 搜索页 / 会员区域可见用户名的可能 DOM 选择器
- [x] 设计页面用户名提取优先级
  说明：
  - DOM 可见文本
  - 全局运行时对象
  - 内嵌 JSON / script 数据
  - 站内接口响应
- [x] 定义统一提取函数签名
  说明：
  - `extract_ali1688_account_name(page) -> dict`
  - 返回值建议包含：
    - `account_name`
    - `source`
    - `confidence`
    - `debug_meta`
- [x] 设计选择器失效后的回退策略
- [x] 定义超时预算与重试次数
- [x] 明确 profile 被占用时的降级策略
- **状态：** complete

### 阶段 3：实时会话探测能力扩展
- [x] 修改 `src/xianyu_tools/ali1688_session.py`
- [x] 在 `inspect_ali1688_session(...)` 中增加用户名提取步骤
- [x] 让返回结果新增：
  - `account_name`
  - `account_name_source`
  - `account_name_confidence`
- [x] 保证失败时不影响现有 `state / url / title` 判断
- [x] 为可能的页面结构变化加入容错日志
- **状态：** complete

### 阶段 4：登录刷新后缓存落盘
- [x] 修改 `scripts/refresh_1688_state.py`
- [x] 登录成功后主动抓取真实用户名
- [x] 设计并落盘扩展缓存文件
  说明：
  - 推荐：`session_report.json`
  - 路径建议：
    - `state/source_channels/<channel_id>/<account_id>/session_report.json`
- [x] 缓存内容至少包含：
  - `account_name`
  - `captured_at`
  - `source`
  - `state_file`
- [x] 明确缓存失效策略
- **状态：** complete

### 阶段 5：后端状态合并链路改造
- [x] 修改 `src/web_api/main.py`
- [x] 为 1688 状态报告增加统一合并函数
- [x] 定义推荐合并顺序：
  1. 实时检测返回的 `account_name`
  2. `session_report.json` 缓存
  3. `storage_state.json` cookie 昵称
  4. `account.label`
- [x] 让以下接口统一走新合并逻辑：
  - `GET /api/system/configs`
  - `POST /api/system/source_channel_status/check`
  - `GET /api/system/source_channel_login_status`
  - `GET /api/system/source_channels/active`
- [x] 保持旧字段结构不破坏前端兼容
- **状态：** complete

### 阶段 6：前端展示与交互校准
- [x] 检查 `web/app.jsx` 中账号名显示位
- [x] 将“真实用户名”和“账号备注/标签”在 UI 上做语义区分
  说明：
  - 若真实用户名已识别，显示真实用户名
  - 若为兜底值，可考虑显示轻提示，如“备注兜底”
- [x] 确认点击“检测状态”后页面能够刷新出最新真实用户名
- [x] 确认登录成功后的自动提示中优先引用真实用户名
- **状态：** complete

### 阶段 7：测试与验证
- [x] 为页面用户名提取函数补单元测试
- [x] 为后端合并顺序补单元测试
- [x] 为缓存文件读写补测试
- [x] 为接口返回真实用户名补集成测试
- [x] 完成人工回归：
  - [x] 配置页显示真实用户名
  - [x] 点击“检测状态”后真实用户名稳定更新
  - profile 被占用时仍能优雅回退
- **状态：** complete

## 风险清单
- 页面 DOM 结构可能变化，单一选择器不稳定
- 某些用户名可能只在接口请求完成后异步出现
- profile 被占用时，实时探测可能只能返回降级结果
- 若把实时探测做得过重，配置页“检测状态”体验会变慢
- 若缓存更新策略不清晰，可能出现用户名陈旧

## 待确认决策
- 实时用户名提取是抓首页、搜索页，还是会员页，哪个稳定性最高
- `session_report.json` 是否作为长期缓存真源，还是仅作为临时辅助缓存
- UI 是否要区分“真实用户名”和“备注兜底名”

## 验收标准
- 使用已有有效 1688 session 时，配置页能显示真实用户名，而不是“未识别”
- 点击“检测状态”后，`session_report.account_name` 优先更新为真实用户名
- 登录刷新成功后，不依赖 cookie 昵称也能回显真实用户名
- 页面探测失败时，系统仍能保持稳定，不影响现有登录状态检测

---
*后续开始实施前，先重新读取本目录下三份文件。*
