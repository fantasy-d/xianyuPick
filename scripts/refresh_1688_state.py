import argparse
import asyncio
import json
import sys
import time
from datetime import datetime
from pathlib import Path
from playwright.async_api import async_playwright

try:
    sys.stdout.reconfigure(line_buffering=True)
    sys.stderr.reconfigure(line_buffering=True)
except Exception:
    pass


def build_session_report_path(state_file: str) -> Path:
    return Path(state_file).with_name("session_report.json")


def looks_like_logged_in(cookies: list[dict], current_url: str) -> bool:
    cookie_map = {str(item.get("name") or ""): str(item.get("value") or "") for item in cookies or []}
    has_session_cookie = any(cookie_map.get(name) for name in ["cookie2", "tracknick", "_nk_", "lgc", "__cn_logon_id__"])
    has_logon_flag = cookie_map.get("__cn_logon__") == "true"
    normalized_url = (current_url or "").lower()
    left_login_page = "login" not in normalized_url and "signin" not in normalized_url
    return has_session_cookie and has_logon_flag and left_login_page


def is_login_related_url(url: str) -> bool:
    normalized = (url or "").lower()
    return any(
        keyword in normalized
        for keyword in (
            "login.1688.com",
            "member/signin",
            "passport.alibaba.com",
            "login.taobao.com",
            "signin.htm",
            "passport.alibaba",
        )
    )


def is_verification_related_url(url: str) -> bool:
    normalized = (url or "").lower()
    return any(
        keyword in normalized
        for keyword in (
            "_____tmd_____/punish",
            "captcha",
            "verify",
            "nocaptcha",
        )
    )


async def clear_ali1688_login_site_state(context, page) -> None:
    origins = [
        "https://www.1688.com",
        "https://login.1688.com",
        "https://member.1688.com",
        "https://login.taobao.com",
    ]
    try:
        cdp = await context.new_cdp_session(page)
    except Exception as exc:
        print(f"[*] 无法建立 CDP 清理通道，跳过站点存储清理: {exc}")
        return

    try:
        await cdp.send("Network.enable")
    except Exception:
        pass

    try:
        await cdp.send("Network.clearBrowserCookies")
    except Exception:
        pass

    try:
        await cdp.send("Network.clearBrowserCache")
    except Exception:
        pass

    for origin in origins:
        try:
            await cdp.send("Storage.clearDataForOrigin", {"origin": origin, "storageTypes": "all"})
        except Exception as exc:
            print(f"[*] 清理站点数据提示 {origin}: {exc}")


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
            existing_pages = list(context.pages)
            page = await context.new_page()
            for stale_page in existing_pages:
                try:
                    await stale_page.close()
                except Exception:
                    pass
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

        print("[*] 正在清理当前浏览器会话并打开 1688 登录页...")
        await context.clear_cookies()
        await clear_ali1688_login_site_state(context, page)
        await page.bring_to_front()
        try:
            await page.goto(
                "https://login.1688.com/member/signin.htm?done=https%3A%2F%2Fwww.1688.com%2F",
                wait_until="domcontentloaded",
                timeout=30000,
            )
        except Exception as exc:
            print(f"[!] 无法打开 1688 登录页，请检查浏览器网络环境或代理设置: {exc}")
            return False

        print("[*] 正在等待登录成功标志...")
        login_page_seen = False
        login_page_seen_at = 0.0
        left_login_page_after_prompt = False
        inherited_session_notice_shown = False
        login_prompt_notice_shown = False
        
        try:
            while True:
                if page.is_closed():
                    print("[!] 浏览器已关闭，登录流程已取消。")
                    return False

                cookies = await context.cookies()
                cur_url = page.url
                now = time.monotonic()
                is_login_page = is_login_related_url(cur_url)
                is_verification_page = is_verification_related_url(cur_url)
                is_logged_in = looks_like_logged_in(cookies, cur_url)

                if is_login_page:
                    if not login_page_seen:
                        login_page_seen = True
                        login_page_seen_at = now
                        print(f"[*] 已进入 1688 登录页: {cur_url}")
                    if not login_prompt_notice_shown:
                        print("[*] 请在浏览器中完成扫码/安全登录，只有离开登录页后系统才会判定成功。")
                        login_prompt_notice_shown = True
                elif login_page_seen and not is_verification_page:
                    left_login_page_after_prompt = True

                has_real_relogin_signal = (
                    login_page_seen
                    and left_login_page_after_prompt
                    and login_page_seen_at > 0
                    and (now - login_page_seen_at) >= 3
                )
                
                if is_logged_in and has_real_relogin_signal:
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
                    account_name_payload = {
                        "account_name": "",
                        "source": "",
                        "confidence": 0.0,
                    }
                    try:
                        from xianyu_tools.ali1688_session import extract_ali1688_account_name

                        for candidate_url in (
                            page.url,
                            "https://www.1688.com/",
                            "https://member.1688.com/member/myalibaba.htm",
                        ):
                            if candidate_url and page.url != candidate_url:
                                await page.goto(candidate_url, wait_until="domcontentloaded", timeout=20000)
                                await asyncio.sleep(2)
                            candidate = await extract_ali1688_account_name(page, context)
                            if candidate.get("account_name"):
                                account_name_payload = candidate
                                break
                    except Exception as e:
                        print(f"[*] 用户名抓取提示: {e}")
                    
                    full_state = {
                        "cookies": state["cookies"],
                        "origins": state["origins"]
                    }
                    
                    Path(state_file).parent.mkdir(parents=True, exist_ok=True)
                    Path(state_file).write_text(json.dumps(full_state, indent=2, ensure_ascii=False))
                    print(f"[*] 状态已成功保存至: {state_file}")

                    session_report_path = build_session_report_path(state_file)
                    session_report_payload = {
                        "account_name": account_name_payload.get("account_name") or "",
                        "captured_at": datetime.now().isoformat(),
                        "source": account_name_payload.get("source") or "",
                        "confidence": account_name_payload.get("confidence") or 0.0,
                        "status_text": "登录正常",
                        "is_usable": True,
                        "state_file": str(Path(state_file).resolve()),
                        "url": page.url,
                        "title": await page.title(),
                    }
                    session_report_path.write_text(
                        json.dumps(session_report_payload, indent=2, ensure_ascii=False),
                        encoding="utf-8",
                    )
                    if session_report_payload["account_name"]:
                        print(f"[*] 已抓取真实账号名: {session_report_payload['account_name']}")
                    else:
                        print("[*] 本次未抓取到真实账号名，已仅保存登录态。")
                    print(f"[*] 账号报告已保存至: {session_report_path}")
                    return True

                if is_logged_in and not has_real_relogin_signal and not inherited_session_notice_shown:
                    print("[*] 检测到浏览器内仍存在可用登录态，但本次尚未完成新的登录确认，继续等待用户操作...")
                    inherited_session_notice_shown = True
                
                await asyncio.sleep(2)
        except Exception as e:
            print(f"[!] 导出过程中出错: {e}")
            return False
        finally:
            await close_target.close()

    return False

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Refresh ali1688 login state and export storage state JSON.")
    parser.add_argument("--state-file", default="state/source_channels/ali1688/ali1688-account-1/storage_state.json")
    parser.add_argument("--user-data-dir")
    parser.add_argument("--profile-directory")
    args = parser.parse_args()
    success = asyncio.run(refresh_state(args.state_file, args.user_data_dir, args.profile_directory))
    sys.exit(0 if success else 1)
