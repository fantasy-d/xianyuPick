# 进度日志

## 会话：2026-07-05

### 阶段 1：基线与边界确认
- **状态：** complete
- **开始时间：** 2026-07-05
- 执行的操作：
  - 创建独立计划目录，避免和既有计划冲突。
  - 明确 POC 先做只读验证，真实发布/下架/删除前必须再次确认。
  - 记录当前 `PublisherV3` 的 OpenAPI 能力基线。
  - 记录官方工作台商品模块的页面能力和 mtop 接口线索。
- 创建/修改的文件：
  - `plan/2026-07-05-seller-workbench-adapter-poc/task_plan.md`
  - `plan/2026-07-05-seller-workbench-adapter-poc/findings.md`
  - `plan/2026-07-05-seller-workbench-adapter-poc/progress.md`

### 阶段 2：只读接口验证
- **状态：** complete
- 执行的操作：
  - 准备验证商品管理列表、发布预请求、运费模板、所在地、类目/属性等只读能力。
  - 尝试直接打开已签名 `h5api` URL 读取状态统计和商品列表接口响应。
  - 发现直接重放返回 `FAIL_SYS_ILLEGAL_ACCESS::非法请求`。
  - 通过页面渲染数据验证商品管理页能拿到商品 ID、标题、价格、库存、创建时间、状态统计。
  - 通过发布页渲染数据验证发布页字段和预请求接口。
- 创建/修改的文件：
  - `plan/2026-07-05-seller-workbench-adapter-poc/findings.md`
  - `plan/2026-07-05-seller-workbench-adapter-poc/progress.md`

### 阶段 3：发布模型映射设计
- **状态：** complete
- 执行的操作：
  - 对齐当前 `PublisherV3.prepare_item_payload` 字段。
  - 从官方发布模块前端包反推出 `itemTextDTO/itemPriceDTO/itemPostFeeDTO/itemSkuList/imageInfoDOList/itemAddrDTO/itemCatDTO` 等字段。
  - 建立第一版字段映射草案。
  - 运行清洗后的静态探针，确认前端包内有 64 个 `mtop.*` API 标记。
  - 补齐能力映射表，明确图片上传、SKU 图片、类目 ID 体系、服务端 mtop 复刻和多账号上下文为主要风险。
- 创建/修改的文件：
  - `plan/2026-07-05-seller-workbench-adapter-poc/task_plan.md`
  - `plan/2026-07-05-seller-workbench-adapter-poc/findings.md`
  - `plan/2026-07-05-seller-workbench-adapter-poc/progress.md`
  - `scripts/probe_seller_workbench_static.py`

### 阶段 4：最小本地 POC
- **状态：** complete
- 执行的操作：
  - 已整理只读静态探针作为第一版 POC 工件。
  - 静态探针只读取公开前端包，不使用登录态、不调用业务接口、不产生发布/下架/删除副作用。
  - 使用当前 in-app browser 的已登录发布页做只读运行时探查。
  - 确认页面加载了 `lib-mtop`、登录、AWSC/Baxia 风控和 `seller-item` 商品模块 bundle。
  - 没有发现可直接调用的全局 mtop 客户端对象。
  - 定点检查常见全局入口和 cookie/storage 键名，受浏览器只读沙箱限制，仍不能证明后端可复刻登录态调用。
  - 导航到商品管理页做只读渲染验证，确认页面仍能展示在卖/下架统计和真实商品 ID。
  - 商品管理页浏览器日志未暴露 mtop/h5api/common.item.search 或错误日志。
  - 新增 `scripts/probe_seller_workbench_readonly.py`，复用 `xianyu_state.json` 做 Playwright 只读响应监听。
  - 真实运行只读探针，成功捕获商品列表、状态统计、发布预请求、运费模板、所在地和类目搜索接口。
  - 确认 `mutation_api_hits` 为空，没有触发发布/下架/删除/更新类接口。
- 下一步：
  - 阶段 5 如果要继续，需要用户明确确认是否允许创建测试商品或测试草稿。
  - 真实发布验证前需确认测试标题、图片、价格、库存、是否发布后立即下架/删除。

### 阶段 5：受控副作用验证
- **状态：** complete
- 执行的操作：
  - 已准备阶段 5 验证方案，记录草稿验证、正式发布验证、继续只读验证三条路径。
  - 已明确推荐测试商品配置：标题包含 `[POC勿拍]`，高价 `9999.00`，库存 `1`，单规格，本地测试图，描述注明不发货。
  - 已明确执行前检查：确认账号、动作、标题、价格、库存、响应监听和无批量操作。
  - 已明确发布后验证与回滚：记录商品 ID、状态、列表可见性；下架/删除需再次确认。
  - 用户明确授权正式发布测试商品，并要求发布后再确认下架/删除。
  - 生成本地测试图：`scratch/seller-workbench-poc/poc-do-not-buy.png`。
  - 新增受控发布脚本：`scripts/probe_seller_workbench_publish_poc.py`，脚本要求显式传入 `--i-understand-this-publishes`。
  - 执行正式发布测试，工作台接口 `mtop.idle.pc.backend.idleitem.publish` 返回成功。
  - 记录返回商品 ID：`1063238250794`。
  - 发布成功页 URL 包含 `#/seller-item/publish/success?itemId=1063238250794`。
  - 商品管理页验证在卖数量为 `3`，新商品显示价格 `¥9999.00`、库存 `1`，操作包含 `编辑/改价/设置粉丝价/下架`。
  - 用户确认下架商品 ID `1063238250794`。
  - 新增受控下架脚本：`scripts/probe_seller_workbench_offline_poc.py`，脚本要求显式传入 `--i-understand-this-offlines`。
  - 第一次下架尝试只打开确认弹窗，未点击到 `确 定`，未触发下架接口。
  - 修复确认按钮识别后重试，工作台接口 `mtop.alibaba.idle.seller.pc.item.offline` 返回成功。
  - 商品管理页验证在卖数量从 `3` 回到 `2`，下架数量从 `65` 到 `66`，在卖列表不再包含 `1063238250794`。
  - 用户确认删除商品 ID `1063238250794`，并要求使用无头浏览器。
  - 新增受控删除脚本：`scripts/probe_seller_workbench_delete_poc.py`，脚本要求显式传入 `--i-understand-this-deletes`。
  - 使用无头浏览器执行删除，工作台接口 `mtop.alibaba.idle.seller.pc.item.delete` 返回成功。
  - 商品管理页验证下架数量从 `66` 回到 `65`，下架列表不再包含 `1063238250794` 和 `[POC勿拍]`。

### 阶段 6：结论与下一步
- **状态：** complete
- 执行的操作：
  - 已形成最终替代性结论：官方工作台具备核心替代能力，但推荐通过 Playwright 浏览器会话适配器接入，不推荐后端直接复刻 mtop。
  - 已记录推荐架构：保留当前 OpenAPI 作为主链路/兜底，新增 `SellerWorkbenchAdapter` 做灰度或备用链路。
  - 已记录剩余风险：媒体上传、类目属性映射、多 SKU/SKU 图片、多账号登录态、页面版本变化。
  - 已记录后续工程任务：适配器抽象、配置开关、回归脚本和强制安全保护。

### POC 后工程化骨架
- **状态：** complete
- 执行的操作：
  - 新增 `src/xianyu_tools/xianyu_adapter/seller_workbench_adapter.py`，沉淀官方卖家工作台浏览器会话适配器骨架。
  - 当前只纳入 POC 已验证的能力：当前页商品列表读取、单商品下架、单商品删除。
  - 下架/删除方法要求 `confirm_item_id` 与 `item_id` 一致；删除还要求传入 `expected_title_substring`，避免仅凭按钮文本误操作。
  - 确认按钮点击限定在 Ant Design 弹窗/气泡层内，避免在整个页面中误点其他行的“下架/删除”按钮。
  - 更新 `src/xianyu_tools/xianyu_adapter/__init__.py` 导出 `SellerWorkbenchAdapter`。
- 验证：
  - `python3 -m py_compile src/xianyu_tools/xianyu_adapter/seller_workbench_adapter.py src/xianyu_tools/xianyu_adapter/__init__.py`
  - `PYTHONPATH=src python3 - <<'PY' ... SellerWorkbenchAdapter.from_state_file('xianyu_state.json').list_items(status='on_sale') ... PY`，读到在卖 2 条。
  - `PYTHONPATH=src python3 - <<'PY' ... SellerWorkbenchAdapter.from_state_file('xianyu_state.json').list_items(status='offline') ... PY`，读到下架当前页 20 条。
  - `PYTHONPATH=src pytest -q tests/test_xianyu_adapter.py tests/test_xianyu_fixture_adapter.py`，17 个测试通过。
- 备注：
  - 这一步没有替换现有 `PublisherV3` / OpenAPI 路径。
  - 发布链路仍保留在受控 POC 脚本中，待图片、类目、SKU 字段工程化后再接入适配器。

### 阶段 7：交易/订单只读能力验证
- **状态：** complete
- 执行的操作：
  - 使用 `xianyu_state.json` 复用登录态，只读打开交易域页面。
  - 第一轮直达 `order-list/rate-manage`，发现 `order-list` 显示“禁止访问”，`rate-manage` 不是评价管理真实路由。
  - 静态解析交易域 bundle `idle-seller-trade/0.0.24/js/main.js`，识别 `71` 个 `mtop.*` API。
  - 反查并验证真实路由：`order-manage/refund-manage/refund-address/evaluation-manage/complaint-manage`。
  - 捕获订单、退款、退货地址、评价、投诉的只读接口响应摘要。
  - 产出脱敏 schema，只保存字段名/类型/列表数量，不保存手机号、地址、买家昵称等原始敏感值。
- 创建/修改的文件：
  - `scratch/seller-workbench-poc/order-readonly-routes.json`
  - `scratch/seller-workbench-poc/trade-static-probe.json`
  - `scratch/seller-workbench-poc/order-readonly-correct-routes.json`
  - `scratch/seller-workbench-poc/order-readonly-schema.json`
  - `plan/2026-07-05-seller-workbench-adapter-poc/task_plan.md`
  - `plan/2026-07-05-seller-workbench-adapter-poc/findings.md`
  - `plan/2026-07-05-seller-workbench-adapter-poc/progress.md`
- 验证结果：
  - 订单管理页：`mtop.taobao.idle.trade.merchant.sold.get` 返回成功，当前列表 `0` 条。
  - 订单统计：`mtop.taobao.idle.merchant.order.count` 返回成功，状态统计列表 `9` 项。
  - 退款管理页：`mtop.taobao.idle.merchant.refund.list` 返回成功，当前列表 `1` 条。
  - 退货地址页：`mtop.alibaba.idle.seller.platform.merchant.delivery.address.list.query` 返回成功，当前列表 `1` 条。
  - 评价管理页：`mtop.taobao.idle.merchant.rate.list` 返回成功，当前列表 `0` 条。
  - 投诉管理页：`mtop.taobao.idle.cco.shop.complain.list` 返回成功，当前列表 `0` 条。
- 安全边界：
  - 未点击发货、退款同意/拒绝、改价、关闭订单、评价、投诉处理、地址新增/编辑/删除等按钮。
  - 静态包中已记录这些副作用接口，但没有执行。

### 阶段 8：交易/订单只读适配器骨架
- **状态：** complete
- 执行的操作：
  - 新增 `src/xianyu_tools/xianyu_adapter/seller_workbench_trade_adapter.py`。
  - 新增 `SellerWorkbenchTradeAdapter`，封装交易域只读快照能力。
  - 支持读取并解析：订单统计、订单列表、退款列表、退货地址、评价列表、投诉列表。
  - 更新 `src/xianyu_tools/xianyu_adapter/__init__.py` 导出 `SellerWorkbenchTradeAdapter`。
  - 解析结果默认返回结构化摘要，退货地址联系人/手机号、买家昵称使用脱敏值。
  - 修正同一个 `order.count` 接口在多个交易页复用导致快照覆盖的问题：快照按访问顺序保留订单页首次捕获结果。
  - 修正退款金额解析，避免把 `alipays://...` 跳转链接识别为金额。
- 验证：
  - `python3 -m py_compile src/xianyu_tools/xianyu_adapter/seller_workbench_trade_adapter.py src/xianyu_tools/xianyu_adapter/__init__.py`
  - `PYTHONPATH=src python3 - <<'PY' ... from xianyu_tools.xianyu_adapter import SellerWorkbenchTradeAdapter ... PY`
  - `PYTHONPATH=src pytest -q tests/test_xianyu_adapter.py tests/test_xianyu_fixture_adapter.py`，17 个测试通过。
  - `SellerWorkbenchTradeAdapter.from_state_file('xianyu_state.json').capture_snapshot()` 只读快照成功：
    - 捕获 6 个交易域只读 API。
    - 订单统计包含 `ALL/NOT_PAY/NOT_SHIP/SHIPPED/REFUND/TRADE_SUCCESS/TRADE_CLOSED` 等状态。
    - 当前订单列表 `0` 条、退款列表 `1` 条、退货地址 `1` 条、评价 `0` 条、投诉 `0` 条。
- 安全边界：
  - 未接入发货、退款同意/拒绝、改价、关闭订单、评价、投诉处理、地址新增/编辑/删除。
  - 本阶段没有新增任何生产 API 路由调用。

## 测试结果
| 测试 | 输入 | 预期结果 | 实际结果 | 状态 |
|------|------|---------|---------|------|
| 基线能力确认 | `PublisherV3` 与官方工作台前端包 | 明确两边核心能力 | 已记录 OpenAPI 与 mtop 能力矩阵 | 通过 |
| 已签名 URL 重放 | `pc.item.status.statistics` / `common.item.search` | 能读取 JSON 或明确失败原因 | 返回 `FAIL_SYS_ILLEGAL_ACCESS::非法请求` | 失败但有结论 |
| 商品管理渲染数据 | `#/seller-item/goods-manage` | 展示商品 ID、标题、状态和操作 | 已提取在卖/下架数量、2 条商品数据、下架入口 | 通过 |
| 发布页字段发现 | `#/seller-item/publish` | 展示发布所需主要字段和预请求接口 | 已提取图片、描述、规格、价格、发货、所在地字段及预请求 mtop API | 通过 |
| 发布字段映射 | `PublisherV3.prepare_item_payload` 与工作台前端包 | 得到字段映射草案 | 已形成第一版映射表，图片/SKU 图片/类目为主要风险 | 通过 |
| 静态探针 | `scripts/probe_seller_workbench_static.py` | 输出清洗后的官方工作台 API/字段证据 | 识别 64 个 `mtop.*` API，发布字段标记全部存在 | 通过 |
| 商品管理页只读渲染 | `#/seller-item/goods-manage` | 页面可展示商品列表与状态统计 | 在卖 2、下架 65，展示 2 个商品 ID 和操作入口 | 通过 |
| 商品管理页日志检查 | `tab.dev.logs` | 找到 mtop/h5api 调用线索或明确工具限制 | 未发现相关日志，不能替代网络抓包 | 有结论 |
| 只读工作台探针 | `scripts/probe_seller_workbench_readonly.py` + `xianyu_state.json` | 捕获核心只读 mtop JSON，且不触发副作用接口 | 捕获 6 个只读 API，商品列表返回 2 个商品，mutation hits 为空 | 通过 |
| 阶段 5 方案准备 | 受控副作用验证 | 明确测试商品、确认条件和回滚路径 | 已记录草稿/正式发布/继续只读三条路径 | 通过 |
| 正式发布测试 | `[POC勿拍]` 测试商品，高价 `9999.00`，库存 `1` | 返回商品 ID，并能在商品管理页看到商品 | 返回商品 ID `1063238250794`，商品管理页在卖数量 `3`，新商品可见 | 通过 |
| 下架测试 | 商品 ID `1063238250794` | 下架接口成功，商品从在卖列表移除 | `offline` 接口返回成功，在卖 `2`，下架 `66`，在卖列表不含该 ID | 通过 |
| 删除测试 | 商品 ID `1063238250794` | 删除接口成功，商品从下架列表移除 | `delete` 接口返回成功，下架 `65`，下架列表不含该 ID 和 `[POC勿拍]` | 通过 |
| 最终结论 | POC 全链路证据 | 给出可替代性判断和架构建议 | 推荐新增浏览器会话适配器，保留 OpenAPI 兜底 | 通过 |
| 适配器骨架编译 | `seller_workbench_adapter.py` | 模块可编译、可导入 | `py_compile` 与 `PYTHONPATH=src` 导入通过 | 通过 |
| 适配器只读列表 | `xianyu_state.json` | 可读取官方工作台在卖/下架当前页 | 在卖 2 条、下架当前页 20 条 | 通过 |
| 现有适配器测试 | `tests/test_xianyu_adapter.py`、`tests/test_xianyu_fixture_adapter.py` | 新增导出不影响原适配器 | 17 passed | 通过 |
| 交易域静态解析 | `idle-seller-trade/0.0.24/js/main.js` | 识别订单相关 API 与真实路由 | 71 个 mtop API，真实路由含 `order-manage/refund-manage/evaluation-manage` | 通过 |
| 交易域只读页面 | `xianyu_state.json` | 只读捕获订单/退款/地址/评价/投诉接口 | 6 个核心只读接口返回成功，无副作用动作 | 通过 |
| 交易域适配器编译 | `seller_workbench_trade_adapter.py` | 模块可编译、可导入 | `py_compile` 与 `PYTHONPATH=src` 导入通过 | 通过 |
| 交易域适配器快照 | `xianyu_state.json` | 可读取交易域只读摘要 | 订单 0、退款 1、退货地址 1、评价 0、投诉 0 | 通过 |

## 错误日志
| 时间戳 | 错误 | 尝试次数 | 解决方案 |
|--------|------|---------|---------|
| 2026-07-05 | 直接打开已签名 `h5api` URL 返回非法请求 | 1 | 改为页面渲染数据验证，并评估是否可捕获运行时请求 body |
| 2026-07-05 | 临时 `h5api` 页签覆盖了当前工作台页签，导致一次页面数据提取命中错误 URL | 1 | 已导航回 `#/seller-item/goods-manage` 后继续验证 |
| 2026-07-05 | 浏览器只读沙箱中直接枚举 `globalThis` 失败 | 1 | 改用 `window` 和 DOM 脚本列表做保守探查 |
| 2026-07-05 | 浏览器只读沙箱无法读取 `localStorage/sessionStorage.length` | 1 | 只记录工具限制，不把它作为“页面没有登录态”的证据 |
| 2026-07-05 | 只读探针第一次读取部分 response body 时 body 已被回收 | 1 | 改为追踪响应读取任务，并在页面阶段结束前等待 |
| 2026-07-05 | `response.finished()` 在页面关闭时产生 `Target closed` 噪音 | 1 | 移除 `response.finished()`，改用 `response.json()` 超时保护 |
| 2026-07-05 | 第一次下架只打开确认弹窗，未点击到 `确 定` | 1 | 增加对 `确 定` 文案的确认按钮识别后重试成功 |

## 五问重启检查
| 问题 | 答案 |
|------|------|
| 我在哪里？ | 阶段 6：结论已完成 |
| 我要去哪里？ | 后续可进入工程实现：新增 `SellerWorkbenchAdapter` 或提交 POC 代码 |
| 目标是什么？ | 判断官方卖家工作台接口是否可替代闲管家 OpenAPI，并产出 POC 证据 |
| 我学到了什么？ | 官方工作台商品模块能力丰富，但依赖浏览器 mtop 与风控；发布字段大多可映射，图片上传、SKU 图片、类目 ID 和服务端 mtop 复刻最不确定 |
| 我做了什么？ | 完成基线、只读验证、字段映射、静态探针、登录态只读探针、正式发布、下架、删除和最终结论 |

---
*每个阶段完成后或遇到错误时更新此文件*
