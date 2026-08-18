#!/usr/bin/env python3
import os
from pathlib import Path
from playwright.sync_api import sync_playwright

output = Path(os.getenv("DASHBOARD_SCREENSHOT", "/tmp/changeshield-dashboard.png"))
with sync_playwright() as playwright:
    browser = playwright.chromium.launch(headless=True)
    page = browser.new_page(viewport={"width": 1440, "height": 1100}, device_scale_factor=1)
    page.goto(os.getenv("DASHBOARD_URL", "http://127.0.0.1:8765/login/"))
    page.get_by_label("Username").fill(os.getenv("DEMO_ADMIN_USERNAME", "operator"))
    page.get_by_label("Password").fill(os.environ["DEMO_ADMIN_PASSWORD"])
    page.get_by_role("button", name="Sign in").click()
    page.wait_for_url("**/")
    page.screenshot(path=str(output), full_page=True)
    browser.close()
print(output)
