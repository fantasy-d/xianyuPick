# 发现与决策：1688 账号名实时识别

> 计划状态：已完成

## 背景
- 用户要求把 `1688` 账号名识别改成“从已登录页面实时抓取真实用户名”。
- 本轮目标是：
  - 先分析现状与根因
  - 再创建独立计划
- 本轮不直接实现代码改动。

## 现状梳理

### 前端展示链路
- 系统设置页“货源渠道号池”中的账号名展示位于：
  - `web/app.jsx`
- 当前展示逻辑：
  - 优先显示 `currentSourceAccount.session_report.account_name`
  - 其次显示 `currentSourceAccount.label`
  - 最后回退为 `未识别`

### 后端轻量识别链路
- 1688 快速识别函数位于：
  - `src/web_api/main.py`
  - `inspect_ali1688_state_file_quick(...)`
- 当前仅从 `storage_state.json` 中读取：
  - `cookies`
  - `origins`
- 当前“登录有效性”判断依赖 cookie：
  - `cookie2`
  - `_m_h5_tk`
  - `_m_h5_tk_enc`
  - `ali_apache_id`
  - `cna`
- 当前“账号名”提取依赖 cookie：
  - `tracknick`
  - `_w_tb_nick`
  - `loginId`
  - `cn`

### 后端实时状态链路
- 1688 实时会话探测位于：
  - `src/xianyu_tools/ali1688_session.py`
  - `inspect_ali1688_session(...)`
- 该函数当前只返回：
  - `state`
  - `url`
  - `title`
  - `user_data_dir`
  - `profile_directory`
- 它目前只负责判断：
  - 是否跳到登录页
  - 是否遇到滑块
  - 是否出现搜索框
- 它**不会**读取页面中的用户昵称，也不会返回 `account_name`。

### 登录刷新脚本链路
- 1688 登录刷新脚本位于：
  - `scripts/refresh_1688_state.py`
- 当前脚本会：
  - 拉起带持久用户目录的 Chrome
  - 完成登录/预热
  - 调用 `context.storage_state()`
  - 把结果导出为 `storage_state.json`
- 目前导出的内容只有：
  - `cookies`
  - `origins`
- 它**不会**额外抓取并保存“页面上可见的真实用户名”。

## 已验证事实

### 事实 1：当前 session 是有效的
- 用户明确反馈：
  - 用当前 session 打开 1688，页面上能看到自己的用户名。
- 当前系统也能判断：
  - `登录正常`
- 说明当前问题不是“session 失效”，而是“账号名提取层级不对”。

### 事实 2：当前状态文件中没有昵称类 cookie
- 已检查文件：
  - `state/source_channels/ali1688/ali1688-account-1/storage_state.json`
- 该文件中存在登录有效 cookie：
  - `cookie2`
  - `_m_h5_tk`
  - `_m_h5_tk_enc`
  - `cna`
- 但没有当前提取逻辑依赖的昵称类 cookie：
  - `tracknick`
  - `_w_tb_nick`
  - `loginId`
  - `cn`

### 事实 3：当前状态文件中的 localStorage 也没有明显用户名键
- 已扫描 `origins/localStorage` 中疑似键名：
  - `nick`
  - `user`
  - `member`
  - `account`
  - `login`
  - `name`
- 当前未发现直接可用的命名字段。

## 根因结论
- 1688 页面能显示用户名，并不等于用户名保存在 `storage_state.json` 里。
- 当前实现的问题本质是：
  - 只做了“状态文件级”的轻量识别
  - 没做“已登录页面运行态”的真实用户名抓取
- 因此出现了：
  - 登录有效可判断
  - 页面上能看到用户名
  - 程序却拿不到 `account_name`

## 设计方向判断

### 正确方向
- 要拿到真实 1688 用户名，必须增加“浏览器实时抓取”链路。
- 推荐识别优先级：
  1. 已登录页面 DOM 中的用户名
  2. 页面运行时对象 / 内嵌 JSON / JS 全局变量中的用户名
  3. 站内接口响应中的用户名
  4. `storage_state.json` 中的昵称类 cookie
  5. 账号备注/账号标签兜底

### 不推荐方向
- 继续只扩展 cookie 名单
  - 原因：当前 session 已证明能显示用户名，但状态文件里没有对应昵称字段
  - 继续赌 cookie 名单，成功率不稳定
- 只靠 localStorage 扫描
  - 原因：当前样本已验证没有明显命名键
  - 作为辅助手段可以保留，但不应作为主方案

## 方案选型建议

### 方案 A：在实时状态检测中直接抓用户名
- 修改点：
  - `src/xianyu_tools/ali1688_session.py`
  - `src/web_api/main.py`
- 做法：
  - 在 `inspect_ali1688_session(...)` 成功识别到已登录搜索态后
  - 继续读取页面中的用户名
  - 随 `session_result` 一起返回
- 优点：
  - 最符合“从已登录页面实时抓取真实用户名”
  - 不依赖状态文件里是否保存昵称
- 风险：
  - 页面结构可能变
  - 需要更多页面探测选择器和超时控制

### 方案 B：在登录刷新脚本成功后顺手抓用户名并写入状态旁路缓存
- 修改点：
  - `scripts/refresh_1688_state.py`
  - `src/web_api/main.py`
- 做法：
  - 登录成功后，在导出 `storage_state.json` 之前或之后抓一次页面用户名
  - 将其写入单独 JSON 或并入扩展状态文件
- 优点：
  - 首次登录后就能稳定回显
  - 页面普通轮询成本较低
- 风险：
  - 仍需要定义缓存真源
  - 若用户名变更或账号切换，缓存可能变旧

### 方案 C：A + B 组合
- 建议作为最终方案：
  - B 负责“登录完成后尽快落盘缓存”
  - A 负责“检测状态时可重新校准真实用户名”
- 这样既满足实时性，也减少页面每次都深探测的成本。

## 关键约束
- 不能因为读取用户名而破坏现有登录态。
- 不能让实时检测过重，导致配置页明显卡顿。
- 需要处理 `profile_locked` 情况：
  - 用户正在使用同一个 Chrome 配置目录时，实时探测可能拿不到页面控制权。
- 需要为失败路径保留稳定回退：
  - 真实用户名失败时，至少显示账号备注/标签。

## 实现建议
- 在 `src/xianyu_tools/ali1688_session.py` 内新增：
  - 页面用户名提取函数
  - 多选择器 / 多来源回退策略
- 建议新增能力：
  - `extract_ali1688_account_name(page) -> str`
  - `inspect_ali1688_session(...)` 返回 `account_name`
- 建议在 `scripts/refresh_1688_state.py` 中同步增加：
  - 登录成功后读取 `account_name`
  - 输出到扩展状态缓存，例如：
    - `state/source_channels/<channel>/<account>/session_report.json`
- 后端接口读取顺序建议：
  1. 实时检测结果中的 `account_name`
  2. 扩展状态缓存中的 `account_name`
  3. `storage_state.json` 中的 cookie 昵称
  4. 配置里的账号备注/标签

## 测试建议
- 单元测试：
  - 选择器命中时能提取用户名
  - 所有选择器失效时回退为空字符串
  - 后端最终 report 合并顺序正确
- 集成测试：
  - 登录成功后状态接口返回真实用户名
  - 关闭页面后仍能从缓存回显上一次抓到的真实用户名
- 人工验证：
  - 配置页点击“检测状态”后，账号名更新为真实用户名
  - 重新登录后，真实用户名能更新

## 本轮结论
1. 当前问题不是 session 无效，而是“用户名只存在于已登录页面运行态，不在 `storage_state.json` 中”。
2. 要满足需求，必须新增“已登录页面实时抓取真实用户名”能力。
3. 推荐最终采用：
   - 实时页面抓取为主
   - 登录后缓存落盘为辅
   - 状态文件 cookie 识别继续作为轻量兜底
4. 当 `profile_directory` 正被登录浏览器占用时，状态检测不应强行抢占浏览器环境；应返回“浏览器配置被占用”，同时继续回退展示缓存中的真实账号名。
5. `profile_locked` 场景下不应把本次失败态覆写回 `session_report.json`，避免把已有的真实用户名缓存污染掉。

## 补充发现（2026-06-25）

6. 1688 的“已登录”并不总是体现在搜索页。
   - 实际验证中，`https://www.1688.com/` 可能先跳到阿里系风控拒绝页。
   - 但同一会话继续访问 `https://member.1688.com/member/myalibaba.htm` 时，页面标题仍可稳定落在 `会员管理`。
   - 因此“会员页已登录”必须单独识别，不能只依赖首页搜索框命中。

7. `session_report.json` 中的旧布尔状态不能高优先级覆盖当前态。
   - 真实复现中，缓存里残留的 `is_logged_in=false` 会把当前 `storage_state.json` 已确认有效的登录态压成未登录。
   - 合并策略应遵循：
     - 实时检测布尔值优先
     - 若无实时结果，当前 `storage_state.json` 的有效性至少不能被旧缓存降级

8. 当前 1688 账号名识别链路已经稳定依赖真实运行态 cookie。
   - 最新接口返回的账号名来源为：
     - `runtime_cookie:__cn_logon_id__`
   - 说明这条链路在“会员页已登录、首页被拒绝”的场景下仍然成立。

## 相关文件
- `web/app.jsx`
- `src/web_api/main.py`
- `src/xianyu_tools/ali1688_session.py`
- `scripts/refresh_1688_state.py`
- `state/source_channels/ali1688/ali1688-account-1/storage_state.json`

---
*本文件只记录分析、约束与决策，不包含执行指令。*
