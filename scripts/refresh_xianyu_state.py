import asyncio
import json
import sys
from pathlib import Path
from playwright.async_api import async_playwright

async def refresh_state():
    state_file = "xianyu_state.json"
    print("\n" + "="*50)
    print("【闲鱼登录态刷新工具】")
    print("1. 脚本将启动一个可见的 Chrome 浏览器。")
    print("2. 请在弹出的浏览器中手动扫码登录闲鱼。")
    print("3. 登录成功后，请在浏览器中随便点击一个页面，或者直接回到这里。")
    print(f"4. 脚本将自动检测登录状态并保存到 {state_file}。")
    print("="*50 + "\n")

    async with async_playwright() as p:
        # 启动可见浏览器
        browser = await p.chromium.launch(
            headless=False, 
            channel="chrome", # 优先使用本地安装的 Chrome
            args=["--start-maximized"]
        )
        
        # 创建上下文（抹除机器人特征，防止扫码后依然被拦截）
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
        )
        await context.add_init_script("Object.defineProperty(navigator, 'webdriver', { get: () => undefined })")
        
        page = await context.new_page()
        await page.goto("https://www.goofish.com/")

        print("[*] 正在等待登录成功标志...")
        
        # 循环检测登录状态 (通过是否存在昵称或特定 API 响应)
        try:
            while True:
                # 检查页面是否包含“退出”或者昵称等登录后才有的元素
                cookies = await context.cookies()
                # 检查关键 Cookie: _m_h5_tk 或 lgc (登录中心标记)
                has_login_cookie = any(c['name'] in ['lgc', 'tracknick', '_nk_', '_m_h5_tk'] for c in cookies)
                
                if has_login_cookie:
                    print("\n[√] 检测到登录成功！正在导出状态数据...")
                    # 获取完整状态 (含 cookies 和 local storage)
                    state = await context.storage_state()
                    
                    # 额外补全一些快照信息以适配您之前的格式
                    full_state = {
                        "capturedAt": "2026-04-12T19:00:00Z",
                        "cookies": state["cookies"],
                        "origins": state["origins"]
                    }
                    
                    Path(state_file).write_text(json.dumps(full_state, indent=2, ensure_ascii=False))
                    print(f"[*] 状态已成功保存至: {state_file}")
                    print("[*] 您现在可以关闭浏览器并开始任务了。")
                    break
                
                await asyncio.sleep(2)
                if page.is_closed():
                    print("[!] 浏览器已关闭，操作取消。")
                    break
        except Exception as e:
            print(f"[!] 导出过程中出错: {e}")
        finally:
            await browser.close()

if __name__ == "__main__":
    asyncio.run(refresh_state())
