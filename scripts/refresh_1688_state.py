import argparse
import asyncio
import json
import sys
from pathlib import Path
from playwright.async_api import async_playwright

async def refresh_state(state_file: str, user_data_dir: str | None = None, profile_directory: str | None = None):
    print("\n" + "="*50)
    print("【1688登录态刷新工具】")
    print("1. 脚本将启动一个可见的 Chrome 浏览器。")
    print("2. 请在弹出的浏览器中手动扫码登录 1688 (可通过淘宝/支付宝/密码登录)。")
    print("3. 登录成功后，请直接回到这里，或者等待检测通过。")
    print(f"4. 脚本将自动检测登录状态并保存到 {state_file}。")
    print("="*50 + "\n")

    async with async_playwright() as p:
        page = None
        close_target = None
        if user_data_dir:
            launch_args = ["--start-maximized"]
            if profile_directory:
                launch_args.append(f"--profile-directory={profile_directory}")
            context = await p.chromium.launch_persistent_context(
                user_data_dir,
                channel="chrome",
                headless=False,
                args=launch_args,
                user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
            )
            close_target = context
            await context.add_init_script("Object.defineProperty(navigator, 'webdriver', { get: () => undefined })")
            page = context.pages[0] if context.pages else await context.new_page()
        else:
            browser = await p.chromium.launch(
                channel="chrome",
                headless=False,
                args=["--start-maximized"]
            )
            context = await browser.new_context(
                user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
            )
            close_target = browser
            await context.add_init_script("Object.defineProperty(navigator, 'webdriver', { get: () => undefined })")
            page = await context.new_page()

        await page.goto("https://login.1688.com/member/signin.htm")

        print("[*] 正在等待登录成功标志...")
        
        try:
            while True:
                cookies = await context.cookies()
                has_login_cookie = any(c['name'] in ['cookie2', 'lgc', '_nk_', 'tracknick'] for c in cookies)
                cur_url = page.url
                is_logged_in = has_login_cookie and ("login" not in cur_url or "Done" in cur_url)
                
                if is_logged_in:
                    print("\n[√] 检测到登录成功！正在进行全方位业务域名安全预热，请不要关闭浏览器...")
                    
                    # 1. 访问 1688 首页预热
                    try:
                        print("[*] 正在预热 1688 首页...")
                        await page.goto("https://www.1688.com", wait_until="domcontentloaded", timeout=20000)
                        await asyncio.sleep(3)
                    except Exception as e:
                        print(f"[*] 首页预热提示: {e}")
                        
                    # 2. 访问 1688 详情页确认与滑块自愈
                    try:
                        print("[*] 正在预热详情页并确认登录态完整性...")
                        await page.goto("https://detail.1688.com/offer/904776936832.html", wait_until="domcontentloaded", timeout=20000)
                        await asyncio.sleep(3)
                        
                        if "login.taobao.com" in page.url or "_____tmd_____/punish" in page.url:
                            print("[!] 详情页提示安全验证，请在浏览器中手动完成滑块验证...")
                            for _ in range(30):
                                await asyncio.sleep(2)
                                if "login.taobao.com" not in page.url and "_____tmd_____/punish" not in page.url:
                                    print("[√] 详情页验证通过！")
                                    await asyncio.sleep(2)
                                    break
                            else:
                                print("[!] 详情页验证超时，将直接进入下一步。")
                    except Exception as e:
                        print(f"[*] 详情页预热提示: {e}")
                        
                    # 3. 访问 1688 以图搜源首页与滑块自愈
                    try:
                        print("[*] 正在预热以图搜源域名并激活安全会话...")
                        search_url = "https://s.1688.com/youyuan/index.htm?tab=imageSearch&imageAddress=https%3A%2F%2Fcbu01.alicdn.com%2Fimg%2Fibank%2FO1CN016f4Xpe1yY67H2b8d5_%21%212201402280208-0-cib.jpg"
                        await page.goto(search_url, wait_until="domcontentloaded", timeout=20000)
                        await asyncio.sleep(4)
                        
                        if "_____tmd_____/punish" in page.url:
                            print("[!] 以图搜结果页提示安全验证，请在浏览器中手动完成滑块验证...")
                            for _ in range(30):
                                await asyncio.sleep(2)
                                if "_____tmd_____/punish" not in page.url:
                                    print("[√] 以图搜结果页验证通过！")
                                    await asyncio.sleep(2)
                                    break
                            else:
                                print("[!] 以图搜结果页验证超时。")
                    except Exception as e:
                        print(f"[*] 以图搜域名预热提示: {e}")
                        
                    print("\n[*] 正在导出全套完整的状态数据...")
                    state = await context.storage_state()
                    
                    full_state = {
                        "cookies": state["cookies"],
                        "origins": state["origins"]
                    }
                    
                    Path(state_file).parent.mkdir(parents=True, exist_ok=True)
                    Path(state_file).write_text(json.dumps(full_state, indent=2, ensure_ascii=False))
                    print(f"[*] 状态已成功保存至: {state_file}")
                    break
                
                await asyncio.sleep(2)
                if page.is_closed():
                    print("[!] 浏览器已关闭，操作取消。")
                    break
        except Exception as e:
            print(f"[!] 导出过程中出错: {e}")
        finally:
            await close_target.close()

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Refresh ali1688 login state and export storage state JSON.")
    parser.add_argument("--state-file", default="state/source_channels/ali1688/ali1688-account-1/storage_state.json")
    parser.add_argument("--user-data-dir")
    parser.add_argument("--profile-directory")
    args = parser.parse_args()
    asyncio.run(refresh_state(args.state_file, args.user_data_dir, args.profile_directory))
