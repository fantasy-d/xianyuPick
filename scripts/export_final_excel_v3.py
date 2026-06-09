import json
import re
from pathlib import Path
from datetime import datetime
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment

def sanitize_dir_name(name: str) -> str:
    clean = re.sub(r'[\\/:*?"<>|]', '_', name).strip()
    return clean[:30]

def style_header(sheet):
    header_font = Font(name="PingFang SC", size=12, bold=True, color="FFFFFF")
    header_fill = PatternFill(start_color="4F81BD", end_color="4F81BD", fill_type="solid")
    for cell in sheet[1]:
        cell.font = header_font
        cell.fill = header_fill
        cell.alignment = Alignment(horizontal="center")

def autosize_columns(sheet):
    for column in sheet.columns:
        max_length = 0
        column_letter = column[0].column_letter
        for cell in column:
            try:
                if len(str(cell.value)) > max_length:
                    max_length = len(str(cell.value))
            except: pass
        sheet.column_dimensions[column_letter].width = min(max_length + 4, 50)

def write_sheet(wb, title, rows):
    if not rows:
        ws = wb.create_sheet(title)
        ws.append(["暂无数据"])
        return
    ws = wb.create_sheet(title)
    headers = list(rows[0].keys())
    ws.append(headers)
    for r in rows:
        ws.append([r.get(h) for h in headers])
    style_header(ws)
    autosize_columns(ws)

def main():
    keyword = "人体工学椅"
    date_str = datetime.now().strftime("%Y%m%d")
    root_dir = Path(f"outputs/{keyword}_{date_str}")
    
    if not root_dir.exists():
        print(f"Directory {root_dir} not found.")
        return

    # 1. 加载数据
    xianyu_json = root_dir / "xianyu_hot_items.json"
    if not xianyu_json.exists(): return
    hot_items = json.loads(xianyu_json.read_text()).get("hot_items", [])

    # 2. 准备 Sheet 数据
    overview_rows = []
    profit_calc_rows = []
    source_candidates = []
    hot_item_rows = []

    for i, item in enumerate(hot_items, start=1):
        item_id = str(item.get("hot_item_id"))
        safe_title = sanitize_dir_name(item.get("title", "item"))
        item_dir = root_dir / f"Rank_{i}_{safe_title}"
        
        best_price = 999999.0
        best_source = None

        if item_dir.exists():
            # 同时扫描 CSV 和 JSON
            for csv_file in item_dir.glob("*.csv"):
                if "结论分析表" in csv_file.name: continue
                offer_id = csv_file.stem.split("_")[-1]
                source_title = csv_file.stem.rsplit("_", 1)[0]
                
                # 寻找最低价
                current_min = 999999.0
                import csv
                try:
                    with open(csv_file, newline='', encoding='utf-8-sig') as f:
                        reader = csv.DictReader(f)
                        for row in reader:
                            p = float(row.get("价格") or 999999.0)
                            if p < current_min: current_min = p
                except: continue

                if current_min == 999999.0: continue

                source_info = {
                    "闲鱼Rank": i,
                    "货源标题": source_title,
                    "最低价格": current_min,
                    "OfferID": offer_id,
                    "货源链接": f"https://detail.1688.com/offer/{offer_id}.html"
                }
                source_candidates.append(source_info)
                if current_min < best_price:
                    best_price = current_min
                    best_source = source_info

        # 闲鱼热品 Sheet
        hot_item_rows.append({
            "排名": i,
            "想要人数": item.get("want_count"),
            "标题": item.get("title"),
            "售价": item.get("price"),
            "链接": item.get("item_url")
        })

        # 利润测算 & 筛选总览
        margin = "N/A"
        if best_source:
            margin = item["price"] - best_price - 20 - (item["price"] * 0.006)
            profit_calc_rows.append({
                "排名": i,
                "闲鱼售价": item["price"],
                "1688最低成本": best_price,
                "预估利润": round(margin, 2),
                "状态": "高利润" if margin > 50 else "可盈利" if margin > 0 else "无利润"
            })

        overview_rows.append({
            "Rank": i,
            "想要人数": item["want_count"],
            "闲鱼售价": item["price"],
            "1688成本": best_price if best_source else "未找到",
            "利润": round(margin, 2) if isinstance(margin, float) else "N/A",
            "决策": "上架" if isinstance(margin, float) and margin > 0 else "放弃"
        })

    # 3. 生成 Excel
    wb = Workbook()
    # 移除默认 sheet
    wb.remove(wb.active)
    
    write_sheet(wb, "筛选总览", overview_rows)
    write_sheet(wb, "利润测算", profit_calc_rows)
    write_sheet(wb, "1688货源候选Top100", source_candidates)
    write_sheet(wb, "闲鱼热品", hot_item_rows)

    excel_path = root_dir / f"{keyword}_深度分析报表_标准多Sheet版.xlsx"
    wb.save(excel_path)
    print(f"Success: Real multi-sheet Excel generated at: {excel_path.resolve()}")

if __name__ == "__main__":
    main()
