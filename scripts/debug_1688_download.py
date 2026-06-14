import asyncio
import json
from pathlib import Path
from playwright.async_api import async_playwright

from xianyu_tools.config import settings

async def debug_download():
    target_url = "https://detail.1688.com/offer/986504328531.html"
    runtime_cfg = settings.get_active_ali1688_runtime_config()
    state_file = runtime_cfg.get("state_file") or "state/source_channels/ali1688/ali1688-account-1/storage_state.json"
    
    print(f"\n[*] 启动调试浏览器，目标页面: {target_url}")
    
    async with async_playwright() as p:
        # 启动可见浏览器以便观察
        browser = await p.chromium.launch(headless=False, args=["--start-maximized"])
        context = await browser.new_context()
        
        # 加载 1688 登录态
        if Path(state_file).exists():
            state = json.loads(Path(state_file).read_text())
            await context.add_cookies(state.get("cookies", []))
            print("[*] 已加载 1688 登录态。")

        page = await context.new_page()
        await page.goto(target_url, wait_until="domcontentloaded")
        
        print("[*] 页面已加载。正在寻找“商品图片下载”按钮...")
        await asyncio.sleep(5) # 等待页面完全渲染

        # 尝试几种可能的选择器
        try:
            # 方案 1: 通过文本内容寻找 (1688 详情页上方通常有个浮动的工具条或右侧有按钮)
            # 常见的类名可能包含: .download-btn, .image-download, 或者直接是 span 文本
            selectors = [
                "text='商品图片下载'",
                "text='下载图片'",
                ".video-download-btn", # 有时是在视频下载旁边
                ".img-download-btn"
            ]
            
            target_btn = None
            for sel in selectors:
                loc = page.locator(sel).first
                if await loc.is_visible():
                    print(f"[√] 找到按钮: {sel}")
                    target_btn = loc
                    break
            
            if target_btn:
                await target_btn.click()
                print("[*] 已点击下载按钮。正在等待弹窗...")
                await asyncio.sleep(3)
                
                # 在弹窗中寻找“主图”勾选框
                # 通常是一个包含“主图”文本的 label
                main_img_chk = page.get_by_text("主图", exact=False)
                if await main_img_chk.is_visible():
                    print("[*] 找到“主图”勾选项，准备勾选...")
                    await main_img_chk.click()
                
                # 寻找“导出”或“生成地址”按钮
                export_btn = page.get_by_text("生成地址", exact=False).or_(page.get_by_text("导出图片", exact=False)).first
                if await export_btn.is_visible():
                    print("[*] 执行导出动作...")
                    await export_btn.click()
                    await asyncio.sleep(2)
                    
                    # 尝试从弹出的 textarea 中抓取内容
                    textarea = page.locator("textarea").first
                    if await textarea.is_visible():
                        val = await textarea.input_value()
                        print("\n[！！！成功捕获图片链接！！！]")
                        print(val[:200] + "...")
            else:
                print("[x] 未能找到对应的下载按钮。请检查页面是否发生了 UI 变动。")
                # 截图保存以便分析
                await page.screenshot(path="debug_1688_ui.png")
                print("[*] 已保存页面截图至 debug_1688_ui.png")

        except Exception as e:
            print(f"[!] 调试出错: {e}")

        print("\n[*] 调试完成。浏览器将在 10 秒后自动关闭，您可以趁现在手动查看元素。")
        await asyncio.sleep(10)
        await browser.close()

if __name__ == "__main__":
    asyncio.run(debug_download())
