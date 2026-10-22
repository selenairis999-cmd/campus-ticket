# -*- coding: utf-8 -*-
"""用 Playwright 登录并截取指定页面（用于文档配图截图）。

用法：
  python tools/screenshot_page.py <输出png> [--route /admin/risk] [--width 1440] [--full]

默认截取管理员风控监控页面。宽视口 + deviceScaleFactor=2 保证插图清晰。
"""
import sys
import argparse
from playwright.sync_api import sync_playwright

BASE = "http://localhost:8080"
ACCOUNTS = {
    "admin": ("admin", "123456"),
    "student": ("student01", "123456"),
}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("out")
    ap.add_argument("--route", default="/admin/risk")
    ap.add_argument("--role", default="admin")
    ap.add_argument("--width", type=int, default=1600)
    ap.add_argument("--height", type=int, default=900)
    ap.add_argument("--full", action="store_true", help="整页截图")
    ap.add_argument("--wait", type=float, default=2.5, help="渲染等待秒数")
    args = ap.parse_args()

    user, pwd = ACCOUNTS[args.role]

    with sync_playwright() as p:
        browser = p.chromium.launch(args=["--no-sandbox"])
        ctx = browser.new_context(
            viewport={"width": args.width, "height": args.height},
            device_scale_factor=2,
        )
        page = ctx.new_page()

        # 登录页填表（按钮文案是「登 录」，中间有空格，用 contains 匹配）
        page.goto(BASE + "/login", wait_until="networkidle")
        page.wait_for_timeout(1500)
        page.fill('input[placeholder="用户名"]', user)
        page.fill('input[placeholder="密码"]', pwd)
        page.click('button:has-text("登")')
        page.wait_for_timeout(2500)
        print("登录后 URL:", page.url)

        # 跳到目标路由
        page.goto(BASE + args.route, wait_until="networkidle")
        page.wait_for_timeout(int(args.wait * 1000))
        print("目标 URL:", page.url)

        page.screenshot(path=args.out, full_page=args.full)
        print("已保存:", args.out)
        browser.close()


if __name__ == "__main__":
    main()
