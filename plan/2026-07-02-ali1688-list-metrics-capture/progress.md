# 进度记录：1688 商品列表页指标采集

## 2026-07-02

### 已完成

- 创建计划目录：
  - `plan/2026-07-02-ali1688-list-metrics-capture`
- 创建规划文件：
  - `task_plan.md`
  - `findings.md`
  - `progress.md`
- 初步确认：
  - DB 字段已存在
  - 入库链路已读取对应 `res` 字段
  - API 详情已返回对应字段
  - 前端商品详情页已有基础展示入口

### 当前阶段

- 阶段 3：入库与 API 校验

### 下一步

1. 检查任务详情页货源列表卡片是否展示全部列表页指标。
2. 补 API / 页面级契约或 fixture，验证字段从 `summary.json` 进入 API。
3. 准备真实抓取样本做页面级验收。

## 2026-07-02 解析契约补齐

### 已完成

- 新增 `validate_ali1688_list_metrics_extraction_contract`。
- 修复 `scripts/run_ali1688_slow_flow.py` 中数量文本正则：
  - `月代发1k+`
  - `7天代发600+`
  - `铺货数100内`
  - `分销商数400+`
- 单点验证通过：

```bash
PYTHONPATH=src /opt/anaconda3/envs/mytools/bin/python -c 'from scripts.validate_source_channel_config import validate_ali1688_list_metrics_extraction_contract; validate_ali1688_list_metrics_extraction_contract(); print("ali1688-list-metrics-contract-ok")'
```

输出：

```text
ali1688-list-metrics-contract-ok
```

备注：
- 验证过程中出现的 MySQL 初始化失败来自导入 WebAPI 时的沙箱环境限制，不影响该解析契约。

### 链路确认

- `scripts/run_ali1688_slow_flow.py` 会把列表页指标写入 `item_data`。
- `_export_sku_from_detail_page()` 返回后只更新 `status / images / sku_items / sku_count`，不会覆盖列表页指标。
- `summary.json` 因此会保留列表页指标字段。
- `scripts/run_full_pipeline.py` 已把这些字段写入 `ali1688_sources`。
- `/api/task_details/{task_id}` 已返回这些字段。
- `web/app.jsx` 货源列表卡片已用 `sourceMetrics` 展示这些指标，并单独展示 `company_name`。

### 当前阻塞

- 已解除。服务已在 `127.0.0.1:8000` 成功重启。

## 2026-07-03 真实任务闭环

### 已完成

- 重启服务：

```bash
export PYTHONPATH=$PYTHONPATH:/Users/mac/PycharmProjects/mytools/xianyu-tools/src && /opt/anaconda3/envs/mytools/bin/uvicorn src.web_api.main:app --host 127.0.0.1 --port 8000
```

- 真实任务 `ec24a2fd` 已完成：
  - 关键词：`海飞丝洗发水`
  - 状态：`已完成`
  - 进度：`100`
  - 货源数：`100`

- API 验收：
  - `detail_count`: 10
  - `source_count`: 100
  - `company_name`: 100
  - `pickup_48h_text`: 14
  - `pickup_24h_text`: 14
  - `month_dispatch_text`: 19
  - `seven_day_dispatch_text`: 19
  - `listing_count_text`: 4
  - `distributor_count_text`: 19
  - `settled_years_text`: 20

- 页面验收：
  - 打开任务 `ec24a2fd`
  - 进入 Rank 9（闲鱼 DB_ID `273`）
  - 货源卡片实际显示：
    - `48H揽收98%`
    - `24H揽收88%`
    - `月代发100`
    - `7天代发100`
    - `铺货数100`
    - `分销商数5000+`
    - `入驻2年`
    - `商家: 上海涵潇电子商务有限公司`

### 校验命令

```bash
PYTHONPATH=src /opt/anaconda3/envs/mytools/bin/python -c 'from scripts.validate_source_channel_config import validate_ali1688_list_metrics_extraction_contract; validate_ali1688_list_metrics_extraction_contract(); print("ali1688-metrics-contract-ok")'
```

输出：

```text
ali1688-metrics-contract-ok
```

### 状态

- 阶段 3：`completed`
- 阶段 4：`completed`
- 阶段 5：`completed`
