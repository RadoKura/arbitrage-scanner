from playwright.sync_api import sync_playwright

from scrapers._common_1x2 import CHROMIUM_LAUNCH_ARGS

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True, args=CHROMIUM_LAUNCH_ARGS)
    page = browser.new_page()
    try:
        page.goto("http://1.1.1.1", timeout=10000)
        print("IP работи!")
    except Exception as e:
        print(f"IP грешка: {e}")
    try:
        page.goto("https://www.efbet.com", timeout=10000)
        print("efbet работи!")
    except Exception as e:
        print(f"efbet грешка: {e}")
    browser.close()
