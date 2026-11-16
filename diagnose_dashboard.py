"""
Diagnose dashboard issues via Playwright Chromium.
Capture console errors, network requests, and test chart rendering.
"""

from playwright.sync_api import sync_playwright

def main():
    console_messages = []
    network_requests = []

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(viewport={"width": 1440, "height": 900})
        page = context.new_page()

        page.on("console", lambda msg: console_messages.append(f"[{msg.type}] {msg.text}"))
        page.on("request", lambda req: network_requests.append(req.url))

        try:
            page.goto("http://localhost:8000", timeout=10000)
            page.wait_for_timeout(3000)
        except Exception as e:
            print(f"Error loading page: {e}")

        charts_to_check = [
            "dailyTrendChart", "monthlyChart", "paymentMixChart", "methodSuccessChart",
            "hourlyHeatmapChart", "failureReasonsChart", "bankSuccessChart",
            "latencyChart", "categoryPerfChart", "topMerchantsChart"
        ]

        chart_status = {}
        for chart_id in charts_to_check:
            script = f"() => {{ const el = document.getElementById('{chart_id}'); if (!el) return 'NOT_FOUND'; return el.innerHTML.trim().length > 0 ? 'RENDERED' : 'EMPTY'; }}"
            has_content = page.evaluate(script)
            chart_status[chart_id] = has_content

        browser.close()

    print("=== CONSOLE MESSAGES ===")
    for msg in console_messages:
        print(msg)

    print("\n=== NETWORK REQUESTS ===")
    for req in network_requests:
        print(req)

    print("\n=== CHART RENDER STATUS ===")
    for k, v in chart_status.items():
        print(f"{k}: {v}")

if __name__ == "__main__":
    main()
