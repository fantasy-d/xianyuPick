import json
import csv
from pathlib import Path

def main():
    json_path = Path("outputs/final_decision_report.json")
    if not json_path.exists():
        print("Error: JSON report not found.")
        return

    data = json.loads(json_path.read_text(encoding="utf-8"))
    
    csv_path = Path("outputs/final_decision_report.csv")
    
    # 定义表头
    fieldnames = [
        "rank", "title", "want_count", "xianyu_price", 
        "source_price", "estimated_margin", "status", 
        "xianyu_url", "source_url"
    ]
    
    header_mapping = {
        "rank": "排名",
        "title": "商品标题",
        "want_count": "想要人数",
        "xianyu_price": "闲鱼售价",
        "source_price": "1688成本",
        "estimated_margin": "预估毛利",
        "status": "利润状态",
        "xianyu_url": "闲鱼链接",
        "source_url": "1688货源链接"
    }

    try:
        with open(csv_path, mode='w', encoding='utf-8-sig', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            
            # 写入中文表头
            writer.writerow(header_mapping)
            
            for item in data:
                writer.writerow(item)
                
        print(f"Excel-compatible CSV report saved to: {csv_path.resolve()}")
    except Exception as e:
        print(f"Error saving CSV: {e}")

if __name__ == "__main__":
    main()
