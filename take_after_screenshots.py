"""
Take 'after' screenshots using Playwright Firefox.
"""

from pathlib import Path
from playwright.sync_api import sync_playwright

def main():
    screenshots_dir = Path("screenshots/after")
    screenshots_dir.mkdir(parents=True, exist_ok=True)

    with sync_playwright() as p:
        browser = p.firefox.launch(headless=True)

        # 1. Desktop 1440x900 - Light
        context = browser.new_context(viewport={"width": 1440, "height": 900}, color_scheme="light")
        page = context.new_page()
        page.goto("http://localhost:8000")
        page.wait_for_timeout(2500)
        page.screenshot(path=str(screenshots_dir / "desktop_light.png"), full_page=True)
        context.close()

        # 2. Desktop 1440x900 - Dark
        context = browser.new_context(viewport={"width": 1440, "height": 900}, color_scheme="dark")
        page = context.new_page()
        page.goto("http://localhost:8000")
        page.evaluate("document.documentElement.setAttribute('data-theme', 'dark')")
        page.wait_for_timeout(2500)
        page.screenshot(path=str(screenshots_dir / "desktop_dark.png"), full_page=True)
        context.close()

        # 3. Mobile 375x812 - Light
        context = browser.new_context(viewport={"width": 375, "height": 812}, color_scheme="light")
        page = context.new_page()
        page.goto("http://localhost:8000")
        page.wait_for_timeout(2500)
        page.screenshot(path=str(screenshots_dir / "mobile_light.png"), full_page=True)
        context.close()

        # 4. Mobile 375x812 - Dark
        context = browser.new_context(viewport={"width": 375, "height": 812}, color_scheme="dark")
        page = context.new_page()
        page.goto("http://localhost:8000")
        page.evaluate("document.documentElement.setAttribute('data-theme', 'dark')")
        page.wait_for_timeout(2500)
        page.screenshot(path=str(screenshots_dir / "mobile_dark.png"), full_page=True)
        context.close()

        browser.close()
    print("After screenshots captured successfully with Firefox.")

if __name__ == "__main__":
    main()
