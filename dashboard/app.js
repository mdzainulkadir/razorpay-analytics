document.addEventListener("DOMContentLoaded", async () => {
    const themeBtn = document.getElementById("themeToggle");
    if (themeBtn) {
        themeBtn.addEventListener("click", () => {
            const current = document.documentElement.getAttribute("data-theme");
            const next = current === "dark" ? "light" : "dark";
            document.documentElement.setAttribute("data-theme", next);
            themeBtn.textContent = next === "dark" ? "☀️" : "🌙";
            updateDashboard();
        });
    }

    await window.PayPulseData.load();
    const initialData = window.PayPulseData.aggregate({ period: 'all', category: 'all', method: 'all' });

    const catSelect = document.getElementById("categoryFilter");
    if (catSelect) {
        catSelect.innerHTML = '<option value="all">All Categories</option>';
        try {
            const catRes = await fetch("data/category_perf.json");
            const cats = await catRes.json();
            cats.forEach(c => {
                if (c && c.category) {
                    const humCat = window.PayPulseData.humanize(c.category);
                    catSelect.innerHTML += `<option value="${humCat}">${humCat}</option>`;
                }
            });
        } catch (e) {
            const cats = initialData.categoryPerf || [];
            cats.forEach(c => {
                if (c && c.category) {
                    catSelect.innerHTML += `<option value="${c.category}">${c.category}</option>`;
                }
            });
        }
    }

    const methodSelect = document.getElementById("methodFilter");
    if (methodSelect) {
        methodSelect.innerHTML = '<option value="all">All Methods</option>';
        const mixes = initialData.paymentMix || [];
        mixes.forEach(m => {
            if (m && m.payment_method) {
                methodSelect.innerHTML += `<option value="${m.payment_method}">${m.payment_method}</option>`;
            }
        });
    }

    ["periodFilter", "categoryFilter", "methodFilter"].forEach(id => {
        const el = document.getElementById(id);
        if (el) el.addEventListener("change", updateDashboard);
    });

    if (initialData.meta) {
        document.getElementById("footerMeta").textContent = `${initialData.meta.data_type === 'synthetic' ? 'Demo built on synthetic data' : 'Production'} • Generated ${initialData.meta.generated_at}`;
    }

    updateDashboard();
});

function getBaseLayout() {
    const isDark = document.documentElement.getAttribute("data-theme") === "dark";
    return {
        paper_bgcolor: "rgba(0,0,0,0)",
        plot_bgcolor: "rgba(0,0,0,0)",
        font: { color: isDark ? "#f8fafc" : "#0c2a5c", family: "Inter", size: 12 },
        xaxis: { gridcolor: isDark ? "#263147" : "#e2e8f0", zerolinecolor: isDark ? "#263147" : "#e2e8f0", type: "category" },
        yaxis: { gridcolor: isDark ? "#263147" : "#e2e8f0", zerolinecolor: isDark ? "#263147" : "#e2e8f0", type: "linear" },
        margin: { t: 20, r: 20, b: 40, l: 60 }
    };
}

function formatINR(val) {
    if (!val && val !== 0) return "₹0";
    if (val >= 10000000) return "₹" + (val / 10000000).toFixed(2) + " Cr";
    if (val >= 100000) return "₹" + (val / 100000).toFixed(2) + " L";
    return "₹" + val.toLocaleString('en-IN');
}

function renderDelta(changePct, isLowerBetter = false) {
    if (changePct === null || changePct === undefined || isNaN(changePct)) {
        return `<span class="kpi-change neutral" title="All Time baseline (-)">-</span>`;
    }
    const val = Number(changePct);
    if (val === 0) {
        return `<span class="kpi-change neutral" title="No change vs prior period">0.0%</span>`;
    }
    const isPositive = val > 0;
    // Lower is better (e.g., refund rate): positive change is bad (red), negative change is good (green)
    // Regular: positive change is good (green), negative change is bad (red)
    let isGood = isLowerBetter ? !isPositive : isPositive;
    let cssClass = isGood ? "positive" : "negative";
    let sign = isPositive ? "+" : "";
    return `<span class="kpi-change ${cssClass}" title="Compared to prior equal-length period">${sign}${val.toFixed(1)}%</span>`;
}

function updateDashboard() {
    const period = document.getElementById("periodFilter")?.value || "all";
    const category = document.getElementById("categoryFilter")?.value || "all";
    const method = document.getElementById("methodFilter")?.value || "all";

    const data = window.PayPulseData.aggregate({ period, category, method });

    // Toggle daily trend note
    const noteEl = document.getElementById("dailyTrendNote");
    if (noteEl) {
        noteEl.style.display = data.isMonthlyView ? "block" : "none";
    }

    // 1. KPIs with proper deltas
    if (data.kpis) {
        const kpiGrid = document.getElementById("kpiGrid");
        if (kpiGrid) {
            kpiGrid.innerHTML = `
                <div class="kpi-card">
                    <div class="kpi-title">Gross Merchandise Value (GMV)</div>
                    <div class="kpi-value">${formatINR(data.kpis.gmv.current)}</div>
                    ${renderDelta(data.kpis.gmv.change_pct, false)}
                </div>
                <div class="kpi-card">
                    <div class="kpi-title">Success Rate</div>
                    <div class="kpi-value">${Number(data.kpis.success_rate.current).toFixed(2)}%</div>
                    ${renderDelta(data.kpis.success_rate.change_pct, false)}
                </div>
                <div class="kpi-card">
                    <div class="kpi-title">Net Revenue (Fees)</div>
                    <div class="kpi-value">${formatINR(data.kpis.net_revenue.current)}</div>
                    ${renderDelta(data.kpis.net_revenue.change_pct, false)}
                </div>
                <div class="kpi-card">
                    <div class="kpi-title">Refund Rate</div>
                    <div class="kpi-value">${Number(data.kpis.refund_rate.current).toFixed(2)}%</div>
                    ${renderDelta(data.kpis.refund_rate.change_pct, true)}
                </div>
                <div class="kpi-card">
                    <div class="kpi-title">Avg Ticket Size</div>
                    <div class="kpi-value">${formatINR(data.kpis.avg_ticket.current)}</div>
                    ${renderDelta(data.kpis.avg_ticket.change_pct, false)}
                </div>
                <div class="kpi-card">
                    <div class="kpi-title">Active Merchants</div>
                    <div class="kpi-value">${data.kpis.active_merchants.current.toLocaleString()}</div>
                    ${renderDelta(data.kpis.active_merchants.change_pct, false)}
                </div>
            `;
        }
    }

    // 2. Insights Strip
    if (data.insights && data.insights.length > 0) {
        const insightEl = document.getElementById("insightText");
        if (insightEl) {
            insightEl.textContent = data.insights[0].text;
        }
    }

    const layoutConfig = {
        responsive: true,
        displayModeBar: false,
        displaylogo: false
    };

    // 3. Daily / Native Trend Chart
    const daily = data.dailyTrend || [];
    const dailyLayout = JSON.parse(JSON.stringify(getBaseLayout()));
    dailyLayout.xaxis.type = data.isMonthlyView ? "category" : "date";
    Plotly.newPlot("dailyChart", [
        {
            x: daily.map(d => d.date),
            y: daily.map(d => Number(d.gmv)),
            type: "scatter",
            mode: "lines+markers",
            name: "GMV",
            line: { color: "#3395FF", width: 2 }
        }
    ], dailyLayout, layoutConfig);

    // 4. Monthly GMV & Revenue
    const monthly = data.monthly || [];
    const monthlyLayout = JSON.parse(JSON.stringify(getBaseLayout()));
    monthlyLayout.xaxis.type = "category";
    monthlyLayout.yaxis2 = { overlaying: "y", side: "right", showgrid: false };
    monthlyLayout.margin.r = 40;
    Plotly.newPlot("monthlyChart", [
        {
            x: monthly.map(m => m.month),
            y: monthly.map(m => Number(m.gmv)),
            type: "bar",
            name: "GMV",
            marker: { color: "#3395FF" }
        },
        {
            x: monthly.map(m => m.month),
            y: monthly.map(m => Number(m.revenue)),
            type: "scatter",
            mode: "lines+markers",
            name: "Net Revenue",
            yaxis: "y2",
            line: { color: "#10b981", width: 3 }
        }
    ], monthlyLayout, layoutConfig);

    // 5. Payment Method Mix
    const mix = data.paymentMix || [];
    const mixLayout = JSON.parse(JSON.stringify(getBaseLayout()));
    mixLayout.xaxis.visible = false;
    mixLayout.yaxis.visible = false;
    Plotly.newPlot("paymentMixChart", [{
        values: mix.map(m => Number(m.txn_count)),
        labels: mix.map(m => m.payment_method),
        type: "pie",
        hole: 0.55,
        marker: { colors: ["#3395FF", "#0c2a5c", "#60a5fa", "#10b981", "#f59e0b"] }
    }], mixLayout, { ...layoutConfig, showlegend: true });

    // 6. Success Rate by Method
    const sortedMix = [...mix].sort((a, b) => a.success_rate - b.success_rate);
    const methodLayout = JSON.parse(JSON.stringify(getBaseLayout()));
    methodLayout.xaxis.type = "linear";
    methodLayout.yaxis.type = "category";
    methodLayout.margin.l = 110;
    Plotly.newPlot("methodSuccessChart", [{
        x: sortedMix.map(m => Number(m.success_rate)),
        y: sortedMix.map(m => m.payment_method),
        type: "bar",
        orientation: "h",
        marker: { color: "#10b981" }
    }], methodLayout, layoutConfig);

    // 7. Top Failure Reasons
    const fails = [...(data.failureReasons || [])].sort((a, b) => a.count - b.count);
    const failLayout = JSON.parse(JSON.stringify(getBaseLayout()));
    failLayout.xaxis.type = "linear";
    failLayout.yaxis.type = "category";
    failLayout.margin.l = 140;
    Plotly.newPlot("failureReasonsChart", [{
        x: fails.map(f => Number(f.count)),
        y: fails.map(f => f.failure_reason),
        type: "bar",
        orientation: "h",
        marker: { color: "#ef4444" }
    }], failLayout, layoutConfig);

    // 8. Bank Success Rate
    const banks = [...(data.bankSuccess || [])].sort((a, b) => a.success_rate - b.success_rate).slice(0, 15);
    const bankLayout = JSON.parse(JSON.stringify(getBaseLayout()));
    bankLayout.xaxis.type = "linear";
    bankLayout.yaxis.type = "category";
    bankLayout.margin.l = 110;
    Plotly.newPlot("bankSuccessChart", [{
        x: banks.map(b => Number(b.success_rate)),
        y: banks.map(b => b.issuing_bank),
        type: "bar",
        orientation: "h",
        marker: { color: "#3395FF" }
    }], bankLayout, layoutConfig);

    // 9. Hourly Heatmap (missing cells are null, not 0)
    const heatmap = data.hourlyHeatmap || [];
    const days = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"];
    const hours = Array.from({ length: 24 }, (_, i) => `${String(i).padStart(2, '0')}:00`);
    const z = days.map(day => Array.from({ length: 24 }, (_, h) => {
        const found = heatmap.find(x => x.day_of_week === day && Number(x.hour) === h);
        return found ? found.failure_rate : null;
    }));
    const heatLayout = JSON.parse(JSON.stringify(getBaseLayout()));
    heatLayout.xaxis.type = "category";
    heatLayout.yaxis.type = "category";
    heatLayout.margin.l = 90;
    Plotly.newPlot("heatmapChart", [{
        z: z,
        x: hours,
        y: days,
        type: "heatmap",
        colorscale: [[0, "#f1f5f9"], [1, "#ef4444"]]
    }], heatLayout, layoutConfig);

    // 10. Category Performance
    const cats = data.categoryPerf || [];
    const catLayout = JSON.parse(JSON.stringify(getBaseLayout()));
    catLayout.xaxis.type = "category";
    catLayout.yaxis.type = "linear";
    catLayout.margin.b = 80;
    Plotly.newPlot("categoryPerfChart", [{
        x: cats.map(c => c.category),
        y: cats.map(c => Number(c.gmv)),
        type: "bar",
        marker: { color: "#3395FF" }
    }], catLayout, layoutConfig);

    // 11. Top Merchants Concentration
    const merchants = data.topMerchants || [];
    const merchLayout = JSON.parse(JSON.stringify(getBaseLayout()));
    merchLayout.xaxis.type = "category";
    merchLayout.yaxis.type = "linear";
    Plotly.newPlot("topMerchantsChart", [{
        x: merchants.map(m => m.merchant_rank),
        y: merchants.map(m => Number(m.gmv_share_pct)),
        type: "scatter",
        mode: "lines+markers",
        line: { color: "#3395FF", width: 3 }
    }], merchLayout, layoutConfig);

    // 12. Latency Percentiles
    const lat = data.latency || [];
    const latLayout = JSON.parse(JSON.stringify(getBaseLayout()));
    latLayout.xaxis.type = "category";
    latLayout.yaxis.type = "linear";
    Plotly.newPlot("latencyChart", [
        { x: lat.map(l => l.month), y: lat.map(l => Number(l.p50)), type: "scatter", mode: "lines", name: "p50", line: { color: "#10b981", width: 2 } },
        { x: lat.map(l => l.month), y: lat.map(l => Number(l.p90)), type: "scatter", mode: "lines", name: "p90", line: { color: "#f59e0b", width: 2 } },
        { x: lat.map(l => l.month), y: lat.map(l => Number(l.p99)), type: "scatter", mode: "lines", name: "p99", line: { color: "#ef4444", width: 2 } }
    ], latLayout, layoutConfig);

    // 13. Incidents
    const incs = data.incidents || [];
    const container = document.getElementById("incidentContainer");
    if (container) {
        if (incs.length === 0) {
            container.innerHTML = '<p class="empty-state">No active incidents detected in the selected period.</p>';
        } else {
            container.innerHTML = incs.map(i => `
                <div style="border-left: 4px solid #ef4444; background: rgba(239,68,68,0.05); padding: 1rem; margin-bottom: 0.75rem; border-radius: 6px;">
                    <div style="font-weight: 600; color: #ef4444; margin-bottom: 0.25rem;">🚨 ${i.start_time} — ${i.end_time}</div>
                    <div style="font-size: 0.875rem; color: var(--text-primary);">Peak Failure Rate: <strong>${i.peak_failure_rate_pct}%</strong> • Affected Transactions: <strong>${i.affected_txns.toLocaleString()}</strong> • Top Failure Reason: <strong>${i.top_failure_reason}</strong></div>
                </div>
            `).join("");
        }
    }
}
