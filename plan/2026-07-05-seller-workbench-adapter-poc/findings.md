# 发现与决策

## 需求
- 按 POC 流程判断官方闲鱼卖家工作台接口能否替代当前闲管家 OpenAPI。
- 用户给定商品发布页：`https://seller.goofish.com/?site=COMMONPRO#/seller-item/publish`。
- 当前浏览器已登录官方卖家工作台。

## 研究发现
- 当前闲管家 OpenAPI 能力基线来自 `PublisherV3`：
  - 类目：`/api/open/product/category/list`
  - 单商品创建：`/api/open/product/create`
  - 批量创建：`/api/open/product/batchCreate`
  - 正式上架：`/api/open/product/publish`
  - 下架：`/api/open/product/downShelf`
  - 删除：`/api/open/product/delete`
- 当前 OpenAPI 认证方式是服务端签名：`appid + timestamp + sign`，请求由后端 `requests.post` 发起。
- 官方工作台商品模块前端包为 `https://g.alicdn.com/idle-pc/seller-item/0.0.14/js/main.js`。
- 官方工作台核心调用是 `h5api.m.goofish.com` 的 mtop 接口，依赖浏览器登录态、mtop 签名、`AutoLoginOnly` 和风控脚本。
- 前端包中观察到的核心能力接口包括：
  - 发布：`mtop.idle.pc.backend.idleitem.publish`、`mtop.idle.pc.first.hand.idleitem.publish`
  - 草稿：`mtop.idle.idleitem.draft.publish`、`mtop.alibaba.idle.item.pc.draft.search`
  - 列表：`mtop.alibaba.idle.seller.pc.common.item.search`
  - 状态统计：`mtop.taobao.idle.seller.platform.pc.item.status.statistics`
  - 下架：`mtop.alibaba.idle.seller.pc.item.offline`、`mtop.alibaba.idle.seller.pc.item.batch.offline`
  - 删除：`mtop.alibaba.idle.seller.pc.item.delete`、`mtop.alibaba.idle.seller.pc.item.batch.delete`
  - 编辑：`mtop.alibaba.idle.seller.pc.item.info.update`
  - 价格/库存：`mtop.alibaba.idle.seller.pc.item.price.update`、`mtop.alibaba.idle.seller.pc.item.quantity.update`
  - 运费模板：`mtop.alibaba.idle.seller.platform.freight.template.pc.all`
  - 类目/属性：`mtop.taobao.idle.item.pc.category.list`、`mtop.taobao.idle.seller.platform.item.pc.category.property.query`
  - 所在地：`mtop.taobao.idle.local.poi.get`

## 技术决策
| 决策 | 理由 |
|------|------|
| 先做只读接口验证 | 降低对真实账号造成副作用的风险 |
| 阶段 2 以“页面渲染数据 + 前端包接口结构 + 重放失败原因”作为只读证据 | 当前工具无法直接读取 XHR response body，直接重放 mtop URL 又会非法请求；继续强行抓包风险更高 |

## 发布字段映射草案
| 当前 `PublisherV3` 字段 | 官方工作台字段线索 | 映射判断 |
|------|------|------|
| `publish_shop[].title` / `source_data.title` | `itemTextDTO.title`、页面主要显示“宝贝描述”并可智能识别标题/属性 | 可映射，但需要确认发布页是否接受显式标题，UI 上标题字段不明显 |
| `publish_shop[].content` / `description` | `itemTextDTO.desc`、`richTextDesc` | 可映射 |
| `publish_shop[].images` | `imageInfoDOList`、`descImages`、媒体上传组件 | 高风险；当前 OpenAPI 接收远程 URL，官方页看起来需要媒体上传后的对象 |
| `price` / `original_price` | `itemPriceDTO.priceInCent`、`itemPriceDTO.origPriceInCent` | 可映射 |
| `stock` | `quantity` 或 SKU 行 `quantity` | 可映射 |
| `sku_items[].sku_text/price/stock` | `itemSkuList[].propertyList/priceInCent/quantity` | 可映射，但需要将 `sku_text` 拆成属性名和值 |
| `sku_images` | `propertyImageList` 或属性值图片上传对象 | 高风险；需要媒体对象与属性值绑定 |
| `channel_cat_id` / `sp_biz_type` | `itemCatDTO.channelCatId/catId/leafId/tbCatId`、类目属性接口 | 可映射但需要官方类目 ID 体系对齐验证 |
| `express_fee` | `itemPostFeeDTO.postPriceInCent`、包邮/运费模板/无需邮寄 | 可映射 |
| `province/city/district` | `itemAddrDTO.prov/city/area/divisionId/gps/poiId/poiName` | 可映射但需要地点接口返回结构 |
| `user_name` | 工作台当前登录账号 | 不需要传用户名，但需要确认多账号/子账号切换方式 |

## 阶段 3 结论：映射可行性
| 能力项 | 当前 OpenAPI 路径 | 官方工作台线索 | POC 判断 |
|------|------|------|------|
| 商品创建/发布 | `/api/open/product/create` + `/api/open/product/publish` | `mtop.idle.pc.backend.idleitem.publish`、`mtop.idle.pc.first.hand.idleitem.publish` | 功能存在，但需要解决 mtop 登录态、签名、风控和媒体对象 |
| 批量创建 | `/api/open/product/batchCreate` | 前端未发现等价批量发布接口 | 暂不可直接映射，迁移时可能需要逐条发布 |
| 草稿 | 当前链路不依赖草稿 | `mtop.idle.idleitem.draft.publish`、`mtop.alibaba.idle.item.pc.draft.*` | 可作为安全 POC 方向，但仍可能产生账号侧草稿副作用 |
| 商品列表/状态 | 当前系统维护本地发布状态并可调用 OpenAPI 操作 | `mtop.alibaba.idle.seller.pc.common.item.search`、`mtop.taobao.idle.seller.platform.pc.item.status.statistics` | 只读能力已从页面渲染和 bundle 证据验证 |
| 下架/删除 | `/api/open/product/downShelf`、`/api/open/product/delete` | `mtop.alibaba.idle.seller.pc.item.offline/delete` 及 batch 版本 | 功能存在；真实动作必须二次确认 |
| 编辑/调价/改库存 | 当前主链路较少使用 | `info.update`、`price.update`、`quantity.update` | 功能存在，可作为替代后增强项 |
| 运费模板/发货 | `express_fee` 和默认配置 | `freight.template.pc.all`、`itemPostFeeDTO` | 可映射，需要确认模板 ID 和包邮/无需邮寄组合 |
| 类目属性 | `channel_cat_id/sp_biz_type` | `category.list`、`category.property.query`、`brands/models`、`kgraph` | 可映射但不是同一 ID 体系，需要新增类目转换/推荐步骤 |
| 所在地 | `province/city/district` | `local.poi.get`、`division.all.get`、`itemAddrDTO` | 可映射，需要接口返回结构补充 `divisionId/gps/poiId` |
| 图片/视频 | 远程 URL 列表 | `imageInfoDOList`、`descImages`、媒体上传组件 | 最大风险；不能假设远程 URL 可直接发布 |
| SKU 图片 | `sku_images[].src/sku_text` | `propertyImageList` | 高风险；需要先完成媒体上传，再绑定属性值 |

## 静态探针结果
- POC 脚本：`scripts/probe_seller_workbench_static.py`。
- 探针方式：拉取公开前端包 `https://g.alicdn.com/idle-pc/seller-item/0.0.14/js/main.js`，只提取 `mtop.*` API 名、路由和发布 payload 标记；不使用 cookie，不调用业务接口。
- 最新结果：bundle 大小 `4368648` 字符，识别 `64` 个 `mtop.*` API。
- 能力覆盖：
  - 发布/服务卡：`publish` 类 7 个接口
  - 草稿：7 个接口
  - 搜索/状态：7 个接口
  - 下架：2 个接口
  - 删除：4 个接口
  - 编辑/调价/改库存：9 个接口
  - 运费模板：9 个接口
  - 类目/属性/品牌型号：10 个接口
  - 安全校验：2 个接口
  - POI/行政区：2 个接口
- 发布字段标记全部存在：`itemTextDTO/itemCatDTO/itemPriceDTO/itemPostFeeDTO/itemSkuList/imageInfoDOList/propertyImageList/descImages/itemAddrDTO/userRightsProtocols/uniqueCode/sourceId/bizcode/publishScene`。

## 当前不可直接替代项
| 风险 | 原因 | 下一步验证 |
|------|------|------|
| 服务端复刻 mtop 调用不确定 | 直接重放已签名 `h5api` URL 返回非法请求，说明依赖浏览器上下文、签名、token 或风控 | 阶段 4 设计浏览器内只读探针，或确认后端签名复刻所需 cookie/token |
| 图片上传链路未确认 | 工作台 payload 需要媒体对象，当前 OpenAPI 只传远程 URL | 阶段 4/5 捕获发布页上传接口；真实上传前确认测试素材 |
| 类目 ID 体系不一致 | 当前 `channel_cat_id/sp_biz_type` 与工作台 `catId/leafId/tbCatId` 不是同一套字段 | 用只读类目接口验证标题到类目推荐/属性查询链路 |
| 批量发布能力缺口 | bundle 中未确认官方工作台存在批量发布等价接口 | 迁移设计先按单条发布串行处理，后续再评估批量优化 |
| 多账号/子账号切换不确定 | 工作台调用依赖当前浏览器登录态，不像 OpenAPI 明确传 `user_name` | 需要识别账号上下文和多账号切换方式 |

## 阶段 4 运行时探查
- 当前 in-app browser 页面：`https://seller.goofish.com/?site=COMMONPRO#/seller-item/publish`，标题“商品发布 - 闲鱼卖家工作台”。
- 页面脚本中确认加载：
  - `mtb/lib-mtop/2.7.3/mtop.js`
  - `mtb/lib-login/3.5.1/login.js`
  - `AWSC/awsc.js`
  - `sd/baxia/baxiaCommon.js`
  - `o.alicdn.com/vip/goofish-auto-login/plugin.js`
  - `idle-pc/seller-item/0.0.14/js/main.js`
- 只读运行时枚举没有发现可直接调用的全局 `mtop/lib/goofish` 对象。
- 判断：页面确实具备浏览器侧 mtop 运行依赖，但它不是一个明显暴露的全局 SDK；阶段 4 不能把“浏览器上下文可直接调用 mtop”作为已证明事实。
- 定点检查 `window.lib/window.mtop/window.AWSC/window.BaxiaCommon/window.__webpack_require__` 等名称，结果均为未暴露。
- cookie/storage 键名探查在浏览器只读沙箱内受限：cookie name 为空，`localStorage/sessionStorage` 无法读取长度。不能据此判断页面没有 cookie，只能说明当前探查工具拿不到登录态表面。
- 导航到商品管理页 `https://seller.goofish.com/?site=COMMONPRO#/seller-item/goods-manage` 后，页面只读渲染正常：
  - 标题“商品管理 - 闲鱼卖家工作台”
  - 在卖 `2`、下架 `65`
  - 商品 `1059889885905`，标题“半甜初品黑糯米千层蛋糕券”，价格 `¥29.99`，库存 `2`
  - 商品 `949419974611`，标题“[闪亮]全新现货[闪亮]”，价格 `¥328.00`，库存 `1`
  - 页面显示“共2项数据”“批量下架”
- 商品管理页加载后的浏览器日志中没有 `mtop`、`h5api`、`common.item.search` 或 error 日志可用。当前浏览器工具不能作为网络抓包替代。

## 阶段 4 最小只读 POC 结果
- 新增脚本：`scripts/probe_seller_workbench_readonly.py`。
- 运行命令：
  - `python3 scripts/probe_seller_workbench_readonly.py --state-file xianyu_state.json --pages goods-manage publish --timeout-ms 30000 --settle-ms 5000 --response-timeout-ms 8000`
- POC 形态：
  - 复用本地 `xianyu_state.json`。
  - 使用 Playwright 打开官方卖家工作台页面。
  - 只监听 allowlist 中的只读 `mtop` 响应。
  - 不主动调用发布、下架、删除、更新接口。
- 验证通过的只读接口：
  - `mtop.taobao.idle.seller.platform.pc.item.status.statistics`：返回成功，统计列表数量 `2`。
  - `mtop.alibaba.idle.seller.pc.common.item.search`：返回成功，商品列表数量 `2`，样例商品 ID `1059889885905`、`949419974611`。
  - `mtop.taobao.idle.seller.platform.item.pc.search.categories`：返回成功，类目候选数量 `99`。
  - `mtop.idle.pc.backend.idleitem.preget`：返回成功，包含 `commissionConfig/needUpFirstHandItem/supportSkuOrInventory/violationInfo`。
  - `mtop.alibaba.idle.seller.platform.freight.template.pc.all`：返回成功，模板列表数量 `0`。
  - `mtop.taobao.idle.local.poi.get`：返回成功，常用地址 `6`，附近地址 `10`。
- 未触发 mutation API：`mutation_api_hits` 为空。
- 未完成的只读接口：
  - `mtop.taobao.idle.item.pc.category.list`
  - `mtop.taobao.idle.seller.platform.item.pc.category.property.query`
  - 判断：这两个更可能需要搜索/选择类目后触发，不能靠页面初始加载完成。
- 调用形态结论：
  - “后端 `requests` 直接复刻 mtop”仍未证明可行。
  - “Playwright 浏览器会话 + storage state + response 监听”已证明可读取核心只读数据。
  - 如果迁移官方工作台，短期更现实的是新增浏览器会话适配器，而不是替换成纯后端 HTTP client。

## 阶段 5 受控副作用验证方案
### 安全边界
- 用户说“继续”只视为继续准备方案，不视为授权真实发布、保存草稿、下架或删除。
- 任何会在官方闲鱼账号中新增、修改、下架或删除数据的动作，都必须在执行前再次确认。
- 确认时需要明确目标账号、动作、测试商品标题、价格、库存，以及是否立即下架/删除。

### 可选验证路径
| 路径 | 目标 | 风险 | 证明力 | 是否需要确认 |
|------|------|------|------|------|
| 草稿验证 | 走发布表单/接口到草稿或草稿发布接口，验证 payload、图片、类目、价格字段能被工作台接受 | 会在账号侧产生草稿；不影响前台售卖 | 中等，不能证明正式上架 | 需要 |
| 正式发布验证 | 发布一个明显的测试商品，拿到商品 ID，随后验证列表可见、可下架/删除 | 会短暂产生真实在售商品 | 最高，能证明替代 OpenAPI 的核心链路 | 需要 |
| 继续只读验证 | 只补类目属性、上传接口观察，不创建商品 | 无账号侧业务数据副作用 | 较低，不能证明发布成功 | 不需要或弱确认 |

### 推荐测试商品配置
| 字段 | 建议值 | 理由 |
|------|------|------|
| 标题 | `[POC勿拍] 官方卖家工作台适配器联调测试 YYYYMMDD-HHMM` | 一眼识别测试商品，避免误购 |
| 描述 | `系统联调测试商品，请勿拍，不发货。用于验证官方卖家工作台适配器发布链路。` | 明确告知买家和后续审计 |
| 价格 | `9999.00` | 极高价格降低误拍风险 |
| 原价 | `9999.00` 或留空 | 避免复杂促销字段 |
| 库存 | `1` | 降低误售风险 |
| 规格 | 单规格，无 SKU 图片 | 先验证最小发布链路，降低图片/属性绑定复杂度 |
| 图片 | 本地生成一张测试图，文字包含 `POC TEST DO NOT BUY` | 避免使用真实商品素材引发误导 |
| 发货 | 优先选择无需邮寄或工作台默认最小配置 | 降低真实履约风险 |
| 所在地 | 使用发布页当前默认所在地 | 避免额外触发定位/地址选择问题 |

### 执行前检查
- 只允许监听或触发以下目标动作：
  - 发布前预请求：`mtop.idle.pc.backend.idleitem.preget`
  - 正式发布候选：`mtop.idle.pc.backend.idleitem.publish` 或 `mtop.idle.pc.first.hand.idleitem.publish`
  - 草稿候选：`mtop.idle.idleitem.draft.publish`
- 执行前必须确认没有批量操作。
- 执行前必须确认标题包含 `[POC勿拍]`。
- 执行前必须确认价格为高价、库存为 `1`。
- 执行前必须打开响应监听，记录返回商品 ID 或错误码。

### 发布后验证与回滚
- 发布成功后立即到商品管理页确认：
  - 商品 ID
  - 标题
  - 价格
  - 库存
  - 状态/列表可见性
- 下架前再次确认下架动作，目标为刚发布的测试商品 ID。
- 删除前再次确认删除动作，目标为刚发布的测试商品 ID。
- 如果发布失败，只记录 mtop ret/code/msg，不重试超过 1 次，避免触发风控。

### 阶段 5 当前状态
- 准备方案已完成。
- 用户已明确授权正式发布测试商品。
- 已完成正式发布验证；下架/删除仍需用户再次确认。

## 阶段 5 正式发布验证结果
- 执行脚本：`scripts/probe_seller_workbench_publish_poc.py`。
- 输出文件：`scratch/seller-workbench-poc/publish-result.json`。
- 截图文件：`scratch/seller-workbench-poc/publish-result.png`。
- 测试商品：
  - 标题：`[POC勿拍] 官方卖家工作台适配器联调测试 20260705-1421`
  - 价格：`9999.00`
  - 库存：`1`
  - 图片：`scratch/seller-workbench-poc/poc-do-not-buy.png`
- 发布接口：
  - `mtop.idle.pc.backend.idleitem.publish`
  - HTTP 状态：`200`
  - ret：`SUCCESS::调用成功`
  - 返回商品 ID：`1063238250794`
- 发布成功页：
  - URL 包含 `#/seller-item/publish/success?itemId=1063238250794`
  - 页面显示“发布成功”“查看商品”“编辑商品”
- 商品管理页验证：
  - 在卖数量从 `2` 变为 `3`
  - 新商品出现在列表第一条
  - 商品 ID：`1063238250794`
  - 价格：`¥9999.00`
  - 库存：`1`
  - 创建时间：`2026-07-05 14:22:02`
  - 可见操作：`编辑`、`改价`、`设置粉丝价`、`下架`
- 结论：
  - 官方卖家工作台的浏览器会话适配器可以完成最小正式发布链路。
  - 已证明可获取发布返回商品 ID，并能在商品管理页验证上架状态。
  - 下架能力已完成验证；删除能力尚未执行。

## 阶段 5 下架验证结果
- 用户确认：`确认下架 1063238250794`。
- 执行脚本：`scripts/probe_seller_workbench_offline_poc.py`。
- 输出文件：`scratch/seller-workbench-poc/offline-result.json`。
- 截图文件：`scratch/seller-workbench-poc/offline-result.png`。
- 第一次尝试：
  - 只打开了“立即下架”确认弹窗，未点击到弹窗中的 `确 定` 按钮。
  - 未触发下架接口，商品仍在在卖列表。
  - 这是安全失败，没有误操作其他商品。
- 第二次尝试：
  - 修复脚本对 `确 定` 按钮文案的识别。
  - 下架接口：`mtop.alibaba.idle.seller.pc.item.offline`
  - HTTP 状态：`200`
  - ret：`SUCCESS::调用成功`
  - code/msg：`success` / `成功`
- 商品管理页验证：
  - 下架前：在卖 `3`，下架 `65`
  - 下架后：在卖 `2`，下架 `66`
  - 在卖列表不再包含商品 ID `1063238250794`
- 结论：
  - 官方卖家工作台浏览器会话适配器可完成单商品下架链路。
  - 删除能力已完成验证。

## 阶段 5 删除验证结果
- 用户确认：`确认删除 1063238250794，请用无头浏览器操作`。
- 执行方式：无头浏览器。
- 执行脚本：`scripts/probe_seller_workbench_delete_poc.py`。
- 输出文件：`scratch/seller-workbench-poc/delete-result.json`。
- 截图文件：`scratch/seller-workbench-poc/delete-result.png`。
- 删除接口：
  - `mtop.alibaba.idle.seller.pc.item.delete`
  - HTTP 状态：`200`
  - ret：`SUCCESS::调用成功`
  - code/msg：`success` / `成功`
- 商品管理页验证：
  - 删除前下架列表包含商品 ID `1063238250794`，标题包含 `[POC勿拍]`
  - 删除后下架数量从 `66` 回到 `65`
  - 下架列表不再包含商品 ID `1063238250794`

## 阶段 7：交易/订单只读能力验证
### 交易域入口
- 官方交易域前端包：`https://g.alicdn.com/idle-pc/idle-seller-trade/0.0.24/js/main.js`。
- 静态解析结果：bundle 大小 `3854398` 字符，识别 `71` 个 `mtop.*` API。
- 正确路由：
  - 订单管理：`#/seller-trade/order-manage`
  - 退款管理：`#/seller-trade/refund-manage`
  - 评价管理：`#/seller-trade/evaluation-manage`
  - 投诉管理：`#/seller-trade/complaint-manage`
  - 退货地址：`#/seller-trade/refund-address`
- 错误/不可用路由：
  - `#/seller-trade/order-list` 页面显示“禁止访问”。
  - `#/seller-trade/rate-manage` 不是评价管理真实路由。

### 只读页面验证结果
- 订单管理：
  - 接口：`mtop.taobao.idle.trade.merchant.sold.get`
  - 统计接口：`mtop.taobao.idle.merchant.order.count`
  - 页面状态：可进入订单管理页；当前账号订单列表返回 `0` 条，统计包含全部、待付款、待发货、已发货、售后中等状态。
  - 请求结构：`pageNumber`、`rowsPerPage`、`queryCode`、`orderSearchParam`、`orderIds`。
- 退款管理：
  - 接口：`mtop.taobao.idle.merchant.refund.list`
  - 页面状态：当前账号退款列表返回 `1` 条，页面展示售后编号、订单号、申请时间、退款类型等信息。
  - 脱敏字段结构：`buyerInfoVO`、`commonData.orderId/itemId/orderStatus/refundStatus`、`itemVO.title/itemPicUrl`、`priceVO.refundFee`、`refundInfoVO.refundId/refundType/refundStatus/reason`、`rightVO.btnList`。
- 退货地址：
  - 接口：`mtop.alibaba.idle.seller.platform.merchant.delivery.address.list.query`
  - 页面状态：当前账号退货地址列表返回 `1` 条。
  - 脱敏字段结构：`contactId/contactName/mobilePhone/provinceName/cityName/districtName/detailAddress/defaultAddr/zipCode`。
- 评价管理：
  - 接口：`mtop.taobao.idle.merchant.rate.list`
  - 页面状态：当前账号评价列表返回 `0` 条；页面含待卖家评价、批量评价入口。
- 投诉管理：
  - 接口：`mtop.taobao.idle.cco.shop.complain.list`
  - 页面状态：当前账号投诉列表返回 `0` 条；页面含待卖家处理、待客服处理、待买家处理等状态统计。

### 静态包中的潜在副作用接口
- 发货/物流：
  - `mtop.taobao.idle.logistics.merchant.consign.page.render`
  - `mtop.taobao.idle.logistics.merchant.consign.offline`
  - `mtop.taobao.idle.logistics.merchant.consign.dummy`
  - `mtop.taobao.idle.logistics.merchant.consign.resend`
  - `mtop.taobao.idle.logistics.merchant.excel.consign.offline`
  - `mtop.taobao.idle.logistics.guess.mailno`
- 退款/售后处理：
  - `mtop.taobao.idle.merchant.refund.detail`
  - `mtop.taobao.idle.merchant.refund.agree.refund`
  - `mtop.taobao.idle.merchant.refund.refuse`
  - `mtop.taobao.idle.merchant.refund.refuse.render`
  - `mtop.taobao.idle.merchant.postage.refund.pay`
  - `mtop.taobao.idle.merchant.postage.refund.refuse`
- 订单动作：
  - `mtop.taobao.idle.trade.merchant.close.by.seller`
  - `mtop.taobao.idle.trade.merchant.batch.delay.confirm`
  - `mtop.taobao.idle.trade.merchant.batch.remind.confirm`
  - `mtop.taobao.idle.trade.merchant.user.adjust.price`
  - `mtop.taobao.idle.trade.merchant.adjust.price.render`
  - `mtop.idle.merchant.order.address.modify.agree`
  - `mtop.idle.merchant.order.address.modify.refuse`
- 评价/投诉/地址：
  - `mtop.taobao.idle.merchant.rate.create`
  - `mtop.taobao.idle.cco.shop.complain.apply.revoke`
  - `mtop.taobao.idle.cco.shop.complain.refuse`
  - `mtop.alibaba.idle.seller.platform.merchant.delivery.address.add`
  - `mtop.alibaba.idle.seller.platform.merchant.delivery.address.update`
  - `mtop.alibaba.idle.seller.platform.merchant.delivery.address.delete`
  - `mtop.alibaba.idle.seller.platform.merchant.delivery.address.set.default`

### 阶段 7 结论
- 官方卖家工作台交易域具备订单、退款、退货地址、评价、投诉的只读列表能力。
- 发货、退款同意/拒绝、改价、关闭订单、评价、投诉处理、地址新增/修改/删除等副作用能力在静态包中存在，但尚未做受控执行验证。
- 订单列表当前账号为 `0` 条，暂时只能验证列表接口与请求结构；后续若要做订单详情/发货 POC，需要有待发货测试订单或用户明确授权创建测试交易场景。
- 交易域同样依赖浏览器登录态、mtop 签名和风控上下文；短期仍推荐通过 Playwright 浏览器会话适配器接入，不建议纯后端 `requests` 复刻。
  - 下架列表不再包含 `[POC勿拍]`
- 结论：
  - 官方卖家工作台浏览器会话适配器可完成单商品删除链路。

## 阶段 6 最终结论
- 可替代性判断：官方卖家工作台具备替代闲管家 OpenAPI 的核心能力，但替代方式不应是后端直接 `requests` 调 mtop。
- 已验证能力：
  - 商品管理列表/状态只读读取。
  - 发布预请求、运费模板、所在地、类目搜索等只读读取。
  - 正式发布测试商品并拿到商品 ID。
  - 商品管理页验证发布状态。
  - 单商品下架。
  - 单商品删除。
- 推荐架构：
  - 保留当前 `PublisherV3` / 闲管家 OpenAPI 作为稳定主链路或兜底。
  - 新增官方卖家工作台 `SellerWorkbenchAdapter`，基于 Playwright 浏览器会话和 `xianyu_state.json` / storage state 工作。
  - 适配器能力先覆盖：`list_items`、`publish_item`、`offline_item`、`delete_item`。
  - 适配器必须内置安全保护：单商品定位、标题/ID 双校验、强制确认参数、mutation API allowlist、操作后页面验证。
- 不建议：
  - 不建议直接复刻 mtop 签名做纯后端 HTTP client。直接重放已签名 URL 已返回非法请求，且 mtop 依赖浏览器登录态、签名、AutoLoginOnly 和风控脚本。
  - 不建议一次性替换当前 OpenAPI 主链路。工作台适配器对浏览器环境、页面 DOM 和风控更敏感。
- 主要剩余风险：
  - 图片上传依赖 `@ali/speedster-media-upload` / 媒体对象，生产化需要封装上传结果校验。
  - 类目和属性 ID 与 OpenAPI 当前字段体系不一致，需要新增类目推荐/属性查询映射层。
  - 多 SKU、SKU 图片、品牌/成色/功能状态等复杂类目字段尚未做完整真实发布验证。
  - 多账号/子账号切换依赖浏览器登录态，需要和现有账号池配置统一。
  - 页面 DOM 和 mtop 入参可能随官方工作台前端版本变化，需要探针/告警。
- 建议下一步工程任务：
  - 抽象 `SellerWorkbenchAdapter`，复用当前 POC 脚本中的 Playwright 会话、response 监听、确认保护和页面验证逻辑。
  - 增加配置开关：OpenAPI / 官方工作台 / 双适配器灰度。
  - 增加最小回归脚本：只读列表、发布测试草稿/测试商品、下架、删除。
  - 把 POC 脚本中的业务动作保护保留到生产：必须校验商品 ID、标题标记和目标账号。

## 遇到的问题
| 问题 | 解决方案 |
|------|---------|
| 直接打开页面资源中的已签名 `h5api` URL 会返回 `FAIL_SYS_ILLEGAL_ACCESS::非法请求` | 说明 mtop URL 不能简单重放，后续需要捕获原请求 body/运行时上下文，或在浏览器页面上下文内发起 |

## 资源
- `src/xianyu_tools/xianyu_adapter/publisher_v3.py`
- `src/web_api/main.py`
- `docs/xianguanjia_openapi_guide.md`
- `https://seller.goofish.com/?site=COMMONPRO#/seller-item/publish`
- `https://seller.goofish.com/?site=COMMONPRO#/seller-item/goods-manage`

## 视觉/浏览器发现
- 登录后发布页标题为“商品发布 - 闲鱼卖家工作台”。
- 发布页可见“宝贝图片、宝贝视频、宝贝描述、商品规格、价格、原价、库存、发货设置、宝贝所在地、发布按钮”。
- 商品管理页标题为“商品管理 - 闲鱼卖家工作台”。
- 商品管理页可见商品列表、商品链接、商品 ID、下架、批量下架、筛选输入框。
- 商品管理页已观察到真实商品链接示例，页面可直接展示 `https://www.goofish.com/item?id=...` 形式的闲鱼商品 ID。
- 直接在新标签打开 `pc.item.status.statistics` 和 `common.item.search` 的已签名 URL，均返回 `FAIL_SYS_ILLEGAL_ACCESS::非法请求`，说明不是复制 URL 就能服务端调用。
- 商品管理页渲染数据可见：
  - 在卖 2、下架 65
  - 商品 `1059889885905`，标题“半甜初品黑糯米千层蛋糕券”，价格 `¥29.99`，库存 `2`，创建时间 `2026-06-17 19:36:58`
  - 商品 `949419974611`，标题“[闪亮]全新现货[闪亮]”，价格 `¥328.00`，库存 `1`，创建时间 `2025-07-08 13:56:01`
  - 操作入口包括“设置粉丝价”“下架”“批量下架”
- 发布页渲染字段可见：
  - 上传：宝贝图片、宝贝视频
  - 文本：宝贝描述，`0/1500`
  - 商品规格：添加规格类型，最多 `0/2`
  - 价格：价格、原价、库存
  - 发货：包邮、按距离计费、一口价、运费模版、无需邮寄、支持自提、邮费
  - 所在地：北京 东城区
- 发布页已加载的 mtop 只读/预请求接口包括：
  - `mtop.idle.pc.backend.idleitem.preget`
  - `mtop.alibaba.idle.seller.platform.freight.template.pc.all`
  - `mtop.taobao.idle.local.poi.get`
  - `mtop.taobao.idle.seller.platform.item.pc.search.categories`
  - `mtop.taobao.idle.seller.platform.item.pc.fix.search.term.query`
  - `mtop.taobao.idle.seller.platform.pc.item.status.statistics`
  - `mtop.alibaba.idle.seller.pc.common.item.search`
- 官方发布函数线索显示最终发布 payload 会包含：
  - `itemTextDTO`：标题、描述、标题描述分离标记
  - `itemCatDTO`：类目相关 ID
  - `itemPriceDTO`：售价和原价，单位分
  - `itemPostFeeDTO`：包邮、运费、模板等
  - `itemSkuList`：SKU 价格、库存、属性列表
  - `imageInfoDOList`：主图和视频媒体对象
  - `propertyImageList`：SKU 属性图片
  - `itemAddrDTO`：所在地
  - `uniqueCode/sourceId/bizcode/publishScene`：工作台发布上下文

---
*每执行2次查看/浏览器/搜索操作后更新此文件*
*防止视觉信息丢失*
