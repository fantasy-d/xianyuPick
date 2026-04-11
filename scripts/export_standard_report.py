import json
import csv
import re
from pathlib import Path
from datetime import datetime

def sanitize_dir_name(name: str) -> str:
    clean = re.sub(r'[\\/:*?"<>|]', '_', name).strip()
    return clean[:30]

def main():
    keyword = "人体工学椅"
    date_str = datetime.now().strftime("%Y%m%d")
    root_dir = Path(f"outputs/{keyword}_{date_str}")
    
    if not root_dir.exists():
        print(f"Directory {root_dir} not found.")
        return

    # 1. 加载闲鱼数据
    xianyu_json = root_dir / "xianyu_hot_items.json"
    if not xianyu_json.exists():
        print("Xianyu data missing.")
        return
    hot_items = json.loads(xianyu_json.read_text()).get("hot_items", [])

    # 2. 准备标准 Sheet 数据
    overview_rows = []      # 筛选总览
    hot_item_rows = []      # 闲鱼热品
    match_results = []      # 货源匹配结果
    source_candidates = []  # 1688货源候选 (这里要放 Top 10 * 10 = 100个)
    profit_calc_rows = []   # 利润测算 (基于每个热品的最优货源)

    for i, item in enumerate(hot_items, start=1):
        item_id = str(item.get("hot_item_id"))
        safe_title = sanitize_dir_name(item.get("title", "item"))
        item_dir = root_dir / f"Rank_{i}_{safe_title}"
        
        best_price = 999999.0
        best_source = None
        item_sources = []

        # 遍历该商品下的 10 个货源
        if item_dir.exists():
            # 优先从 API Raw 数据中提取 1688 标题和链接
            api_raw_files = sorted(list(item_dir.glob("api_raw_*.json")))
            csv_files = sorted(list(item_dir.glob("*.csv")))
            
            for csv_file in csv_files:
                if "结论分析表" in csv_file.name: continue
                # 提取 OfferID
                offer_id = csv_file.stem.split("_")[-1]
                source_title = csv_file.stem.rsplit("_", 1)[0]
                
                # 获取该货源的最低价
                current_min = 999999.0
                try:
                    with open(csv_file, newline='', encoding='utf-8-sig') as f:
                        reader = csv.DictReader(f)
                        for row in reader:
                            p = float(row.get("价格") or 999999.0)
                            if p < current_min: current_min = p
                except: continue

                if current_min == 999999.0: continue

                source_info = {
                    "闲鱼商品ID": item_id,
                    "货源标题": source_title,
                    "最低价格": current_min,
                    "OfferID": offer_id,
                    "货源链接": f"https://detail.1688.com/offer/{offer_id}.html"
                }
                source_candidates.append(source_info)
                item_sources.append(source_info)

                if current_min < best_price:
                    best_price = current_min
                    best_source = source_info

        # 填充各 Sheet
        hot_item_rows.append({
            "排名": i,
            "想要人数": item.get("want_count"),
            "标题": item.get("title"),
            "售价": item.get("price"),
            "卖家": item.get("seller_name"),
            "链接": item.get("item_url")
        })

        match_results.append({
            "闲鱼商品ID": item_id,
            "匹配状态": "成功" if best_source else "失败",
            "货源数": len(item_sources)
        })

        margin = "N/A"
        if best_source:
            margin = item["price"] - best_price - 20 - (item["price"] * 0.006)
            profit_calc_rows.append({
                "闲鱼ID": item_id,
                "闲鱼售价": item["price"],
                "1688最优成本": best_price,
                "预估利润": round(margin, 2),
                "建议": "高利润" if margin > 50 else "可盈利" if margin > 0 else "无利润"
            })

        overview_rows.append({
            "Rank": i,
            "想要人数": item["want_count"],
            "闲鱼售价": item["price"],
            "1688最低价": best_price if best_source else "N/A",
            "利润": round(margin, 2) if isinstance(margin, float) else "N/A",
            "推荐": "是" if isinstance(margin, float) and margin > 0 else "否"
        })

    # 3. 输出符合项目标准的 Excel (CSV形式展示 Sheet)
    # 因为环境中 openpyxl 不稳定，我将生成一个前缀明确的 CSV 集合，或尝试生成一个合并的 CSV
    final_csv = root_dir / f"{keyword}_标准分析报表_固定格式.csv"
    
    # 模拟多 Sheet：将数据按块写入同一个 CSV，用分隔符分开
    with open(final_csv, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.writer(f)
        
        def write_block(title, rows):
            writer.writerow([f"=== Sheet: {title} ==="])
            if not rows:
                writer.writerow(["暂无数据"])
            else:
                headers = list(rows[0].keys())
                writer.writerow(headers)
                for r in rows:
                    writer.writerow([r.get(h) for h in headers])
            writer.writerow([]) # 空行分隔

        write_block("筛选总览", overview_rows)
        write_block("利润测算", profit_calc_rows)
        write_block("1688货源候选(Top 100)", source_candidates)
        write_block("闲鱼热品", hot_item_rows)
        write_block("货源匹配结果", match_results)

    print(f"Standard report (Multi-Sheet Style) generated at: {final_csv.resolve()}")

if __name__ == "__main__":
    main()
