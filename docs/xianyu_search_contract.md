# Xianyu Search Output Contract

## Goal

闲鱼搜索输出需要固定成稳定结构，避免脚本层、workflow 层和后续处理层各自维护一套格式。

当前统一约定：

- 搜索脚本输出单层 JSON
- sourcing 输出单层 JSON
- workflow 输出单层 JSON


## Top-Level Shape

当前搜索相关输出统一为：

```json
{
  "search_returned_count": 30,
  "search_items": []
}
```

语义：

- `search_returned_count`
  本次实际搜索返回的商品条数
- `search_items`
  本次搜索返回的全部商品列表


## search_items Contract

每条搜索结果当前固定保留这些字段：

- `item_id`
- `title`
- `price`
- `original_price`
- `seller_name`
- `area`
- `publish_time`
- `item_url`
- `image_url`
- `tags`


## URL Contract

`item_url` 统一输出短链：

```text
https://www.goofish.com/item?id=<item_id>
```

不保留追踪参数，不保留长 query 参数。


## Metadata Rule

默认输出不包含 `metadata`。

只有显式要求保留原始调试信息时，才允许输出 `metadata`。


## Extension Fields

如果某条搜索商品进入后续匹配流程，可以在该条 `search_items` 上追加字段。

当前允许追加：

- `source_keyword`
- `top_candidates`

这类扩展字段只能挂在商品条目本身下面，不再引入单独的 `items` 列表。


## CLI Contract

### `run_xianyu_search.py`

默认 `json` 输出：

```json
{
  "search_returned_count": 30,
  "search_items": [...]
}
```

`table` 输出仅用于人读，不改变 JSON 契约。


### `run_xianyu_sourcing.py`

输出仍保持：

- `search_returned_count`
- `search_items`

其中参与匹配的条目会追加：

- `source_keyword`
- `top_candidates`


### `run_xianyu_workflow.py`

输出仍保持：

- `search_returned_count`
- `search_items`

workflow 只是在同一结构上叠加更多阶段结果，不再引入新的平级列表。
