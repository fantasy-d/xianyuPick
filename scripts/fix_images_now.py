import json
import asyncio
import pymysql
from pathlib import Path
from playwright.async_api import async_playwright
from xianyu_tools.source_adapter.ali1688 import Ali1688SourceAdapter

async def fix_missing_images():
    print("=== 正在执行全量货源图片补抓任务 ===")
    
    # 1. 链接数据库
    config = json.load(open("config/database.json"))
    conn = pymysql.connect(**config)
    cursor = conn.cursor(pymysql.cursors.DictCursor)
    
    # 2. 找到最近 5 条没有图片的 1688 货源
    cursor.execute("SELECT id, source_url, title FROM ali1688_sources WHERE images IS NULL OR images = '[]' ORDER BY id DESC LIMIT 5")
    sources = cursor.fetchall()
    
    if not sources:
        print("[*] 没发现缺失图片的活跃货源。")
        return

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context()
        
        for s in sources:
            print(f"[*] 正在为货源 [{s['id']}] 抓取图片: {s['title'][:20]}...")
            page = await context.new_page()
            try:
                # 访问 1688 详情页
                await page.goto(s['source_url'], wait_until="domcontentloaded", timeout=30000)
                await asyncio.sleep(3)
                
                # 简单解析页面中的图片 (寻找常见的 1688 详情图/主图特征)
                # 这里我们直接从 DOM 中找
                imgs = await page.evaluate("""
                    () => {
                        const list = [];
                        document.querySelectorAll('.tab-pane img, .desc-custom-area img').forEach(img => {
                            if(img.src && img.src.includes('alicdn.com')) list.append(img.src);
                        });
                        // 兜底主图
                        document.querySelectorAll('.detail-gallery img').forEach(img => {
                            if(img.src) list.push(img.src);
                        });
                        return [...new Set(list)].slice(0, 5);
                    }
                """)
                
                if imgs:
                    img_json = json.dumps(imgs, ensure_ascii=False)
                    cursor.execute("UPDATE ali1688_sources SET images = %s WHERE id = %s", (img_json, s['id']))
                    conn.commit()
                    print(f"  [√] 成功补抓到 {len(imgs)} 张图片。")
                else:
                    print("  [x] 未能在页面找到图片。")
            except Exception as e:
                print(f"  [!] 抓取失败: {e}")
            finally:
                await page.close()
        
        await browser.close()
    conn.close()

if __name__ == "__main__":
    asyncio.run(fix_missing_images())
