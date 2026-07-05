# 进度日志：闲管家 OpenAPI 订单管理

## 2026-07-05

### 阶段 1：接口与现状调研
- **状态：** in_progress
- 已完成：
  - 创建计划目录 `plan/2026-07-05-openapi-order-management/`
  - 写入 `task_plan.md / findings.md / progress.md`
  - 确认本地文档中订单列表/详情路径
  - 定位现有 OpenAPI 适配器和前端导航注册点
  - 通过公开 Apifox 文档确认订单列表/详情的最小请求体与核心响应字段
  - 在 `PublisherV3` 增加 `query_order_list(...)` 和 `query_order_detail(...)`
  - 在 `src/web_api/main.py` 增加 `/api/orders` 和 `/api/orders/{order_no}` 只读接口
  - 在 `web/app.jsx` 增加 `OrderManager` 订单管理页面
  - 侧边栏、顶部标题、主内容分支已注册 `orders`
  - 页面支持订单刷新、状态筛选、分页、详情查看
- 当前状态：
  - 全部计划阶段已完成

## 验证记录
| 检查 | 结果 |
|------|------|
| Python 编译 | `src/web_api/main.py` 与 `publisher_v3.py` 通过 |
| 前端 JSX 转译 | 使用 bundled Node + `web/babel.min.js` 转译 `web/app.jsx` 通过 |
| 首页探活 | `GET /` 返回 200 |
| 订单列表接口 | `GET /api/orders?page=1&limit=2` 返回 1 条真实订单 |
| 订单详情接口 | `GET /api/orders/3302059874686006981` 返回成功 |
| 状态筛选接口 | `GET /api/orders?page=1&limit=1&order_status=24` 返回成功 |
| 页面级验证 | in-app browser 可看到“订单管理”、订单列表、详情面板，点击详情后展示订单号、商品、金额、收货、物流 |

## 错误日志
| 时间 | 错误 | 处理 |
|------|------|------|
| 2026-07-05 | 第一次 in-app browser 完整 DOM 快照超时，浏览器控制内核重置 | 改用轻量 `evaluate` 检查页面关键文本与状态 |
| 2026-07-05 | 浏览器验证过程中出现 Statsig 外部请求超时日志 | 不影响本地页面验证结果，订单详情 DOM 检查已返回 `ok: true` |

## 剩余风险
- 订单状态数字枚举暂无完整官方映射，当前页面展示 `状态 x` 原始值。
- 当前功能为只读，不包含发货、改价、售后等订单操作。

### 交互修正：订单详情需要先选中订单
- **状态：** complete
- 已完成：
  - 将“点击行直接查询详情”改为“点击行/选择按钮只选中订单”
  - 未选中订单时，“查看订单详情”按钮禁用
  - 选中订单后，按钮启用但不自动加载详情
  - 点击“查看订单详情”后才调用详情接口并展示详情面板
- 验证：
  - Babel 转译 `web/app.jsx` 通过
  - `py_compile` 后端文件通过
  - in-app browser 页面级验证通过：初始禁用、选中启用、点击后展示详情

### 交互修正：详情改为独立页面，列表左侧加选择框
- **状态：** complete
- 已完成：
  - 订单列表左侧新增单选 checkbox
  - 移除列表右侧内嵌详情面板
  - “查看订单详情”改为选中订单后跳转到独立 `order_detail` 页面
  - 新增独立订单详情页，支持返回订单列表、刷新详情
  - 订单管理导航在 `orders/order_detail` 两个视图下保持选中态
- 验证：
  - Babel 转译 `web/app.jsx` 通过
  - `py_compile` 后端文件通过
  - in-app browser 验证通过：列表显示 checkbox、未选中时详情按钮禁用、选中后跳转详情页、返回列表可用
