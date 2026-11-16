import sys
import time
from playwright.sync_api import sync_playwright

def run_verification():
    print("Starting comprehensive Playwright dashboard verification...")
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()

        console_errors = []
        page.on("console", lambda msg: console_errors.append(msg.text) if msg.type == "error" else None)
        page.on("pageerror", lambda err: console_errors.append(str(err)))

        url = "http://localhost:8000"
        page.goto(url, wait_until="networkidle", timeout=15000)
        time.sleep(3)

        print(f"Captured console errors: {len(console_errors)}")
        if console_errors:
            print("Errors:", console_errors)

        title = page.title()
        badge_locator = page.locator(".badge-synthetic")
        badge_text = badge_locator.inner_text() if badge_locator.count() > 0 else ""

        print(f"Page Title: {title}")
        print(f"Synthetic Badge: {badge_text}")

        failed_assertions = []

        body_text = page.locator("body").inner_text()
        if "PayPulse" not in title:
            failed_assertions.append("Title does not contain 'PayPulse'")
        if "Synthetic" not in badge_text:
            failed_assertions.append("Badge does not contain 'Synthetic'")
        if "Live" in body_text or "Production" in body_text:
            failed_assertions.append("Page contains forbidden words ('Live' or 'Production')")

        chart_ids = [
            "dailyChart", "monthlyChart", "paymentMixChart", "methodSuccessChart",
            "failureReasonsChart", "bankSuccessChart", "heatmapChart",
            "categoryPerfChart", "topMerchantsChart", "latencyChart"
        ]

        def test_state(period_val, cat_val, method_val):
            page.evaluate(f"""() => {{
                document.getElementById('periodFilter').value = '{period_val}';
                document.getElementById('periodFilter').dispatchEvent(new Event('change'));
                document.getElementById('categoryFilter').value = '{cat_val}';
                document.getElementById('categoryFilter').dispatchEvent(new Event('change'));
                document.getElementById('methodFilter').value = '{method_val}';
                document.getElementById('methodFilter').dispatchEvent(new Event('change'));
            }}""")
            time.sleep(1.5)

            gmv_kpi_text = page.evaluate("() => document.querySelector('.kpi-card .kpi-value')?.innerText || '₹0'")

            metrics = page.evaluate(f"""() => {{
                const chartIds = {chart_ids};
                let results = {{}};
                chartIds.forEach(cid => {{
                    const el = document.getElementById(cid);
                    if (!el || (!el._fullData && !el.data)) {{
                        results[cid] = {{ finiteNumCount: 0, hasEpoch: false, hasNaN: true, xType: 'missing', yType: 'missing', zValues: [] }};
                        return;
                    }}
                    const traces = el._fullData || el.data;
                    const layout = el._fullLayout || el.layout || {{}};
                    let finiteNumCount = 0;
                    let hasEpoch = false;
                    let hasNaN = false;
                    let zValues = [];
                    const xType = layout.xaxis && layout.xaxis.type ? layout.xaxis.type : 'category';
                    const yType = layout.yaxis && layout.yaxis.type ? layout.yaxis.type : 'linear';

                    traces.forEach(t => {{
                        const checkNumeric = (arr) => {{
                            if (!Array.isArray(arr)) return;
                            arr.forEach(val => {{
                                if (Array.isArray(val)) {{
                                    checkNumeric(val);
                                }} else if (typeof val === 'number' && !isNaN(val)) {{
                                    finiteNumCount++;
                                    zValues.push(val);
                                }} else if (val != null) {{
                                    const num = Number(val);
                                    if (!isNaN(num)) finiteNumCount++;
                                }}
                            }});
                        }};
                        checkNumeric(t.y);
                        checkNumeric(t.x);
                        checkNumeric(t.z);
                        checkNumeric(t.values);
                    }});
                    results[cid] = {{ finiteNumCount, hasEpoch, hasNaN, xType, yType, zValues }};
                }});
                return results;
            }}""")

            trend_sum = page.evaluate("""() => {
                const trend = window.PayPulseData.aggregate({
                    period: document.getElementById('periodFilter').value,
                    category: document.getElementById('categoryFilter').value,
                    method: document.getElementById('methodFilter').value
                }).dailyTrend;
                return trend.reduce((sum, d) => sum + d.gmv, 0);
            }""")

            return gmv_kpi_text, trend_sum, metrics

        # Get available options from dropdowns first
        time.sleep(1)
        categories = page.evaluate("() => Array.from(document.getElementById('categoryFilter').options).map(o => o.value).filter(v => v !== 'all')")
        methods = page.evaluate("() => Array.from(document.getElementById('methodFilter').options).map(o => o.value).filter(v => v !== 'all')")
        print("Available Categories:", categories)
        print("Available Methods:", methods)

        c1 = categories[0] if len(categories) > 0 else 'E-Commerce'
        c2 = categories[1] if len(categories) > 1 else 'Education'
        m1 = methods[0] if len(methods) > 0 else 'UPI'
        m2 = methods[1] if len(methods) > 1 else 'Card'

        scenarios = [
            ("all", "all", "all"),
            ("all", c1, m1),
            ("all", c2, m2),
            ("q1_nov_jan", c1, m2),
            ("q2_feb_apr", c2, m1)
        ]

        for idx, (p_val, c_val, m_val) in enumerate(scenarios):
            print(f"\n--- Testing Scenario {idx+1}: Period={p_val}, Category={c_val}, Method={m_val} ---")
            gmv_text, trend_sum, metrics = test_state(p_val, c_val, m_val)
            print(f"GMV KPI Text: {gmv_text} | Computed Trend Sum: {trend_sum:,.2f}")

            for cid, m in metrics.items():
                if m['finiteNumCount'] < 1:
                    failed_assertions.append(f"Chart {cid} in scenario {idx+1} has 0 finite numeric points")
                if m['hasEpoch']:
                    failed_assertions.append(f"Chart {cid} in scenario {idx+1} has 1970/epoch date")

            if metrics['dailyChart']['xType'] not in ['date', 'category']:
                failed_assertions.append(f"dailyChart xType is invalid: {metrics['dailyChart']['xType']}")
            if metrics['monthlyChart']['xType'] != 'category':
                failed_assertions.append(f"monthlyChart xType is not category: {metrics['monthlyChart']['xType']}")

            heatmap_z = metrics['heatmapChart']['zValues']
            if metrics['heatmapChart']['finiteNumCount'] == 0:
                failed_assertions.append(f"Heatmap in scenario {idx+1} has 0 finite numeric points")

            delta_pills = page.evaluate("() => Array.from(document.querySelectorAll('.kpi-change')).map(el => el.innerText)")
            for pill in delta_pills:
                if '+-' in pill or '-+' in pill:
                    failed_assertions.append(f"Delta pill has invalid sign format: '{pill}'")

        if len(console_errors) > 0:
            failed_assertions.append(f"Captured {len(console_errors)} console errors")

        browser.close()

        print("\n=== Verification Results ===")
        if len(failed_assertions) == 0:
            print("ALL CHECKS PASSED: PASS")
            sys.exit(0)
        else:
            print(f"FAILED CHECKS ({len(failed_assertions)}):")
            for err in failed_assertions:
                print(f" - {err}")
            print("RESULT: FAIL")
            sys.exit(1)

if __name__ == "__main__":
    run_verification()
