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

    // Populate category dropdown from cubes or default
    const catSelect = document.getElementById("categoryFilter");
    if (catSelect) {
        const aggregatedInitial = window.PayPulseData.aggregate({ period: 'all', category: 'all', method: 'all' });
        const cats = aggregatedInitial.categoryPerf || [];
        cats.forEach(c => {
            if (c && c.category) {
                catSelect.innerHTML += `<option value="${c.category}">${c.category}</option>`;
            }
        });
    }

    // Populate method dropdown
    const methodSelect = document.getElementById("methodFilter");
    if (methodSelect) {
        const aggregatedInitial = window.PayPulseData.aggregate({ period: 'all', category: 'all', method: 'all' });
        const mixes = aggregatedInitial.paymentMix || [];
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

    const initialData = window.PayPulseData.aggregate({ period: 'all', category: 'all', method: 'all' });
    if (initialData.meta) {
        document.getElementById("footerMeta").textContent = `${initialData.meta.data_type === 'synthetic' ? 'Demo built on synthetic data' : 'Production'} • Generated ${initialData.meta.generated_at}`;
    }

    updateDashboard();
});

function getColors() {
    const isDark = document.documentElement.getAttribute("data-theme") === "dark";
    return {
        paper_bgcolor: "rgba(0,0,0,0)",
        plot_bgcolor: "rgba(0,0,0,0)",
        font: { color: isDark ? "#f8fafc" : "#0c2a5c", family: "Inter", size: 12 },
        xaxis: { gridcolor: isDark ? "#263147" : "#e2e8f0", zerolinecolor: isDark ? "#263147" : "#e2e8f0" },
        yaxis: { gridcolor: isDark ? "#263147" : "#e2e8f0", zerolinecolor: isDark ? "#263147" : "#e2e8f0" }
    };
}

function formatINR(val) {
    if (!val && val !== 0) return "₹0";
    if (val >= 10000000) return "₹" + (val / 10000000).toFixed(2) + " Cr";
    if (val >= 100000) return "₹" + (val / 100000).toFixed(2) + " L";
    return "₹" + val.toLocaleString('en-IN');
}

function updateDashboard() {
    const period = document.getElementById("periodFilter")?.value || "all";
    const category = document.getElementById("categoryFilter")?.value || "all";
    const method = document.getElementById("methodFilter")?.value || "all";

    const data = window.PayPulseData.aggregate({ period, category, method });
    const colors = getColors();

    // 1. KPIs
    try {
        if (data.kpis) {
            const kpiGrid = document.getElementById("kpiGrid");
            if (kpiGrid) {
                kpiGrid.innerHTML = `
                    <div class="kpi-card">
                        <div class="kpi-title">Gross Merchandise Value (GMV)</div>
                        <div class="kpi-value">${formatINR(data.kpis.gmv.current)}</div>
                        <span class="kpi-change positive">+${data.kpis.gmv.change_pct}% vs prior</span>
                    </div>
                    <div class="kpi-card">
                        <div class="kpi-title">Success Rate</div>
                        <div class="kpi-value">${Number(data.kpis.success_rate.current).toFixed(2)}%</div>
                        <span class="kpi-change positive">+${data.kpis.success_rate.change_pct}% vs prior</span>
                    </div>
                    <div class="kpi-card">
                        <div class="kpi-title">Net Revenue (Fees)</div>
                        <div class="kpi-value">${formatINR(data.kpis.net_revenue.current)}</div>
                        <span class="kpi-change positive">+${data.kpis.net_revenue.change_pct}% vs prior</span>
                    </div>
                    <div class="kpi-card">
                        <div class="kpi-title">Refund Rate</div>
                        <div class="kpi-value">${Number(data.kpis.refund_rate.current).toFixed(2)}%</div>
                        <span class="kpi-change negative">${data.kpis.refund_rate.change_pct}% vs prior</span>
                    </div>
                    <div class="kpi-card">
                        <div class="kpi-title">Avg Ticket Size</div>
                        <div class="kpi-value">${formatINR(data.kpis.avg_ticket.current)}</div>
                        <span class="kpi-change positive">+${data.kpis.avg_ticket.change_pct}% vs prior</span>
                    </div>
                    <div class="kpi-card">
                        <div class="kpi-title">Active Merchants</div>
                        <div class="kpi-value">${data.kpis.active_merchants.current.toLocaleString()}</div>
                        <span class="kpi-change positive">+${data.kpis.active_merchants.change_pct}% vs prior</span>
                    </div>
                `;
            }
        }
    } catch (e) {
        console.error("KPI render error:", e);
    }

    // 2. Insights Strip
    try {
        if (data.insights && data.insights.length > 0) {
            const insightEl = document.getElementById("insightText");
            if (insightEl) {
                insightEl.textContent = data.insights[0].text;
            }
        }
    } catch (e) {
        console.error("Insight render error:", e);
    }

    const layoutConfig = {
        responsive: true,
        displayModeBar: false,
        displaylogo: false
    };

    // 3. Daily Trend
    try {
        const daily = data.dailyTrend || [];
        Plotly.newPlot("dailyChart", [
            {
                x: daily.map(d => d.date),
                y: daily.map(d => Number(d.txn_count)),
                type: "scatter",
                mode: "lines",
                name: "Attempts",
                line: { color: "#3395FF", width: 2 }
            }
        ], { ...colors, margin: { t: 20, r: 20, b: 40, l: 60 } }, layoutConfig);
    } catch (e) { console.error("Daily chart error:", e); }

    // 4. Monthly GMV & Revenue
    try {
        const monthly = data.monthly || [];
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
        ], {
            ...colors,
            margin: { t: 20, r: 40, b: 40, l: 60 },
            yaxis2: { overlaying: "y", side: "right", showgrid: false }
        }, layoutConfig);
    } catch (e) { console.error("Monthly chart error:", e); }

    // 5. Payment Method Mix
    try {
        const mix = data.paymentMix || [];
        Plotly.newPlot("paymentMixChart", [{
            values: mix.map(m => Number(m.txn_count)),
            labels: mix.map(m => m.payment_method),
            type: "pie",
            hole: 0.55,
            marker: { colors: ["#3395FF", "#0c2a5c", "#60a5fa", "#10b981", "#f59e0b"] }
        }], { ...colors, margin: { t: 20, r: 20, b: 20, l: 20 }, showlegend: true }, layoutConfig);
    } catch (e) { console.error("Payment mix chart error:", e); }

    // 6. Success Rate by Method
    try {
        const mix = [...(data.paymentMix || [])].sort((a, b) => a.success_rate - b.success_rate);
        Plotly.newPlot("methodSuccessChart", [{
            x: mix.map(m => Number(m.success_rate)),
            y: mix.map(m => m.payment_method),
            type: "bar",
            orientation: "h",
            marker: { color: "#10b981" }
        }], { ...colors, margin: { t: 20, r: 20, b: 40, l: 110 } }, layoutConfig);
    } catch (e) { console.error("Method success chart error:", e); }

    // 7. Top Failure Reasons
    try {
        const fails = [...(data.failureReasons || [])].sort((a, b) => a.count - b.count);
        Plotly.newPlot("failureReasonsChart", [{
            x: fails.map(f => Number(f.count)),
            y: fails.map(f => f.failure_reason),
            type: "bar",
            orientation: "h",
            marker: { color: "#ef4444" }
        }], { ...colors, margin: { t: 20, r: 20, b: 40, l: 140 } }, layoutConfig);
    } catch (e) { console.error("Failure reasons chart error:", e); }

    // 8. Bank Success Rate
    try {
        const banks = [...(data.bankSuccess || [])].sort((a, b) => a.success_rate - b.success_rate).slice(0, 15);
        Plotly.newPlot("bankSuccessChart", [{
            x: banks.map(b => Number(b.success_rate)),
            y: banks.map(b => b.issuing_bank),
            type: "bar",
            orientation: "h",
            marker: { color: "#3395FF" }
        }], { ...colors, margin: { t: 20, r: 20, b: 40, l: 110 } }, layoutConfig);
    } catch (e) { console.error("Bank success chart error:", e); }

    // 9. Hourly Heatmap
    try {
        const heatmap = data.hourlyHeatmap || [];
        const days = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"];
        const hours = Array.from({ length: 24 }, (_, i) => `${String(i).padStart(2, '0')}:00`);
        const z = days.map(day => Array.from({ length: 24 }, (_, h) => {
            const found = heatmap.find(x => x.day_of_week === day && Number(x.hour) === h);
            return found ? Number(found.failure_rate) : 0;
        }));
        Plotly.newPlot("heatmapChart", [{
            z: z,
            x: hours,
            y: days,
            type: "heatmap",
            colorscale: [[0, "#f1f5f9"], [1, "#ef4444"]]
        }], { ...colors, margin: { t: 20, r: 20, b: 40, l: 90 } }, layoutConfig);
    } catch (e) { console.error("Heatmap chart error:", e); }

    // 10. Category Performance
    try {
        const cats = data.categoryPerf || [];
        Plotly.newPlot("categoryPerfChart", [{
            x: cats.map(c => c.category),
            y: cats.map(c => Number(c.gmv)),
            type: "bar",
            marker: { color: "#3395FF" }
        }], { ...colors, margin: { t: 20, r: 20, b: 80, l: 60 } }, layoutConfig);
    } catch (e) { console.error("Category perf chart error:", e); }

    // 11. Top Merchants Concentration
    try {
        const merchants = data.topMerchants || [];
        Plotly.newPlot("topMerchantsChart", [{
            x: merchants.map(m => m.merchant_rank),
            y: merchants.map(m => Number(m.gmv_share_pct)),
            type: "scatter",
            mode: "lines+markers",
            line: { color: "#3395FF", width: 3 }
        }], { ...colors, margin: { t: 20, r: 20, b: 40, l: 60 } }, layoutConfig);
    } catch (e) { console.error("Merchants chart error:", e); }

    // 12. Latency Percentiles
    try {
        const lat = data.latency || [];
        Plotly.newPlot("latencyChart", [
            { x: lat.map(l => l.month), y: lat.map(l => Number(l.p50)), type: "scatter", mode: "lines", name: "p50", line: { color: "#10b981", width: 2 } },
            { x: lat.map(l => l.month), y: lat.map(l => Number(l.p90)), type: "scatter", mode: "lines", name: "p90", line: { color: "#f59e0b", width: 2 } },
            { x: lat.map(l => l.month), y: lat.map(l => Number(l.p99)), type: "scatter", mode: "lines", name: "p99", line: { color: "#ef4444", width: 2 } }
        ], { ...colors, margin: { t: 20, r: 20, b: 40, l: 60 } }, layoutConfig);
    } catch (e) { console.error("Latency chart error:", e); }

    // 13. Incidents
    try {
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
    } catch (e) { console.error("Incident render error:", e); }
}
