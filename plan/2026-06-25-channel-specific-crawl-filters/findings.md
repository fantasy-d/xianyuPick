# 发现与决策：按渠道配置 1688 商品列表筛选项

> 状态：已根据 2026-06-27 新需求重新细化，供后续实施直接消费

## 1. 需求重述

用户新增要求：

1. 1688 列表页中的以下条件要做成配置项：
   - 极速开票
   - 分销严选
   - 一件代发
   - 7天无理由
   - 1件代发包邮
   - 包邮
   - 退货包运费
   - 真实工厂认证
   - 实力认证
   - 官方物流
   - 密文面单
2. 这些配置项必须放在“商品爬取与筛选配置”中。
3. 这些配置项必须按不同渠道区分。
4. 修计划时要同步考虑：
   - 决策资产库中的资产应展示使用了哪些渠道
   - 详情页应按渠道分区展示结果与策略

## 2. 已确认事实

### 2.1 共享筛选定义已经存在，且已覆盖密文面单

文件：

- `src/xianyu_tools/channel_search_filters.py`
- `web/app.jsx`

结论：

- 11 个筛选项并不是从零开始建模
- 当前代码里已经有统一 key/label/group 定义
- 说明本轮更像“把已有定义升级成渠道级配置与落地实施计划”

### 2.2 当前系统已经支持“按渠道管理抓取配置”

文件：

- `src/xianyu_tools/config.py`
- `web/app.jsx`
- `plan/2026-06-22-crawl-source-channel-config/task_plan.md`

结论：

- 渠道选择能力已存在
- 本次无需重做渠道维度
- 只需把筛选条件附着到渠道之下

### 2.3 当前 query 级强证据并不覆盖 11 个全部项

文件：

- `src/xianyu_tools/channel_search_filters.py`
- `src/xianyu_tools/source_adapter/ali1688.py`
- `scripts/validate_source_channel_config.py`

结论：

- 当前更适合把 11 个项拆成四类：
  - query candidate
  - ui checkbox candidate
  - semantic combo candidate
  - special panel candidate
- 这样能避免“一刀切把所有项都强行接进 runtime”

### 2.4 决策资产库与详情页已经有“按渠道分区”的基础

文件：

- `src/web_api/main.py`
- `web/app.jsx`

结论：

- 用户新增要求不是要推翻现有详情页结构
- 而是在既有渠道分组之上，补渠道筛选摘要与追溯解释

## 3. 11 个筛选项的当前判断

| key | 文案 | 当前判断 | 说明 |
|---|---|---|---|
| `rapid_invoice` | 极速开票 | query candidate | 适合优先验证 |
| `selected_distributors` | 分销严选 | ui checkbox candidate | 需页面证据 |
| `single_piece_drop_shipping` | 一件代发 | strong query candidate | 当前最成熟 |
| `seven_day_return` | 7天无理由 | ui checkbox candidate | 需页面证据 |
| `single_piece_free_shipping` | 1件代发包邮 | semantic combo candidate | 可能是组合语义 |
| `free_shipping` | 包邮 | query candidate | 可继续推进 |
| `freight_insurance_return` | 退货包运费 | query candidate | 可继续推进 |
| `real_factory_verified` | 真实工厂认证 | ui checkbox candidate | 需页面证据 |
| `strength_verified` | 实力认证 | ui checkbox candidate | 需页面证据 |
| `official_logistics` | 官方物流 | query candidate | 可继续推进 |
| `encrypted_waybill` | 密文面单 | special panel candidate | 需确认是否在特殊区域 |

## 4. 本轮计划细化后的关键决策

### 4.1 渠道筛选与排序必须继续分治

用户当前要求是：

- 按货源渠道筛选

不是：

- 把排序模式做成配置项

因此本轮继续坚持：

- 排序策略固定为“预估纯利倒序”
- 渠道筛选配置独立建模

### 4.2 顶层资产卡片与详情页承担不同信息密度

为了避免页面信息过载：

- 顶层资产卡片：只展示“用了哪些渠道”
- 详情页：再展示“每个渠道用了哪些筛选项”

### 4.3 对无证据项，先诚实记录，不伪造生效

适用项：

- 分销严选
- 7天无理由
- 真实工厂认证
- 实力认证
- 密文面单

结论：

- 先做配置可保存
- 先做快照可追溯
- 不直接声称“已生效”

## 5. 本轮调研还需补的证据

### 5.1 页面级证据

需要额外确认：

- `selected_distributors` 的真实控件定位方式
- `seven_day_return` 的稳定控件定位方式
- `real_factory_verified` / `strength_verified` 的勾选后反馈
- `encrypted_waybill` 是否属于列表页常规筛选区

### 5.2 结果级证据

需要确认：

- 哪些 query 参数在跳转后会被保留
- 哪些参数会被 1688 重写或丢弃
- 不同渠道使用同一组筛选项时，是否需要记录渠道特定说明

## 6. 本轮调研输出如何被实施消费

### 对配置层

- 决定 UI 要展示哪些项
- 决定默认值与渠道级隔离方式

### 对 runtime 层

- 决定第一批优先接入哪些项
- 决定哪些项先只做快照

### 对展示层

- 决定资产库顶层只展示渠道摘要
- 决定详情页按渠道展示筛选摘要

## 7. 后续实施建议顺序

1. 先把渠道级配置行为彻底收口
2. 再把快照/追溯链打透
3. 再逐项推进真实搜索能力映射

