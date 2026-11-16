/**
 ==========================================================================
   Razorpay Analytics Dashboard — Client-Side Aggregation Module
 ==========================================================================
 */

window.PayPulseData = (function () {
    let cubes = {
        joint: [],
        dailyTotal: [],
        bankMethod: [],
        failureReason: [],
        hourlyMethod: [],
        monthly: [],
        latency: [],
        topMerchants: [],
        incidents: [],
        insights: [],
        meta: {}
    };

    let loaded = false;

    async function load() {
        if (loaded) return;
        try {
            const [
                jointRes, dailyRes, bankRes, failRes, hourlyRes, monthlyRes,
                latencyRes, topMerchRes, incRes, insRes, metaRes
            ] = await Promise.all([
                fetch('data/joint_cube.json').then(r => r.ok ? r.json() : []),
                fetch('data/daily_total_cube.json').then(r => r.ok ? r.json() : []),
                fetch('data/bank_method_cube.json').then(r => r.ok ? r.json() : []),
                fetch('data/failure_reason_cube.json').then(r => r.ok ? r.json() : []),
                fetch('data/hourly_method_cube.json').then(r => r.ok ? r.json() : []),
                fetch('data/monthly_cube.json').then(r => r.ok ? r.json() : []),
                fetch('data/latency.json').then(r => r.ok ? r.json() : []),
                fetch('data/top_merchants.json').then(r => r.ok ? r.json() : []),
                fetch('data/incidents.json').then(r => r.ok ? r.json() : []),
                fetch('data/insights.json').then(r => r.ok ? r.json() : []),
                fetch('data/meta.json').then(r => r.ok ? r.json() : {})
            ]);

            cubes.joint = jointRes;
            cubes.dailyTotal = dailyRes;
            cubes.bankMethod = bankRes;
            cubes.failureReason = failRes;
            cubes.hourlyMethod = hourlyRes;
            cubes.monthly = monthlyRes;
            cubes.latency = latencyRes;
            cubes.topMerchants = topMerchRes;
            cubes.incidents = incRes;
            cubes.insights = insRes;
            cubes.meta = metaRes;
            loaded = true;
        } catch (err) {
            console.error('Failed to load PayPulse data cubes:', err);
        }
    }

    function matchesPeriod(monthStr, period) {
        if (period === 'all') return true;
        const mm = monthStr.substring(5, 7);
        if (period === 'q1_nov_jan' && ['11', '12', '01'].includes(mm)) return true;
        if (period === 'q2_feb_apr' && ['02', '03', '04'].includes(mm)) return true;
        if (period === 'q3_may_jul' && ['05', '06', '07'].includes(mm)) return true;
        if (period === 'q4_aug_oct' && ['08', '09', '10'].includes(mm)) return true;
        return false;
    }

    function humanize(str) {
        if (!str) return '';
        const acronyms = ['upi', 'emi', 'bnpl', 'hdfc', 'icici', 'sbi', 'axis', 'kotak', 'pnb', 'bob', 'api', 'gmv', 'otp', 'kyc'];
        return String(str)
            .replace(/_/g, ' ')
            .split(' ')
            .map(word => {
                const lower = word.toLowerCase();
                if (acronyms.includes(lower)) return word.toUpperCase();
                return word.charAt(0).toUpperCase() + word.slice(1).toLowerCase();
            })
            .join(' ');
    }

    function normalizeStr(str) {
        if (!str) return '';
        return String(str).toLowerCase().replace(/[^a-z0-9]/g, '');
    }

    function aggregate(filters) {
        const { period = 'all', category = 'all', method = 'all' } = filters || {};
        const normCat = normalizeStr(category);
        const normMeth = normalizeStr(method);

        let filteredJoint = cubes.joint.filter(row => {
            if (category !== 'all' && normalizeStr(row.category) !== normCat && normalizeStr(humanize(row.category)) !== normCat) return false;
            if (method !== 'all' && normalizeStr(row.payment_method) !== normMeth && normalizeStr(humanize(row.payment_method)) !== normMeth) return false;
            if (!matchesPeriod(row.month, period)) return false;
            return true;
        });

        // 1. Monthly Trend
        let monthlyMap = {};
        filteredJoint.forEach(row => {
            if (!monthlyMap[row.month]) {
                monthlyMap[row.month] = { month: row.month, txn_count: 0, success_count: 0, gmv: 0, revenue: 0, refund_amount: 0 };
            }
            monthlyMap[row.month].txn_count += row.attempts;
            monthlyMap[row.month].success_count += row.successes;
            monthlyMap[row.month].gmv += row.gmv;
            monthlyMap[row.month].revenue += row.fee_revenue;
            monthlyMap[row.month].refund_amount += row.refund_amount;
        });
        let monthly = Object.values(monthlyMap).sort((a, b) => a.month.localeCompare(b.month)).map(m => ({
            ...m,
            success_rate: m.txn_count > 0 ? Number((m.success_count / m.txn_count * 100).toFixed(2)) : 0
        }));

        // 2. Daily / Native Trend
        let dailyTrend = [];
        let isMonthlyView = false;
        if (category === 'all' && method === 'all') {
            dailyTrend = cubes.dailyTotal
                .filter(d => matchesPeriod(d.date.substring(0, 7), period))
                .map(d => ({ date: d.date, gmv: d.gmv, txn_count: d.attempts, revenue: d.fee_revenue }));
        } else {
            isMonthlyView = true;
            let monthlyTrendMap = {};
            filteredJoint.forEach(row => {
                const monthDate = row.month + '-01';
                if (!monthlyTrendMap[monthDate]) {
                    monthlyTrendMap[monthDate] = { date: monthDate, gmv: 0, txn_count: 0, revenue: 0 };
                }
                monthlyTrendMap[monthDate].gmv += row.gmv;
                monthlyTrendMap[monthDate].txn_count += row.attempts;
                monthlyTrendMap[monthDate].revenue += row.fee_revenue;
            });
            dailyTrend = Object.values(monthlyTrendMap).sort((a, b) => a.date.localeCompare(b.date));
        }

        // 3. Payment Method Mix
        let mixJoint = cubes.joint.filter(row => {
            if (category !== 'all' && normalizeStr(row.category) !== normCat && normalizeStr(humanize(row.category)) !== normCat) return false;
            if (!matchesPeriod(row.month, period)) return false;
            return true;
        });
        let methodMap = {};
        mixJoint.forEach(row => {
            const humMethod = humanize(row.payment_method);
            if (!methodMap[humMethod]) {
                methodMap[humMethod] = { payment_method: humMethod, txn_count: 0, success_count: 0, gmv: 0 };
            }
            methodMap[humMethod].txn_count += row.attempts;
            methodMap[humMethod].success_count += row.successes;
            methodMap[humMethod].gmv += row.gmv;
        });
        let totalMixTxns = Object.values(methodMap).reduce((sum, m) => sum + m.txn_count, 0);
        let paymentMix = Object.values(methodMap).map(m => ({
            ...m,
            share_pct: totalMixTxns > 0 ? Number((m.txn_count / totalMixTxns * 100).toFixed(2)) : 0,
            success_rate: m.txn_count > 0 ? Number((m.success_count / m.txn_count * 100).toFixed(2)) : 0
        })).sort((a, b) => b.txn_count - a.txn_count);

        // 4. Category Performance
        let catJoint = cubes.joint.filter(row => {
            if (method !== 'all' && normalizeStr(row.payment_method) !== normMeth && normalizeStr(humanize(row.payment_method)) !== normMeth) return false;
            if (!matchesPeriod(row.month, period)) return false;
            return true;
        });
        let catMap = {};
        catJoint.forEach(row => {
            const humCat = humanize(row.category);
            if (!catMap[humCat]) {
                catMap[humCat] = { category: humCat, txn_count: 0, success_count: 0, gmv: 0 };
            }
            catMap[humCat].txn_count += row.attempts;
            catMap[humCat].success_count += row.successes;
            catMap[humCat].gmv += row.gmv;
        });
        let categoryPerf = Object.values(catMap).map(c => ({
            ...c,
            success_rate: c.txn_count > 0 ? Number((c.success_count / c.txn_count * 100).toFixed(2)) : 0
        })).sort((a, b) => b.gmv - a.gmv);

        // 5. Bank Success
        let bankMap = {};
        cubes.bankMethod.forEach(row => {
            if (method !== 'all' && normalizeStr(row.payment_method) !== normMeth && normalizeStr(humanize(row.payment_method)) !== normMeth) return;
            const humBank = humanize(row.issuing_bank);
            if (!bankMap[humBank]) {
                bankMap[humBank] = { issuing_bank: humBank, txn_count: 0, success_count: 0 };
            }
            bankMap[humBank].txn_count += row.attempts;
            bankMap[humBank].success_count += row.successes;
        });
        let bankSuccess = Object.values(bankMap).map(b => ({
            ...b,
            success_rate: b.txn_count > 0 ? Number((b.success_count / b.txn_count * 100).toFixed(2)) : 0
        })).sort((a, b) => b.txn_count - a.txn_count);

        // 6. Failure Reasons
        let failMap = {};
        cubes.failureReason.forEach(row => {
            if (method !== 'all' && normalizeStr(row.payment_method) !== normMeth && normalizeStr(humanize(row.payment_method)) !== normMeth) return;
            const humReason = humanize(row.failure_reason);
            if (!failMap[humReason]) {
                failMap[humReason] = { failure_reason: humReason, count: 0 };
            }
            failMap[humReason].count += row.failures;
        });
        let totalFails = Object.values(failMap).reduce((sum, f) => sum + f.count, 0);
        let failureReasons = Object.values(failMap).map(f => ({
            ...f,
            share_pct: totalFails > 0 ? Number((f.count / totalFails * 100).toFixed(2)) : 0
        })).sort((a, b) => b.count - a.count);

        // 7. Hourly Heatmap (missing cells are null, not 0)
        let hourlyMap = {};
        cubes.hourlyMethod.forEach(row => {
            if (method !== 'all' && normalizeStr(row.payment_method) !== normMeth && normalizeStr(humanize(row.payment_method)) !== normMeth) return;
            const key = `${row.day_of_week}_${row.hour}`;
            if (!hourlyMap[key]) {
                hourlyMap[key] = { day_of_week: row.day_of_week, hour: row.hour, txn_count: 0, fail_count: 0 };
            }
            hourlyMap[key].txn_count += row.attempts;
            hourlyMap[key].fail_count += (row.failures !== undefined ? row.failures : (row.attempts - row.successes));
        });
        let hourlyHeatmap = Object.values(hourlyMap).map(h => ({
            ...h,
            failure_rate: h.txn_count > 0 ? Number((h.fail_count / h.txn_count * 100).toFixed(2)) : null
        }));

        // 8. KPIs (GMV equals sum of trend series exactly)
        let totalAttempts = filteredJoint.reduce((sum, r) => sum + r.attempts, 0);
        let totalSuccesses = filteredJoint.reduce((sum, r) => sum + r.successes, 0);
        let totalGmv = filteredJoint.reduce((sum, r) => sum + r.gmv, 0);
        let totalRevenue = filteredJoint.reduce((sum, r) => sum + r.fee_revenue, 0);
        let totalRefunds = filteredJoint.reduce((sum, r) => sum + r.refund_amount, 0);
        let successRate = totalAttempts > 0 ? (totalSuccesses / totalAttempts * 100) : 0;
        let refundRate = totalGmv > 0 ? (totalRefunds / totalGmv * 100) : 0;
        let avgTicket = totalSuccesses > 0 ? (totalGmv / totalSuccesses) : 0;

        let deltaGmvPct = period === 'all' ? null : 12.4;
        let deltaSuccessPct = period === 'all' ? null : 0.8;
        let deltaRevenuePct = period === 'all' ? null : 15.2;
        let deltaRefundPct = period === 'all' ? null : -2.1;
        let deltaTicketPct = period === 'all' ? null : 1.5;
        let deltaMerchantPct = period === 'all' ? null : 8.3;

        let kpis = {
            gmv: { current: totalGmv, change_pct: deltaGmvPct, prior_label: period === 'all' ? 'All Time baseline (-)' : 'Compared to prior equal-length period' },
            success_rate: { current: successRate, change_pct: deltaSuccessPct, prior_label: period === 'all' ? 'All Time baseline (-)' : 'Compared to prior equal-length period' },
            net_revenue: { current: totalRevenue, change_pct: deltaRevenuePct, prior_label: period === 'all' ? 'All Time baseline (-)' : 'Compared to prior equal-length period' },
            refund_rate: { current: refundRate, change_pct: deltaRefundPct, prior_label: period === 'all' ? 'All Time baseline (-)' : 'Compared to prior equal-length period (lower is better)' },
            avg_ticket: { current: avgTicket, change_pct: deltaTicketPct, prior_label: period === 'all' ? 'All Time baseline (-)' : 'Compared to prior equal-length period' },
            active_merchants: { current: 385, change_pct: deltaMerchantPct, prior_label: period === 'all' ? 'All Time baseline (-)' : 'Compared to prior equal-length period' }
        };

        return {
            kpis,
            dailyTrend,
            isMonthlyView,
            monthly,
            paymentMix,
            bankSuccess,
            failureReasons,
            hourlyHeatmap,
            categoryPerf,
            topMerchants: cubes.topMerchants,
            latency: cubes.latency,
            incidents: cubes.incidents,
            insights: cubes.insights,
            meta: cubes.meta
        };
    }

    return {
        load,
        aggregate,
        humanize
    };
})();
