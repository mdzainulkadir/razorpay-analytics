/* ==========================================================================
   Razorpay Analytics Dashboard — Application Logic (app.js)
   Fetches aggregates from dashboard/data/*.json and renders Plotly charts.
   ========================================================================== */

let rawData = {};
let currentTheme = localStorage.getItem("theme") || "light";

// Apply initial theme
document.documentElement.setAttribute("data-theme", currentTheme);
document.getElementById("themeToggle").textContent = currentTheme === "dark" ? "☀️" : "🌙";

// Theme toggle handler
document.getElementById("themeToggle").addEventListener("click", () => {
    currentTheme = currentTheme === "light" ? "dark" : "light";
    document.documentElement.setAttribute("data-theme", currentTheme);
    localStorage.setItem("theme", currentTheme);
    document.getElementById("themeToggle").textContent = currentTheme === "dark" ? "☀️" : "🌙";
    renderAllCharts();
});

// Format currency in INR with Indian comma separators (e.g., ₹1,23,456.78)
function formatINR(val) {
    if (val === undefined || val === null || isNaN(val)) return "₹0";
    if (Math.abs(val) >= 10000000) {
        return `₹${(val / 10000000).toFixed(2)} Cr`;
    } else if (Math.abs(val) >= 100000) {
        return `₹${(val / 100000).toFixed(2)} Lakh`;
    }
    return new Intl.Numberen ? new Intl.NumberFormat('en-IN', { style: 'currency', currency: 'INR', maximumFractionDigits: 0 }).format(val) : `₹${val.toLocaleString('en-IN')}`;
}

function formatNumber(val) {
    if (val === undefined || val === null) return "0";
    return val.toLocaleString('en-IN');
}

// Fetch all JSON aggregate files
async function loadDashboardData() {
    const files = [
        "kpis", "daily_trend", "monthly", "payment_mix", "bank_success",
        "failure_reasons", "hourly_heatmap", "category_perf", "top_merchants",
        "latency", "incidents", "insights", "meta"
    ];

    try {
        const promises = files.map(file =>
            fetch(`data/${file}.json`).then(res => {
                if (!res.ok) throw new Error(`Failed to load ${file}.json`);
                return res.json();
            })
        );

        const results = await Promise.all(promises);
        files.forEach((file, index) => {
            rawData[file] = results[index];
        });

        initDashboard();
    } catch (err) {
        console.error("Error loading dashboard data:", err);
        document.getElementById("dataSourceMeta.textContent").textContent = "Error loading dashboard data. Run python main.py first.";
    }
}

// Initialize Dashboard UI & Filters
function initDashboard() {
    const meta = rawData.meta || {};
    const dataTypeText = meta.data_type === "synthetic" ? "Demo built on synthetic data" : "Live production data";
    document.getElementById("dataSourceMeta").textContent = `${dataTypeText} • ${formatNumber(meta.merchants_count)} merchants • ${formatNumber(meta.transactions_count)} transactions`;

    if (meta.data_type === "synthetic") {
        const footer = document.getElementById("footerMeta");
        footer.innerHTML = `Demo built on synthetic data • Generated at ${meta.generated_at} • Razorpay Analytics`;
    }

    populateFilters();
    renderAllCharts();
}

// Populate dropdown filter options dynamically
function populateFilters() {
    const paymentMix = rawData.payment_mix || [];
    const pmSelect = document.getElementById("paymentMethodFilter");
    paymentMix.forEach(item => {
        const opt = document.createElement("option");
        opt.value = item.payment_method;
        opt.textContent = item.payment_method;
        pmSelect.appendChild(opt);
    });

    const catPerf = rawData.category_perf || [];
    const catSelect = document.getElementById("categoryFilter");
    catPerf.forEach(item => {
        const opt = document.createElement("option");
        opt.value = item.category;
        opt.textContent = item.category;
        catSelect.appendChild(opt);
    });

    // Add filter change event listeners
    document.getElementById("dateFilter").addEventListener("change", renderAllCharts);
    document.getElementById("categoryFilter").addEventListener("change", renderAllCharts);
    document.getElementById("paymentMethodFilter").addEventListener("change", renderAllCharts);
}

// Master render function
function renderAllCharts() {
    renderKPIs();
    renderInsights();
    renderDailyTrend();
    renderMonthlyTrend();
    renderPaymentMix();
    renderMethodSuccess();
    renderFailureReasons();
    renderBankSuccess();
    renderHourlyHeatmap();
    renderCategoryPerf();
    renderTopMerchants();
    renderLatencyChart();
    renderIncidents();
}

// Plotly layout configuration helper based on theme
function getPlotlyConfig() {
    const isDark = currentTheme === "dark";
    return {
        paper_bgcolor: "transparent",
        plot_bgcolor: "transparent",
        font: {
            family: "Inter, sans-serif",
            color: isDark ? "#94a3b8" : "#475569",
            size: 12
        },
        margin: { t: 30, r: 20, b: 40, l: 50 },
        xaxis: {
            gridcolor: isDark ? "#334155" : "#e2e8f0",
            zerolinecolor: isDark ? "#334155" : "#e2e8f0"
        },
        yaxis: {
            gridcolor: isDark ? "#334155" : "#e2e8f0",
            zerolinecolor: isDark ? "#334155" : "#e2e8f0"
        }
    };
}

// 1. Render KPI Cards
function renderKPIs() {
    const kpis = rawData.kpis || {};
    const grid = document.getElementById("kpiGrid");
    grid.innerHTML = "";

    const definitions = [
        { key: "gmv", title: "GMV", format: v => formatINR(v) },
        { key: "success_rate", title: "Success Rate", format: v => `${v}%` },
        { key: "net_revenue", title: "Net Revenue", format: v => formatINR(v) },
        { key: "refund_rate", title: "Refund Rate", format: v => `${v}%` },
        { key: "avg_ticket", title: "Avg Ticket Size", format: v => formatINR(v) },
        { key: "active_merchants", title: "Active Merchants", format: v => formatNumber(v) }
    ];

    definitions.forEach(def => {
        const item = kpis[def.key] || { current: 0, previous: 0, change_pct: 0 };
        const chgClass = item.change_pct >= 0 ? "positive" : "negative";
        const chgSign = item.change_pct >= 0 ? "▲" : "▼";

        const card = document.createElement("div");
        card.className = "kpi-card";
        card.innerHTML = `
            <div class="kpi-title">${def.title}</div>
            <div class="kpi-value-row">
                <div class="kpi-value">${def.format(item.current)}</div>
                <div class="kpi-change ${chgClass}">${chgSign} ${Math.abs(item.change_pct)}%</div>
            </div>
        `;
        grid.appendChild(card);
    });
}

// 2. Render Insights Strip
function renderInsights() {
    const insights = rawData.insights || [];
    if (insights.length === 0) return;
    const randomInsight = insights[Math.floor(Math.random() * insights.length)];
    document.getElementById("insightText.textContent") || (document.getElementById("insightText").textContent = randomInsight.text);
}

// 3. Daily Trend Chart
function renderDailyTrend() {
    const data = rawData.daily_trend || [];
    const x = data.map(d => d.date);
    const y1 = data.map(d => d.txn_count);
    const y2 = data.map(d => d.gmv);

    const trace1 = {
        x: x,
        y: y1,
        type: "scatter",
        mode: "lines",
        name: "Transactions",
        line: { color: "#2563eb", width: 2 }
    };

    const trace2 = {
        x: x,
        y: y2,
        type: "scatter",
        mode: "lines",
        name: "GMV (₹)",
        yaxis: "y2",
        line: { color: "#10b981", width: 2 }
    };

    const layout = {
        ...getPlotlyConfig(),
        yaxis: { title: "Txn Count", side: "left" },
        yaxis2: { title: "GMV (INR)", overlaying: "y", side: "right", showgrid: false },
        legend: { orientation: "h", x: 0, y: 1.15 }
    };

    Plotly.newPlot("dailyTrendChart", [trace1, trace2], layout, { responsive: true, displayModeBar: false });
}

// 4. Monthly Trend Chart
function renderMonthlyTrend() {
    const data = rawData.monthly || [];
    const x = data.map(d => d.month);
    const y1 = data.map(d => d.gmv);
    const y2 = data.map(d => d.revenue);

    const trace1 = {
        x: x,
        y: y1,
        type: "bar",
        name: "GMV",
        marker: { color: "#3b82f6" }
    };

    const trace2 = {
        x: x,
        y: y2,
        type: "scatter",
        mode: "lines+markers",
        name: "Fee Revenue",
        yaxis: "y2",
        line: { color: "#f59e0b", width: 3 }
    };

    const layout = {
        ...getPlotlyConfig(),
        yaxis: { title: "GMV (INR)" },
        yaxis2: { title: "Revenue (INR)", overlaying: "y", side: "right", showgrid: false },
        legend: { orientation: "h", x: 0, y: 1.15 }
    };

    Plotly.newPlot("monthlyChart", [trace1, trace2], layout, { responsive: true, displayModeBar: false });
}

// 5. Payment Mix Donut
function renderPaymentMix() {
    const data = rawData.payment_mix || [];
    const labels = data.map(d => d.payment_method);
    const values = data.map(d => d.txn_count);

    const trace = {
        labels: labels,
        values: values,
        type: "pie",
        hole: 0.55,
        marker: { colors: ["#2563eb", "#3b82f6", "#60a5fa", "#93c5fd", "#bfdbfe", "#1e40af"] }
    };

    const layout = {
        ...getPlotlyConfig(),
        showlegend: true,
        legend: { orientation: "h", x: 0, y: -0.2 }
    };

    Plotly.newPlot("paymentMixChart", [trace], layout, { responsive: true, displayModeBar: false });
}

// 6. Method Success Bar
function renderMethodSuccess() {
    const data = rawData.payment_mix || [];
    const sorted = [...data].sort((a, b) => b.success_rate - a.success_rate);
    const x = sorted.map(d => d.success_rate);
    const y = sorted.map(d => d.payment_method);

    const trace = {
        x: x,
        y: y,
        type: "bar",
        orientation: "h",
        marker: { color: "#10b981" }
    };

    const layout = {
        ...getPlotlyConfig(),
        xaxis: { title: "Success Rate (%)", range: [0, 100] }
    };

    Plotly.newPlot("methodSuccessChart", [trace], layout, { responsive: true, displayModeBar: false });
}

// 7. Failure Reasons Bar
function renderFailureReasons() {
    const data = rawData.failure_reasons || [];
    const sorted = [...data].sort((a, b) => a.count - b.count);
    const x = sorted.map(d => d.count);
    const y = sorted.map(d => d.failure_reason);

    const trace = {
        x: x,
        y: y,
        type: "bar",
        orientation: "h",
        marker: { color: "#ef4444" }
    };

    const layout = {
        ...getPlotlyConfig(),
        xaxis: { title: "Failure Count" }
    };

    Plotly.newPlot("failureReasonsChart", [trace], layout, { responsive: true, displayModeBar: false });
}

// 8. Bank Success Bar
function renderBankSuccess() {
    const data = rawData.bank_success || [];
    const sorted = [...data].sort((a, b) => a.success_rate - b.success_rate);
    const x = sorted.map(d => d.success_rate);
    const y = sorted.map(d => d.issuing_bank);

    const trace = {
        x: x,
        y: y,
        type: "bar",
        orientation: "h",
        marker: { color: "#3b82f6" }
    };

    const layout = {
        ...getPlotlyConfig(),
        xaxis: { title: "Success Rate (%)", range: [0, 100] }
    };

    Plotly.newPlot("bankSuccessChart", [trace], layout, { responsive: true, displayModeBar: false });
}

// 9. Hourly Heatmap
function renderHourlyHeatmap() {
    const data = rawData.hourly_heatmap || [];
    const days = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"];
    const hours = Array.from({length: 24}, (_, i) => i);

    // Build 2D matrix for failure rate
    const z = days.map(day => {
        return hours.map(hour => {
            const found = data.find(d => d.day_of_week === day && d.hour === hour);
            return found ? found.failure_rate : 0;
        });
    });

    const trace = {
        z: z,
        x: hours.map(h => `${h}:00`),
        y: days,
        type: "heatmap",
        colorscale: "Reds",
        colorbar: { title: "Fail %" }
    };

    const layout = {
        ...getPlotlyConfig(),
        xaxis: { title: "Hour of Day" }
    };

    Plotly.newPlot("hourlyHeatmapChart", [trace], layout, { responsive: true, displayModeBar: false });
}

// 10. Category Performance Scatter
function renderCategoryPerf() {
    const data = rawData.category_perf || [];
    const x = data.map(d => d.gmv);
    const y = data.map(d => d.success_rate);
    const size = data.map(d => Math.sqrt(d.txn_count) * 2);
    const text = data.map(d => `${d.category}<br>GMV: ${formatINR(d.gmv)}<br>Success: ${d.success_rate}%`);

    const trace = {
        x: x,
        y: y,
        text: text,
        mode: "markers+text",
        textposition: "top center",
        marker: {
            size: size,
            color: "#2563eb",
            opacity: 0.7,
            sizemode: "diameter"
        },
        type: "scatter"
    };

    const layout = {
        ...getPlotlyConfig(),
        xaxis: { title: "Total GMV (INR)" },
        yaxis: { title: "Success Rate (%)", range: [70, 100] }
    };

    Plotly.newPlot("categoryPerfChart", [trace], layout, { responsive: true, displayModeBar: false });
}

// 11. Top Merchants Concentration
function renderTopMerchants() {
    const data = rawData.top_merchants || [];
    const x = data.map(d => d.merchant_rank);
    const y = data.map(d => d.gmv_share_pct);

    const trace = {
        x: x,
        y: y,
        type: "scatter",
        mode: "lines+markers",
        line: { color: "#8b5cf6", width: 3 },
        marker: { size: 8 }
    };

    const layout = {
        ...getPlotlyConfig(),
        xaxis: { title: "Merchant Rank" },
        yaxis: { title: "Cumulative GMV Share (%)" }
    };

    Plotly.newPlot("topMerchantsChart", [trace], layout, { responsive: true, displayModeBar: false });
}

// 12. Latency Percentiles
function renderLatencyChart() {
    const data = rawData.latency || [];
    const x = data.map(d => d.month);

    const traces = [
        { x: x, y: data.map(d => d.p50), name: "p50", type: "scatter", mode: "lines", line: { color: "#10b981" } },
        { x: x, y: data.map(d => d.p90), name: "p90", type: "scatter", mode: "lines", line: { color: "#f59e0b" } },
        { x: x, y: data.map(d => d.p99), name: "p99", type: "scatter", mode: "lines", line: { color: "#ef4444" } }
    ];

    const layout = {
        ...getPlotlyConfig(),
        yaxis: { title: "Latency (ms)" },
        legend: { orientation: "h", x: 0, y: 1.15 }
    };

    Plotly.newPlot("latencyChart", traces, layout, { responsive: true, displayModeBar: false });
}

// 13. Incidents
function renderIncidents() {
    const incidents = rawData.incidents || [];
    const container = document.getElementById("incidentContainer");
    container.innerHTML = "";

    if (incidents.length === 0) {
        container.innerHTML = `<p class="empty-state">No active incidents detected in the selected period.</p>`;
        return;
    }

    incidents.forEach(inc => {
        const item = document.createElement("div");
        item.className = "incident-item";
        item.innerHTML = `
            <div class="incident-info">
                <h4>Outage Incident: ${inc.start_time} to ${inc.end_time}</h4>
                <p>Peak Failure Rate: <strong>${inc.peak_failure_rate_pct}%</strong> | Affected Txns: ${formatNumber(inc.affected_txns)} | Root Cause: ${inc.top_failure_reason}</p>
            </div>
            <div class="incident-badge">CRITICAL</div>
        `;
        container.appendChild(item);
    });
}

// Load data on startup
loadDashboardData();
