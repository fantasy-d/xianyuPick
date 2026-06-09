import asyncio
import json
import re
from pathlib import Path
from playwright.async_api import async_playwright

def sanitize_cookies(cookies):
    allowed_fields = {"name", "value", "url", "domain", "path", "expires", "httpOnly", "secure", "sameSite"}
    clean_cookies = []
    for c in cookies:
        clean_c = {k: v for k, v in c.items() if k in allowed_fields}
        if "sameSite" in clean_c and clean_c["sameSite"] not in ["Strict", "Lax", "None"]:
            del clean_c["sameSite"]
        clean_cookies.append(clean_c)
    return clean_cookies

async def extract_raw_data():
    target_url = "https://detail.1688.com/offer/986504328531.html"
    state_file = "state/ali1688/storage_state.json"
    
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context()
        
        if Path(state_file).exists():
            state = json.loads(Path(state_file).read_text())
            await context.add_cookies(sanitize_cookies(state.get("cookies", [])))

        page = await context.new_page()
        print(f"[*] 正在打开: {target_url}")
        try:
            await page.goto(target_url, wait_until="domcontentloaded", timeout=60000)
            print("[*] 页面基本框架已加载，等待 10s 确保 JS 变量初始化...")
            await asyncio.sleep(10)
            
            data_summary = await page.evaluate("""
                () => {
                    const results = { source: 'none', images: [] };
                    const init = window.__INIT_DATA__;
                    if (init && init.data && init.data.item && init.data.item.images) {
                        results.source = 'INIT_DATA';
                        results.images = init.data.item.images.map(i => i.originalImageUri || i.fullName || i);
                    } else if (window.iDetailConfig && window.iDetailConfig.data) {
                        results.source = 'iDetailConfig';
                        results.images = window.iDetailConfig.data.item.images.map(i => i.originalImageUri || i.fullName);
                    }
                    
                    if (results.images.length === 0) {
                        results.source = 'DOM_FALLBACK';
                        const gallery = Array.from(document.querySelectorAll('.detail-gallery img, .img-box img'))
                            .map(img => img.src).filter(src => src.includes('alicdn.com'));
                        results.images = [...new Set(gallery)].slice(0, 10);
                    }
                    return results;
                }
            """)

            if data_summary['images']:
                print(f"\n[√] 成功提取到 {len(data_summary['images'])} 张主图 (来源: {data_summary['source']})")
                for i, url in enumerate(data_summary['images'][:5], 1):
                    print(f"  {i}. {url}")
            else:
                print("\n[x] 未能提取到任何主图链接。")
        except Exception as e:
            print(f"[!] 运行失败: {e}")
        finally:
            await browser.close()

if __name__ == "__main__":
    asyncio.run(extract_raw_data())
