# 发现与决策：闲管家 OpenAPI 订单管理

## 初始需求
- 集成闲管家 OpenAPI：
  - 查询订单列表
  - 查询订单详情
- 新增系统功能页：订单管理。

## 初始决策
| 决策 | 原因 |
|------|------|
| 先做只读订单管理 | 用户只要求查询列表和详情，没有要求订单操作 |
| 复用现有 OpenAPI 账号体系 | 系统已有闲管家 OpenAPI 配置和多账号选择能力 |
| 后端返回稳定字段 + raw | 订单接口字段不确定时，前端先可用，后续可精细化字段映射 |

## 研究记录
- `docs/xianguanjia_openapi_guide.md` 已记录闲管家 OpenAPI 订单路径：
  - 查询订单列表：`POST /api/open/order/list`
  - 查询订单详情：`POST /api/open/order/detail`
- 现有 `PublisherV3` 已封装 OpenAPI 配置读取、签名和 POST 调用模式，但每个业务方法仍手写请求逻辑。
- 现有商品详情同步方法 `query_product_detail(...)` 可作为订单查询错误处理风格参考。
- `seller_workbench_trade_adapter.py` 是官方卖家工作台 mtop 只读适配器，接口域与本次闲管家 OpenAPI 不同，只适合参考订单 UI 字段，不应混用认证/请求逻辑。
- 前端主导航和页面注册集中在 `web/app.jsx`：
  - `pageIntro` / `topBarMeta`
  - 侧边栏 `<li>`
  - 主内容区域的 `view === ...` 分支
- 公开 Apifox 文档确认：
  - 订单列表：`POST https://open.goofish.pro/api/open/order/list`
  - 列表请求示例：`{"page_size": 10, "page_no": 1, "order_status": 22}`
  - 列表响应：`data.list`，订单字段包含 `order_no/order_status/order_time/total_amount/pay_amount/refund_status/receiver_* / waybill_no / express_* / buyer_nick / seller_name / goods`。
  - 订单详情：`POST https://open.goofish.pro/api/open/order/detail`
  - 详情请求示例：`{"order_no": "string"}`
  - 详情响应：`data` 为单个订单对象，字段与列表项基本一致，并包含 `order_type/refund_amount/idle_biz_type/pin_group_status/is_tax_included` 等。

## 错误记录
| 错误 | 尝试次数 | 解决方案 |
|------|---------|---------|
| in-app browser 完整 DOM 快照超时 | 1 | 改用轻量 `evaluate` 读取关键页面文本 |
| 页面验证过程中出现 Statsig 外部请求超时日志 | 1 | 该请求与本地应用无关，订单页面关键 DOM 检查仍通过 |
