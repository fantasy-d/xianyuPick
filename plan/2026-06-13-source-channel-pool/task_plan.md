# 任务计划：货源渠道号池配置化

> 计划状态：已完成

## 目标
在“系统参数配置”中新增“货源渠道号池”能力，把 `1688` 等货源渠道的账号 Session 状态做成可配置、可区分渠道、可支持多账号的系统级配置；同时为后续渠道扩展预留统一结构，不与现有“闲鱼 OpenAPI 多账号配置”冲突。

## 当前阶段
已完成

## 目标交付物
- 系统配置页新增“货源渠道号池”卡片
- 后端 `/api/system/configs` 支持读取和保存渠道池配置
- 1688 渠道支持多账号 Session 状态回显
- 实际抓取链路可读取“激活渠道 / 激活账号”
- 货源渠道账号配置层仅保留账号语义字段，状态文件与浏览器目录由系统托管生成
- 配置体系统一切到新结构，后续不再保留旧配置兼容分支

## 目标配置草案

```json
{
  "source_channels": {
    "active_channel_id": "ali1688",
    "channels": [
      {
        "channel_id": "ali1688",
        "channel_type": "ali1688",
        "label": "1688 货源渠道",
        "enabled": true,
        "active_account_id": "ali1688-account-1",
        "accounts": [
          {
            "account_id": "ali1688-account-1",
            "label": "1688 账号 1",
            "enabled": true,
            "notes": "",
            "session_report": {
              "is_usable": false,
              "account_name": "",
              "status_text": "未检测",
              "last_checked_at": "",
              "error_message": ""
            }
          }
        ]
      }
    ]
  }
}
```

## 实施原则
- 不复用 `openapi.accounts` 结构存放货源账号，避免语义污染
- 页面展示名允许中文，配置字段统一英文
- 运行时使用“渠道 + 激活账号”组合定位会话，不直接在业务代码里写死 `state/ali1688/storage_state.json`
- 首期先支持 `ali1688`，但结构必须允许后续新增 `taobao / pdd / custom`
- `session_report` 视为运行时派生字段，但允许通过 `/api/system/configs` 返回给前端回显
- 配置保存与状态检测分离，避免“点保存就隐式改状态”的副作用
- 配置层只保留账号语义字段，不暴露 `state_file / user_data_dir / profile_directory / cookies_source` 给用户编辑
- 渠道账号运行时路径必须由系统按 `channel_id + account_id` 自动生成并维护

## 各阶段

### 阶段 1：范围确认与现状梳理
- [x] 确认本轮目标是“先使用 planning with files 创建详细计划”
- [x] 确认配置名称为“货源渠道号池”
- [x] 确认能力边界
  说明：
  - 需要区分不同渠道
  - 每个渠道支持多个账号
  - 每个账号要能展示/识别 Session 状态
- [x] 定位现有 1688 Session 与系统配置相关代码入口
- [x] 记录不与旧计划冲突的落盘方案
- **状态：** complete

### 阶段 2：配置模型设计
- [x] 设计新的系统配置段
  说明：建议新增顶层 `source_channels` 或 `channel_pool` 配置段，不并入 `openapi`
- [x] 明确最终字段名
  说明：建议最终使用 `source_channels`，因为语义比 `channel_pool` 更直接
- [x] 设计配置命名
  说明：前端展示名为“货源渠道号池”，后端字段名保持英文、可扩展
- [x] 设计层级结构
  说明：
  - 渠道列表 `channels`
  - 每个渠道包含 `channel_id / channel_type / label / enabled`
  - 每个渠道包含多个账号 `accounts`
  - 每个账号包含 `account_id / label / enabled / notes`
- [x] 设计状态字段
  说明：
  - `session_report.is_usable`
  - `session_report.account_name`
  - `session_report.last_checked_at`
  - `session_report.status_text`
  - `session_report.error_message`
- [x] 设计账号来源字段
  说明：
  - 配置层保留 `notes`
  - 运行时层内部维护 `state_file / user_data_dir / profile_directory / cookies_source`
  - `notes`
- [x] 明确配置层与运行时层边界
  说明：
  - 配置层只关心账号身份、备注、启停、激活关系
  - 运行时层负责状态文件路径、浏览器目录、Profile 目录和 cookie 来源
- [x] 设计激活策略字段
  说明：
  - 渠道级 `active_account_id`
  - 全局 `active_channel_id`
- [x] 设计渠道类型枚举
  说明：
  - `ali1688`
  - `taobao`（预留）
  - `pdd`（预留）
  - `custom`（预留）
- [x] 设计默认值与空配置策略
  说明：
  - 默认创建一个 `1688` 渠道
  - 默认渠道下可无账号
  - 无账号时页面允许保存，但应显示“未配置账号”
- [x] 设计兼容策略
  说明：
  - 货源渠道号池统一使用新结构
  - 旧配置不再作为长期兼容目标保留
- [x] 明确首期不保存的派生字段
  说明：
  - `session_report` 可在内存和接口返回中存在
  - 是否持久化到 `system_configs` 需要单独决定，优先不作为长期真源
- **状态：** complete

### 阶段 3：后端能力抽象
- [x] 在 `src/xianyu_tools/config.py` 增加新配置读取接口
- [x] 增加建议接口
  说明：
  - `get_source_channels_raw_config()`
  - `get_source_channel_config(channel_id=None)`
  - `get_source_channel_account(channel_id=None, account_id=None)`
- [x] 在 `src/web_api/main.py` 的 `/api/system/configs` GET/POST 中纳入“货源渠道号池”
- [x] 提取“渠道账号归一化”函数
  说明：参考现有 `normalize_openapi_multi_account(...)` 的做法，新增渠道池归一化函数
- [x] 提取建议函数
  说明：
  - `normalize_source_channels_config(raw_cfg)`
  - `normalize_source_channel(raw_channel, idx)`
  - `normalize_source_channel_account(raw_account, channel_type, idx)`
- [x] 提取“渠道账号选择”函数
  说明：按 `channel_id + account_id` 获取当前账号配置
- [x] 提取建议函数
  说明：
  - `get_source_channel(raw_cfg, channel_id=None)`
  - `get_source_channel_account(raw_cfg, channel_id=None, account_id=None)`
- [x] 统一状态检查输出结构
  说明：避免 1688、后续渠道各自返回不同字段
- [x] 定义统一状态结构
  说明：
  - `is_usable: bool`
  - `account_name: str`
  - `status_text: str`
  - `last_checked_at: str`
  - `error_message: str`
  - `meta: dict`
- [x] 决定状态检测接口形态
  说明：
  - 方案 A：继续走 `/api/system/configs` 返回派生状态
  - 方案 B：新增 `/api/system/source_channel_status` 按需检测
  - 推荐：A + B 并存，列表页先用 A，用户手动刷新走 B
- **状态：** complete

### 阶段 4：1688 渠道接入
- [x] 梳理当前 1688 登录态来源
  说明：
  - `state/ali1688/storage_state.json`
  - `profiles/ali1688_chrome_profile`
  - 可能的浏览器 `user-data-dir`
- [x] 设计 1688 账号运行时路径生成规则
  说明：
  - `state_file` 由系统按 `channel_id + account_id` 生成
  - `user_data_dir` 由系统按 `channel_id + account_id` 生成
  - `profile_directory` 作为系统内部默认值维护
- [x] 评估并确定 1688 单账号字段需求
  说明：
  - 配置层：`account_id / label / enabled / notes`
  - 运行时层：`state_file / user_data_dir / profile_directory / cookies_source`
- [x] 确定首期字段最小集
  说明：
  - 配置层必填：`account_id / label / enabled`
  - 运行时路径字段不要求用户填写，由系统自动生成
- [x] 接入 1688 Session 检查逻辑
  说明：优先复用 `scripts/inspect_ali1688_session.py` 和相关 `ali1688_session` 能力，而不是重新发明判断逻辑
- [x] 确认直接复用路径
  说明：
  - 若 `src/xianyu_tools/ali1688_session.py` 已有可直接 import 的检查函数，则在 FastAPI 内直接调用
  - 否则再考虑包装脚本调用，但优先避免 `subprocess`
- [x] 为 1688 渠道实现后端状态回显
  说明：
  - 返回账号可用性
  - 返回识别到的账号名
  - 返回当前状态说明
- [x] 定义 1688 状态文案映射
  说明：
  - 可用：`登录正常`
  - 不可用：`未检测到有效登录`
  - 缺少配置：`未配置状态文件`
  - 检测失败：`检测失败`
- [x] 明确 1688 主流程账号选择策略
  说明：
  - 是固定使用某个“激活账号”
  - 还是支持多账号轮换/兜底
  - 本期建议先做“单渠道多账号管理 + 明确激活账号”
- [x] 明确首期实现结论
  说明：
  - 首期只落“激活账号”
  - 多账号轮换只保留在后续阶段，不进本期实现
- **状态：** complete

### 阶段 5：前端系统设置页扩展
- [x] 在 `web/app.jsx` 的 `SystemSettingsView` 中新增“货源渠道号池”卡片
- [x] 卡片默认收起，行为与现有配置卡片一致
- [x] 设计卡片布局
  说明：
  - 第一层：渠道 tabs / pills
  - 第二层：渠道基础信息
  - 第三层：账号列表与激活账号选择
  - 第四层：状态区和操作按钮
- [x] 支持渠道级操作
  说明：
  - 新增渠道
  - 删除渠道
  - 切换当前激活渠道
- [x] 设计渠道级字段展示
  说明：
  - 渠道名称
  - 渠道类型
  - 是否启用
  - 当前激活账号
- [x] 支持账号级操作
  说明：
  - 新增账号
  - 删除账号
  - 编辑账号备注
  - 不暴露运行时路径类字段
- [x] 设计账号级字段布局
  说明：
  - 第一行：账号备注 / 启用状态 / 激活标记
  - 第二行：账号登录状态与账号名
  - 第三行：Session 状态与操作按钮
- [x] 展示 Session 状态
  说明：
  - 状态文案
  - 账号名
  - 最近检查结果
  - 错误原因（如有）
- [x] 明确状态展示样式
  说明：
  - 绿色：可用
  - 红色：不可用
  - 灰色：未检测 / 未配置
- [x] 若当前渠道支持登录触发，则提供渠道账号级“重新登录/重新检测”入口
- [x] 明确 1688 首期操作按钮
  说明：
  - `检测状态`
  - `打开登录浏览器`（仅当已有对应后端能力）
- [x] 与现有顶部保存按钮、提示动效、静默刷新机制保持一致
- [x] 明确前端状态源
  说明：
  - 保存前用本地 state
  - 保存后以 `/api/system/configs` 回包为准
  - 手动检测后仅刷新当前账号或当前渠道，不整页 reload
- **状态：** complete

### 阶段 6：多渠道与扩展边界
- [x] 定义首期支持渠道枚举
  说明：至少 `ali1688`；为后续淘宝/拼多多/自定义渠道留接口
- [x] 明确渠道差异字段
  说明：
  - 并非所有渠道都有相同登录方式
  - 不同渠道的登录检查方式、状态文件来源可能不同
- [x] 设计前端可扩展 UI
  说明：
  - 通用字段统一渲染
  - 渠道专属字段按 `channel_type` 分支渲染
- [x] 明确首期不做的内容
  说明：
  - 不做跨渠道统一登录弹窗
  - 不做多账号自动轮换抓取
  - 不做渠道级复杂权限体系
- [x] 记录未来扩展钩子
  说明：
  - 渠道级 `capabilities`
  - 账号级 `auth_type`
  - 状态检测适配器注册表
- **状态：** complete

### 阶段 7：流程接入与业务生效
- [x] 确认 1688 慢流程如何读取“激活渠道账号”
  说明：需要打通到 `run_ali1688_slow_flow.py` 及相关调度逻辑
- [x] 标出首批接入点
  说明：
  - `scripts/run_ali1688_slow_flow.py`
  - `scripts/generate_ali1688_result_url_map_via_browser.py`
  - `scripts/run_full_pipeline.py`
- [x] 确认图搜、详情抓取、结果 URL 生成是否共用同一渠道账号配置
- [x] 明确运行时回退策略
  说明：
  - 激活账号不可用时是否阻止任务
  - 是否允许切换到同渠道其他账号
- [x] 建议回退策略
  说明：
  - 首期：激活账号不可用则阻止 1688 慢流程启动，并返回明确错误
  - 非首期：可再扩展为同渠道候补账号
- [x] 将运行时脚本全部收口到“系统托管路径解析”
  说明：
  - 业务代码不再从前端配置直接读取 `state_file / user_data_dir`
  - 一律先根据 `channel_id + account_id` 解析运行时目录
- [x] 如需要，新增后端接口用于运行前状态校验
- [x] 定义建议接口
  说明：
  - `POST /api/system/source_channel_status/check`
  - `GET /api/system/source_channels/active`
- **状态：** complete

### 阶段 8：校验、测试与迁移
- [x] 为配置归一化补单测
- [x] 为渠道账号状态结构补单测
- [x] 为 1688 渠道状态检查补单测或脚本验证
- [x] 为“激活渠道 / 激活账号选择”补单测
- [x] 为旧配置自动补默认结构补单测
- [x] 验证无可用账号时错误提示足够明确
- [x] 手工验证系统配置页新增/删除渠道与账号
- [x] 手工验证保存后刷新仍能正确回显
- [x] 手工验证 Session 状态与账号名展示准确
- [x] 手工验证抓取任务启动前能正确读取激活 1688 账号
- **状态：** complete

### 阶段 9：交付与后续演进
- [x] 汇总字段结构与默认值
- [x] 说明与现有 `openapi` 多账号的边界
- [x] 说明与 1688 实际抓取链路的衔接方式
- [x] 产出实施备注
  说明：
  - 哪些字段是持久配置
  - 哪些字段是派生状态
  - 哪些能力是首期预留未实现
- [x] 记录后续可演进方向
  说明：
  - 同渠道账号轮换
  - 渠道账号健康检查定时任务
  - 渠道级抓取路由策略
- **状态：** complete

## 后端接口草案

### 1. 读取系统配置
- `GET /api/system/configs`
- 新增返回字段：
  - `source_channels`

### 2. 保存系统配置
- `POST /api/system/configs`
- 新增接收字段：
  - `source_channels`

### 3. 检测渠道账号状态（建议新增）
- `POST /api/system/source_channel_status/check`
- 请求体：
  - `channel_id`
  - `account_id`
- 返回：
  - `session_report`

### 4. 获取激活渠道账号（建议新增）
- `GET /api/system/source_channels/active`
- 返回：
  - `active_channel`
  - `active_account`

## 前端交互草案

### 渠道级
- 点击渠道 tab：切换当前编辑渠道
- 点击“新增渠道”：插入默认渠道模板
- 点击“删除渠道”：删除当前渠道并自动切换到下一个
- 点击“设为激活渠道”：更新 `active_channel_id`

### 账号级
- 点击“新增账号”：在当前渠道下插入默认账号模板
- 点击“删除账号”：删除当前账号，必要时重置 `active_account_id`
- 点击“设为激活账号”：更新渠道级 `active_account_id`
- 点击“检测状态”：调用状态检测接口并仅刷新当前账号状态
- 点击“打开登录浏览器”：若该渠道支持登录触发，则打开对应登录流程

## 实现顺序建议
1. 完成配置结构与归一化函数
2. 打通 `/api/system/configs` 读写
3. 接入 1688 状态检查
4. 完成系统设置页卡片与多账号编辑
5. 接入运行时激活账号读取
6. 完成测试、回归和交付说明

## 关键问题
1. “货源渠道号池”是只做 `1688`，还是结构上先支持多渠道、首期只启用 `1688`。
2. 1688 的状态配置最终以 `storage_state.json` 为准，还是 `user_data_dir` 为准，或两者都允许。
3. 运行时实际抓取链路是“渠道内单激活账号”，还是“多账号候补切换”。
4. 是否需要把渠道账号状态同步到首页左下角系统状态区。
5. 是否需要单独的“检测 Session”按钮，而不是在保存后被动刷新。

## 已做决策
| 决策 | 理由 |
|------|------|
| 新计划放入 `plan/2026-06-13-source-channel-pool/` | 避免和项目根目录旧计划混写 |
| 前端展示名使用“货源渠道号池” | 用户已明确命名 |
| 配置结构不并入 `openapi` | `openapi` 是闲鱼发布配置；货源渠道账号池是另一条链路 |
| 结构上按“渠道 -> 多账号”设计 | 用户明确要求区分渠道并支持多账号 |
| 首期重点先打通 `1688` | 当前实际代码里只有 `1688` 账号态是直接相关的主需求 |
| 计划中单列“流程接入”阶段 | 仅做配置页和状态展示没有价值，必须能影响实际抓取链路 |

## 遇到的错误
| 错误 | 尝试次数 | 解决方案 |
|------|---------|---------|
| 项目根目录已有旧计划文件，不能继续混写 | 1 | 新建 `plan/` 目录并使用独立子目录隔离新计划 |

## 备注
- 本计划只建立实施路径，不直接改业务代码。
- 后续真正实现前，应先重新读取本计划、`findings.md` 和 `progress.md`。
- 若后续还要新增其他配置计划，统一继续放在 `plan/` 下。
