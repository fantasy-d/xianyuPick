import json
from pathlib import Path

def main():
    xianyu_path = Path("outputs/xianyu_hot_items.json")
    if not xianyu_path.exists():
        print("Error: Xianyu data not found.")
        return

    xianyu_data = json.loads(xianyu_path.read_text())
    hot_items = xianyu_data.get("hot_items", [])
    
    report = []
    
    print(f"{'Rank':<4} | {'Want':<6} | {'XY Price':<8} | {'1688 Min':<8} | {'Margin':<8} | {'Status'}")
    print("-" * 60)

    for i, item in enumerate(hot_items, start=1):
        item_dir = Path(f"outputs/pipeline/item_{i}")
        parsed_path = item_dir / "09_detail_1_parsed_skus.json"
        
        source_price = None
        status = "No Source"
        margin = 0
        
        if parsed_path.exists():
            source_data = json.loads(parsed_path.read_text())
            price_summary = source_data.get("price_summary")
            if price_summary:
                source_price = price_summary.get("min_price")
                status = "Source Found"
            elif source_data.get("sku_details"):
                # 如果 summary 没拿到，从 sku_details 里取最小值
                prices = [float(s.get("price", 9999)) for s in source_data["sku_details"] if s.get("price")]
                if prices:
                    source_price = min(prices)
                    status = "Source Found (SKU)"

        if source_price:
            # 简单利润计算：闲鱼价格 - 1688价格 - 预估运费(20) - 手续费
            margin = item["price"] - source_price - 20 - (item["price"] * 0.006)
            if margin > 50:
                status = "High Profit"
            elif margin > 0:
                status = "Profitable"
            else:
                status = "Low/No Margin"

        report.append({
            "rank": i,
            "title": item["title"],
            "want_count": item["want_count"],
            "xianyu_price": item["price"],
            "source_price": source_price,
            "estimated_margin": round(margin, 2),
            "status": status,
            "xianyu_url": item.get("item_url"),
            "source_url": source_data.get("url") if parsed_path.exists() else None
        })

        source_price_str = f"{source_price:>8}" if source_price else "N/A"
        margin_str = f"{margin:>8.2f}" if source_price else "N/A"
        print(f"{i:<4} | {item['want_count']:<6} | {item['price']:<8.2f} | {source_price_str} | {margin_str} | {status}")

    # 保存最终报表
    final_output = Path("outputs/final_decision_report.json")
    final_output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print("-" * 60)
    print(f"Final report saved to: {final_output}")

if __name__ == "__main__":
    main()
