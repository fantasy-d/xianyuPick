import json
from pathlib import Path
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill
from collections import Counter

# 这里的工具函数直接复用原脚本的逻辑，确保格式一致
def _style_sheet(sheet):
    header_font = Font(name="PingFang SC", size=14, bold=True)
    body_font = Font(name="PingFang SC", size=12)
    header_fill = PatternFill(fill_type="solid", fgColor="D9EAF7")
    for row_index, row in enumerate(sheet.iter_rows(), start=1):
        for cell in row:
            if row_index == 1:
                cell.font = header_font
                cell.fill = header_fill
            else:
                cell.font = body_font

def _autosize_sheet(sheet):
    for column_cells in sheet.columns:
        max_length = 0
        column_letter = column_cells[0].column_letter
        for cell in column_cells:
            value = "" if cell.value is None else str(cell.value)
            max_length = max(max_length, len(value))
        sheet.column_dimensions[column_letter].width = min(max(max_length + 2, 12), 60)

def _write_table_sheet(workbook, title, rows):
    sheet = workbook.create_sheet(title)
    if not rows:
        sheet.append(["暂无数据"])
        return
    headers = list(rows[0].keys())
    sheet.append(headers)
    for row in rows:
        sheet.append([row.get(header) for header in headers])
    _style_sheet(sheet)
    _autosize_sheet(sheet)

def main():
    # 1. 加载数据
    xianyu_path = Path("outputs/xianyu_hot_items.json")
    if not xianyu_path.exists():
        print("Xianyu data missing.")
        return
    
    xianyu_data = json.loads(xianyu_path.read_text())
    hot_items = xianyu_data.get("hot_items", [])
    
    # 2. 收集各阶段数据
    pipeline_rows = []
    hot_item_rows = []
    source_resolution_rows = []
    source_item_rows = []
    profit_rows = []
    listing_rows = []

    for i, item in enumerate(hot_items, start=1):
        item_id = str(item.get("hot_item_id"))
        item_dir = Path(f"outputs/pipeline/item_{i}")
        summary_path = item_dir / "summary.json"
        parsed_path = item_dir / "09_detail_1_parsed_skus.json"
        
        source_found = False
        best_source = {}
        margin = None
        
        if summary_path.exists():
            summary = json.loads(summary_path.read_text())
            top_candidates = summary.get("top_dispatch_candidates", [])
            if top_candidates:
                source_found = True
                best_source = top_candidates[0]
        
        if parsed_path.exists():
            parsed = json.loads(parsed_path.read_text())
            price_sum = parsed.get("price_summary")
            if price_sum:
                s_price = price_sum.get("min_price")
                margin = item["price"] - s_price - 20 - (item["price"] * 0.006)

        # 构造各 Sheet 所在的行
        hot_item_rows.append({
            "闲鱼商品ID": item_id,
            "标题": item.get("title"),
            "售价": item.get("price"),
            "想要人数": item.get("want_count"),
            "卖家名称": item.get("seller_name"),
            "图片链接": item.get("image_url"),
            "闲鱼链接": item.get("item_url")
        })

        source_resolution_rows.append({
            "闲鱼商品ID": item_id,
            "是否匹配成功": source_found,
            "匹配结果": "API抓取成功" if margin is not None else "待核实"
        })

        if source_found:
            source_item_rows.append({
                "闲鱼商品ID": item_id,
                "货源标题": best_source.get("title"),
                "货源价格": best_source.get("price"),
                "7天代发": best_source.get("seven_day_dispatch_count"),
                "货源链接": best_source.get("item_url")
            })

        if margin is not None:
            profit_rows.append({
                "闲鱼商品ID": item_id,
                "闲鱼售价": item["price"],
                "1688成本": item["price"] - margin - 20,
                "预估利润": round(margin, 2),
                "状态": "高利润" if margin > 50 else "可盈利" if margin > 0 else "无利润"
            })

        # 总览 Sheet
        pipeline_rows.append({
            "闲鱼ID": item_id,
            "想要人数": item.get("want_count"),
            "闲鱼售价": item.get("price"),
            "货源价格": item["price"] - margin - 20 if margin is not None else "N/A",
            "预估利润": round(margin, 2) if margin is not None else "N/A",
            "是否匹配": "是" if source_found else "否",
            "推荐上架": "是" if margin and margin > 0 else "否"
        })

    # 3. 创建 Workbook
    wb = Workbook()
    
    # 汇总页
    ws_sum = wb.active
    ws_sum.title = "汇总"
    ws_sum.append(["指标", "值"])
    ws_sum.append(["搜索品类", xianyu_data.get("xianyu_market", {}).get("category_keyword", "人体工学椅")])
    ws_sum.append(["热品数量", len(hot_items)])
    ws_sum.append(["匹配货源数", len(source_item_rows)])
    ws_sum.append(["高利润商品数", sum(1 for r in profit_rows if r["状态"] == "高利润")])
    _style_sheet(ws_sum)
    _autosize_sheet(ws_sum)

    # 其他页
    _write_table_sheet(wb, "筛选总览", pipeline_rows)
    _write_table_sheet(wb, "闲鱼热品", hot_item_rows)
    _write_table_sheet(wb, "货源匹配结果", source_resolution_rows)
    _write_table_sheet(wb, "1688货源候选", source_item_rows)
    _write_table_sheet(wb, "利润测算", profit_rows)

    output_file = Path("outputs/final_analysis_report.xlsx")
    wb.save(output_file)
    print(f"Standard Excel report saved to: {output_file.resolve()}")

if __name__ == "__main__":
    main()
