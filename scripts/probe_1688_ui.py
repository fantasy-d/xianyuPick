import asyncio
import json
from pathlib import Path
from playwright.async_api import async_playwright

from xianyu_tools.config import settings

async def probe_buttons():
    target_url = "https://detail.1688.com/offer/986504328531.html"
    runtime_cfg = settings.get_active_ali1688_runtime_config()
    state_file = runtime_cfg.get("state_file") or "state/source_channels/ali1688/ali1688-account-1/storage_state.json"
    
    async with async_playwright() as p:
        # 以带界面模式启动，方便您观察
        browser = await p.chromium.launch(headless=False, args=["--start-maximized"])
        context = await browser.new_context()
        if Path(state_file).exists():
            state = json.loads(Path(state_file).read_text())
            await context.add_cookies([{"name": c["name"], "value": c["value"], "domain": c["domain"], "path": c["path"]} for c in state.get("cookies", [])])

        page = await context.new_page()
        await page.goto(target_url)
        print("[*] 正在扫描页面上的所有文字和按钮...")
        await asyncio.sleep(10)

        # 抓取所有看起来像按钮的元素
        elements = await page.evaluate("""
            () => {
                return Array.from(document.querySelectorAll('button, span, div, a'))
                    .filter(el => el.innerText && el.innerText.length < 20)
                    .map(el => ({
                        text: el.innerText.trim(),
                        tag: el.tagName,
                        className: el.className
                    }))
                    .filter(el => el.text.includes('下载') || el.text.includes('图片') || el.text.includes('导出'));
            }
        """)

        print("\n[探测到的潜在按钮]:")
        for el in elements:
            print(f" - [{el['tag']}] '{el['text']}' | Class: {el['className']}")

        print("\n[*] 探测完成。请在打开的浏览器中按 F12 确认插件按钮的真实 Class。")
        await asyncio.sleep(30)
        await browser.close()

if __name__ == "__main__":
    asyncio.run(probe_buttons())
