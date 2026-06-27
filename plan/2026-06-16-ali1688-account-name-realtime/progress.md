# 进度日志：1688 账号名实时识别

> 计划状态：已完成

## 会话：2026-06-16

### 阶段 1：现状分析与根因确认
- **状态：** complete
- **开始时间：** 2026-06-16
- 执行的操作：
  - 读取当前 1688 轻量状态识别逻辑
  - 读取 1688 实时会话探测逻辑
  - 读取 1688 登录刷新脚本
  - 读取前端“货源渠道号池”的账号名显示逻辑
  - 检查当前 `storage_state.json` 中是否存在昵称类 cookie
  - 检查当前 `origins/localStorage` 中是否存在明显用户名键
- 关键结论：
  - 当前 session 是有效的，页面上能看到用户名
  - 当前状态文件里没有可直接复用的昵称类 cookie
  - 当前 localStorage 扫描也没有发现稳定的用户名键
  - 根因不是登录失败，而是“用户名只存在于页面运行态，当前代码没有去抓页面运行态”
- 创建/修改的文件：
  - `plan/2026-06-16-ali1688-account-name-realtime/task_plan.md`
  - `plan/2026-06-16-ali1688-account-name-realtime/findings.md`
  - `plan/2026-06-16-ali1688-account-name-realtime/progress.md`

### 阶段 2：计划建模
- **状态：** complete
- 执行的操作：
  - 将后续工作拆成提取策略设计、实时探测扩展、登录后缓存、后端状态合并、前端展示、测试验证六大阶段
  - 明确推荐方案为“实时页面抓取为主，缓存落盘为辅”
  - 补充了用户名提取优先级：
    - DOM 命中
    - 运行时对象命中
    - 页面运行态 cookie 命中
  - 明确 profile 被占用时用缓存与状态文件降级，不阻塞状态检测

### 阶段 3：实时会话探测扩展
- **状态：** complete
- 执行的操作：
  - 在 `src/xianyu_tools/ali1688_session.py` 中新增 `extract_ali1688_account_name(...)`
  - 为首页与会员页增加用户名提取尝试
  - `inspect_ali1688_session(...)` 已支持返回：
    - `account_name`
    - `account_name_source`
    - `account_name_confidence`
    - `visited_pages`
- 关键结论：
  - 用户名识别已从“静态状态文件”抬高到“页面运行态”
  - 即使提取失败，也不会影响原本的 `state/url/title` 会话判断

### 阶段 4：登录刷新缓存落盘
- **状态：** complete
- 执行的操作：
  - 修改 `scripts/refresh_1688_state.py`
  - 登录成功后补抓真实用户名
  - 新增 `session_report.json` 落盘，缓存真实用户名与抓取时间

### 阶段 5：后端合并链路改造
- **状态：** complete
- 执行的操作：
  - 在 `src/web_api/main.py` 中新增：
    - `build_ali1688_session_report_path(...)`
    - `load_ali1688_session_report_cache(...)`
    - `save_ali1688_session_report_cache(...)`
    - `merge_ali1688_session_report(...)`
  - 统一 1688 会话报告的合并顺序为：
    - 实时结果
    - `session_report.json`
    - `storage_state.json`
    - 账号标签
  - `GET /api/system/configs`
  - `POST /api/system/source_channel_status/check`
  - `GET /api/system/source_channel_login_status`
  - `GET /api/system/source_channels/active`
    已统一切到新合并逻辑

### 阶段 6：前端展示与交互校准
- **状态：** complete
- 执行的操作：
  - 检查 `web/app.jsx` 中 1688 账号名显示位
  - 将“真实账号名”与“账号备注”拆开显示，避免把备注误当成真实用户名
  - 当页面回退到备注兜底时，增加轻提示说明当前展示并非实时识别结果
  - 登录成功后的自动提示改为优先引用真实用户名
- 关键结论：
  - 前端展示语义已经与后端合并链路对齐
  - 用户能直接区分“实时识别出的账号名”和“配置里手填的备注”

### 阶段 7：测试与验证
- **状态：** in_progress
- 执行的操作：
  - 为后端合并顺序、缓存文件读写、接口返回真实用户名补充测试
  - 新增 `tests/test_ali1688_session.py`，覆盖：
    - `normalize_account_name(...)`
    - `looks_like_real_account_name(...)`
    - `extract_ali1688_account_name(...)` 的 DOM 命中与无效 DOM 文案过滤 + cookie 回退
  - 本地执行：
    - `PYTHONPATH=src PYTHONPYCACHEPREFIX=/tmp python3 -m unittest tests.test_source_channels -v`
    - `PYTHONPATH=src /opt/anaconda3/envs/mytools/bin/python -m unittest tests.test_ali1688_session -v`
  - 结果：
    - `tests.test_source_channels`：`17/17` 通过
    - `tests.test_ali1688_session`：`4/4` 通过
  - 语法检查：
    - `PYTHONPATH=src PYTHONPYCACHEPREFIX=/tmp python3 -m py_compile tests/test_source_channels.py src/web_api/main.py src/xianyu_tools/ali1688_session.py scripts/refresh_1688_state.py`
    - `PYTHONPATH=src /opt/anaconda3/envs/mytools/bin/python -m py_compile tests/test_ali1688_session.py src/xianyu_tools/ali1688_session.py`
  - 已重启本地 `uvicorn` 服务，当前运行的是最新代码
- 待继续：
  - 验证 profile 被占用场景下的优雅回退
  - 结合“遇到滑块或风控”结果继续校准 1688 状态判定策略

### 阶段 7：人工联调补充（2026-06-17）
- **状态：** in_progress
- 执行的操作：
  - 使用当前本地 `http://127.0.0.1:8000/` 页面进入“系统设置 -> 货源渠道号池”
  - 实际展开 1688 渠道卡片，确认配置页已展示：
    - `真实账号名：tb4884575_2012`
    - `识别来源：runtime_cookie:__cn_logon_id__`
  - 手动点击一次“检测状态”按钮，观察检测后的页面回显
- 当前结果：
  - 真实账号名展示链路已经打通，不再回退为“未识别”
  - 点击“检测状态”后，真实账号名仍稳定保持为 `tb4884575_2012`
  - 但本次检测返回的会话状态被判定为“遇到滑块或风控”，说明“账号名识别”与“状态判定”已经解耦，后续应单独优化风控判定策略

### 阶段 7：人工联调补充（2026-06-24）
- **状态：** in_progress
- 执行的操作：
  - 在最新本地服务上再次进入“系统设置 -> 货源渠道号池”
  - 实际展开 `1688 货源渠道` 卡片并复核账号名展示
  - 刷新页面后重新进入同一卡片，确认账号名回显链路不会因为刷新丢失
  - 为 `profile_locked` 场景新增自动测试，覆盖：
    - 被占用时状态文案保持“浏览器配置被占用”
    - 账号名继续回退使用缓存中的真实用户名
    - 不会把被占用场景的检测结果覆写回 `session_report.json`
- 当前结果：
  - 页面当前稳定展示：
    - `真实账号名：tb4884575_2012`
    - `识别来源：runtime_cookie:__cn_logon_id__`
  - 说明实时识别结果已经成功写回统一会话报告，并能在后续回显中继续生效
  - `tests.test_source_channels` 当前已提升为 `18/18` 通过，其中包含新增的 `profile_locked` 回退保护
  - 本轮仍未单独补做“profile 被占用”场景的专项回归，因此阶段状态继续保持 `in_progress`

### 阶段 7：状态合并与会员页识别补强（2026-06-25）
- **状态：** complete
- 执行的操作：
  - 重新核对 `src/xianyu_tools/ali1688_session.py`、`src/web_api/main.py`、`web/app.jsx` 当前实现，确认：
    - `member.1688.com/member/myalibaba.htm` 已加入“已登录会员页”识别
    - `profile_locked` 场景前端已允许继续展示已知账号身份
  - 补充回归测试：
    - `test_merge_ali1688_session_report_does_not_let_stale_cache_override_live_login`
  - 修正 `merge_ali1688_session_report(...)`：
    - 不再让缓存中的旧 `is_logged_in=false` 覆盖当前 `storage_state.json` 已确认有效的登录态
  - 重启本地 `uvicorn` 服务，使最新识别逻辑生效
  - 实际调用接口验证：
    - `GET /api/system/source_channels/active`
    - `POST /api/system/source_channel_status/check`
- 当前结果：
  - `GET /api/system/source_channels/active` 已返回：
    - `is_usable: true`
    - `is_logged_in: true`
    - `account_name: tb4884575_2012`
    - `account_name_source: runtime_cookie:__cn_logon_id__`
  - `POST /api/system/source_channel_status/check` 已返回：
    - `meta.state: member`
    - `url: https://member.1688.com/member/myalibaba.htm`
    - `title: 会员管理`
    - `status_text: 登录正常`
    - `account_name: tb4884575_2012`
  - 说明“1688 首页被拒绝但会员页仍已登录”的真实场景已被正确识别，不再误判成“未检测到可用搜索态”
  - 本计划至此完成闭环，可视为已验收

## 当前结论
- 这项需求不能再靠扩展 cookie 名单解决。
- 必须把识别链路抬高到“已登录页面实时抓取真实用户名”。
- 当前实现已经完成后端闭环与前端展示语义对齐，但还需要一次真实会话联调来确认具体用户名选择器在现网页面中的命中率。

---
*本文件用于记录会话进度、阶段变化和测试结果。*
