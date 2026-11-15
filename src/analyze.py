"""
src/analyze.py — Analysis module for payments analytics and incident detection.
Strictly adheres to algorithms specified in prompt.
"""

import logging
import pandas as pd
import numpy as np

log = logging.getLogger("pipeline.analyze")


def compute_all_analyses(merchants_df: pd.DataFrame, txn_df: pd.DataFrame, config: dict) -> dict:
    """Run all analytical computations and return a dictionary of results."""
    log.info("Starting analytics computations...")
    analysis_cfg = config.get("analysis", {})
    min_group_size = analysis_cfg.get("min_group_size", 10)

    kpis = compute_kpis(txn_df, config)
    payment_mix = compute_payment_mix(txn_df, config)
    latency = compute_latency(txn_df)
    incidents = detect_incidents(txn_df, config)

    results = {
        "kpis": kpis,
        "daily_trend": compute_daily_trend(txn_df, config),
        "monthly": compute_monthly(txn_df, config),
        "payment_mix": payment_mix,
        "bank_success": compute_bank_success(txn_df, config, min_group_size),
        "failure_reasons": compute_failure_reasons(txn_df, config, min_group_size),
        "hourly_heatmap": compute_hourly_heatmap(txn_df, config, min_group_size),
        "category_perf": compute_category_perf(txn_df, merchants_df, config, min_group_size),
        "top_merchants": compute_top_merchants(txn_df, merchants_df, config, min_group_size),
        "latency": latency,
        "incidents": incidents,
        "insights": generate_insights(kpis, payment_mix, incidents, latency),
    }

    log.info("All analytics computations completed successfully.")
    return results


def compute_kpis(txn: pd.DataFrame, config: dict) -> dict:
    """Compute core KPIs and % change vs previous period."""
    if len(txn) == 0:
        return {}

    cfg = config.get("analysis", {})
    success_statuses = cfg.get("success_statuses", ["captured", "refunded", "partially_refunded"])
    months_window = cfg.get("period_comparison_months", 6)

    _is_success = txn["status"].isin(success_statuses)

    # Split data into current and previous windows by months
    max_date = txn["created_at"].max()
    split_date = max_date - pd.DateOffset(months=months_window)
    prev_split_date = split_date - pd.DateOffset(months=months_window)

    curr_df = txn[txn["created_at"] >= split_date]
    prev_df = txn[(txn["created_at"] >= prev_split_date) & (txn["created_at"] < split_date)]

    def _calc(df: pd.DataFrame) -> dict:
        if len(df) == 0:
            return {
                "gmv": 0.0,
                "success_rate": 0.0,
                "net_revenue": 0.0,
                "refund_rate": 0.0,
                "avg_ticket": 0.0,
                "active_merchants": 0,
            }

        s_mask = df["status"].isin(success_statuses)
        gmv = float(df.loc[s_mask, "amount_inr"].sum())
        success_rate = float(s_mask.mean() * 100)
        net_revenue = float(df.loc[s_mask, "fee_inr"].sum())
        total_refunds = float(df.loc[s_mask, "refund_amount_inr"].sum())
        refund_rate = (total_refunds / gmv * 100) if gmv > 0 else 0.0
        avg_ticket = float(df.loc[s_mask, "amount_inr"].mean()) if s_mask.sum() > 0 else 0.0
        active_merchants = int(df.loc[s_mask, "merchant_id"].nunique())

        return {
            "gmv": round(gmv, 2),
            "success_rate": round(success_rate, 2),
            "net_revenue": round(net_revenue, 2),
            "refund_rate": round(refund_rate, 2),
            "avg_ticket": round(avg_ticket, 2),
            "active_merchants": active_merchants,
        }

    curr = _calc(curr_df)
    prev = _calc(prev_df)

    def _pct(c, p):
        if p == 0:
            return 0.0
        return round(((c - p) / p) * 100, 2)

    res = {}
    for k in curr:
        c_val = curr[k]
        p_val = prev[k]
        res[k] = {
            "current": c_val,
            "previous": p_val,
            "change_pct": _pct(c_val, p_val),
        }

    return res


def compute_daily_trend(txn: pd.DataFrame, config: dict) -> list[dict]:
    """Compute daily transaction volume and GMV."""
    if len(txn) == 0:
        return []
    cfg = config.get("analysis", {})
    success_statuses = cfg.get("success_statuses", ["captured", "refunded", "partially_refunded"])

    df = txn.copy()
    df["date_str"] = df["created_at"].dt.date.astype(str)
    df["_is_success"] = df["status"].isin(success_statuses)

    grouped = df.groupby("date_str").agg(
        txn_count=("txn_id", "count"),
        success_count=("_is_success", "sum"),
        gmv=("amount_inr", lambda x: float(x[df.loc[x.index, "_is_success"]].sum())),
        revenue=("fee_inr", lambda x: float(x[df.loc[x.index, "_is_success"]].sum())),
    ).reset_index().rename(columns={"date_str": "date"})

    return grouped.to_dict(orient="records")


def compute_monthly(txn: pd.DataFrame, config: dict) -> list[dict]:
    """Compute monthly summary trend."""
    if len(txn) == 0:
        return []
    cfg = config.get("analysis", {})
    success_statuses = cfg.get("success_statuses", ["captured", "refunded", "partially_refunded"])

    df = txn.copy()
    df["month_str"] = df["created_at"].dt.to_period("M").astype(str)
    df["_is_success"] = df["status"].isin(success_statuses)

    grouped = df.groupby("month_str").agg(
        txn_count=("txn_id", "count"),
        success_count=("_is_success", "sum"),
        gmv=("amount_inr", lambda x: float(x[df.loc[x.index, "_is_success"]].sum())),
        revenue=("fee_inr", lambda x: float(x[df.loc[x.index, "_is_success"]].sum())),
        refund_amount=("refund_amount_inr", "sum"),
    ).reset_index().rename(columns={"month_str": "month"})

    grouped["success_rate"] = (grouped["success_count"] / grouped["txn_count"] * 100).round(2)
    return grouped.to_dict(orient="records")


def compute_payment_mix(txn: pd.DataFrame, config: dict) -> list[dict]:
    """Compute payment method breakdown and success rate."""
    if len(txn) == 0:
        return []
    cfg = config.get("analysis", {})
    success_statuses = cfg.get("success_statuses", ["captured", "refunded", "partially_refunded"])

    df = txn.copy()
    df["_is_success"] = df["status"].isin(success_statuses)

    grouped = df.groupby("payment_method").agg(
        txn_count=("txn_id", "count"),
        success_count=("_is_success", "sum"),
        gmv=("amount_inr", lambda x: float(x[df.loc[x.index, "_is_success"]].sum())),
    ).reset_index()

    total = grouped["txn_count"].sum()
    grouped["share_pct"] = (grouped["txn_count"] / total * 100).round(2)
    grouped["success_rate"] = (grouped["success_count"] / grouped["txn_count"] * 100).round(2)

    return grouped.to_dict(orient="records")


def compute_bank_success(txn: pd.DataFrame, config: dict, min_group_size: int) -> list[dict]:
    """Compute bank-wise success rate with minimum group size filtering."""
    if len(txn) == 0 or "issuing_bank" not in txn.columns:
        return []
    cfg = config.get("analysis", {})
    success_statuses = cfg.get("success_statuses", ["captured", "refunded", "partially_refunded"])

    df = txn.dropna(subset=["issuing_bank"]).copy()
    df["_is_success"] = df["status"].isin(success_statuses)

    grouped = df.groupby("issuing_bank").agg(
        txn_count=("txn_id", "count"),
        success_count=("_is_success", "sum"),
    ).reset_index()

    grouped = grouped[grouped["txn_count"] >= min_group_size].copy()
    grouped["success_rate"] = (grouped["success_count"] / grouped["txn_count"] * 100).round(2)
    grouped = grouped.sort_values("txn_count", ascending=False)

    return grouped.to_dict(orient="records")


def compute_failure_reasons(txn: pd.DataFrame, config: dict, min_group_size: int) -> list[dict]:
    """Compute breakdown of failure reasons with min group size filtering."""
    if len(txn) == 0 or "failure_reason" not in txn.columns:
        return []
    cfg = config.get("analysis", {})
    failed_status = cfg.get("failed_status", "failed")

    failed_df = txn[txn["status"] == failed_status].dropna(subset=["failure_reason"]).copy()
    if len(failed_df) == 0:
        return []

    grouped = failed_df.groupby("failure_reason").agg(
        count=("txn_id", "count"),
    ).reset_index()

    grouped = grouped[grouped["count"] >= min_group_size].copy()
    total_failed = grouped["count"].sum()
    if total_failed > 0:
        grouped["share_pct"] = (grouped["count"] / total_failed * 100).round(2)
    else:
        grouped["share_pct"] = 0.0

    grouped = grouped.sort_values("count", ascending=False)
    return grouped.to_dict(orient="records")


def compute_hourly_heatmap(txn: pd.DataFrame, config: dict, min_group_size: int) -> list[dict]:
    """Compute hour x day-of-week failure rate heatmap."""
    if len(txn) == 0:
        return []
    cfg = config.get("analysis", {})
    failed_status = cfg.get("failed_status", "failed")

    df = txn.copy()
    df["_is_fail"] = df["status"] == failed_status

    grouped = df.groupby(["day_of_week", "hour"]).agg(
        txn_count=("txn_id", "count"),
        fail_count=("_is_fail", "sum"),
    ).reset_index()

    grouped = grouped[grouped["txn_count"] >= min_group_size].copy()
    grouped["failure_rate"] = (grouped["fail_count"] / grouped["txn_count"] * 100).round(2)
    return grouped.to_dict(orient="records")


def compute_category_perf(txn: pd.DataFrame, merchants: pd.DataFrame, config: dict, min_group_size: int) -> list[dict]:
    """Compute performance by merchant category."""
    if len(txn) == 0 or len(merchants) == 0:
        return []
    cfg = config.get("analysis", {})
    success_statuses = cfg.get("success_statuses", ["captured", "refunded", "partially_refunded"])

    merged = txn.merge(merchants[["merchant_id", "category"]], on="merchant_id", how="left")
    merged["_is_success"] = merged["status"].isin(success_statuses)

    grouped = merged.groupby("category").agg(
        txn_count=("txn_id", "count"),
        success_count=("_is_success", "sum"),
        gmv=("amount_inr", lambda x: float(x[merged.loc[x.index, "_is_success"]].sum())),
        merchant_count=("merchant_id", "nunique"),
    ).reset_index()

    grouped = grouped[grouped["txn_count"] >= min_group_size].copy()
    grouped["success_rate"] = (grouped["success_count"] / grouped["txn_count"] * 100).round(2)
    grouped["avg_gmv_per_merchant"] = (grouped["gmv"] / grouped["merchant_count"]).round(2)

    return grouped.to_dict(orient="records")


def compute_top_merchants(txn: pd.DataFrame, merchants: pd.DataFrame, config: dict, min_group_size: int) -> list[dict]:
    """Compute top N merchants by GMV and their cumulative share (anonymized for privacy)."""
    if len(txn) == 0 or len(merchants) == 0:
        return []
    cfg = config.get("analysis", {})
    success_statuses = cfg.get("success_statuses", ["captured", "refunded", "partially_refunded"])
    top_n = cfg.get("top_n_merchants", 10)

    success_df = txn[txn["status"].isin(success_statuses)]
    gmv_by_merch = success_df.groupby("merchant_id")["amount_inr"].sum().reset_index()
    gmv_by_merch = gmv_by_merch.merge(merchants[["merchant_id", "category", "tier"]], on="merchant_id", how="left")
    gmv_by_merch = gmv_by_merch.sort_values("amount_inr", ascending=False).head(top_n).reset_index(drop=True)

    total_gmv = success_df["amount_inr"].sum()
    if total_gmv > 0:
        gmv_by_merch["gmv_share_pct"] = (gmv_by_merch["amount_inr"] / total_gmv * 100).round(2)
    else:
        gmv_by_merch["gmv_share_pct"] = 0.0

    gmv_by_merch = gmv_by_merch.rename(columns={"amount_inr": "gmv"})
    gmv_by_merch["merchant_rank"] = [f"Merchant #{i+1}" for i in range(len(gmv_by_merch))]
    gmv_by_merch = gmv_by_merch.drop(columns=["merchant_id"])

    return gmv_by_merch.to_dict(orient="records")


def compute_latency(txn: pd.DataFrame) -> list[dict]:
    """Compute monthly API latency percentiles (p50, p90, p99)."""
    if len(txn) == 0 or "api_latency_ms" not in txn.columns:
        return []

    df = txn.copy()
    df["month_str"] = df["created_at"].dt.to_period("M").astype(str)

    grouped = df.groupby("month_str").agg(
        p50=("api_latency_ms", lambda x: float(np.percentile(x.dropna(), 50))),
        p90=("api_latency_ms", lambda x: float(np.percentile(x.dropna(), 90))),
        p99=("api_latency_ms", lambda x: float(np.percentile(x.dropna(), 99))),
        mean_latency=("api_latency_ms", "mean"),
    ).reset_index().rename(columns={"month_str": "month"})

    for col in ["p50", "p90", "p99", "mean_latency"]:
        grouped[col] = grouped[col].round(1)

    return grouped.to_dict(orient="records")


def detect_incidents(txn: pd.DataFrame, config: dict) -> list[dict]:
    """
    Detect incidents using daily failure-rate z-scores with relative lift check.
    """
    if len(txn) == 0:
        return []

    cfg = config.get("analysis", {})
    z_thresh = cfg.get("incident_zscore_threshold", 3.0)
    min_vol = cfg.get("incident_min_volume", 30)
    failed_status = cfg.get("failed_status", "failed")
    window_days = cfg.get("incident_rolling_window_days", 7)

    df = txn.copy()
    df["_day"] = df["created_at"].dt.floor("D")
    df["_hour"] = df["created_at"].dt.floor("h")
    df["_is_fail"] = df["status"] == failed_status

    # Daily aggregation
    daily = df.groupby("_day").agg(
        txn_count=("txn_id", "count"),
        fail_count=("_is_fail", "sum"),
    ).reset_index()
    daily["failure_rate"] = daily["fail_count"] / daily["txn_count"].replace(0, 1) * 100

    # Fill missing days
    full_days = pd.date_range(daily["_day"].min(), daily["_day"].max(), freq="D")
    daily = daily.set_index("_day").reindex(full_days, fill_value=0).reset_index()
    daily = daily.rename(columns={"index": "_day"})

    # Rolling baseline
    daily["roll_mean"] = daily["failure_rate"].rolling(window_days, min_periods=3).mean().shift(1)
    daily["roll_std"] = daily["failure_rate"].rolling(window_days, min_periods=3).std().shift(1)
    daily["roll_std"] = daily["roll_std"].fillna(daily["failure_rate"].std() or 1.0)

    daily["z_score"] = np.where(
        (daily["roll_std"] > 0) & (daily["txn_count"] >= min_vol),
        (daily["failure_rate"] - daily["roll_mean"]) / daily["roll_std"],
        0.0,
    )

    # Flag with z-score AND relative lift (2x baseline)
    daily["relative_lift"] = daily["failure_rate"] / daily["roll_mean"].replace(0, np.nan)
    flagged = daily[
        (daily["z_score"] > z_thresh)
        & (daily["txn_count"] >= min_vol)
        & (daily["relative_lift"] > 2.0)
    ]

    if len(flagged) == 0:
        log.info("Incident detection: 0 incidents found")
        return []

    # Merge adjacent days
    flagged = flagged.sort_values("_day").reset_index(drop=True)
    flagged["_gap_days"] = flagged["_day"].diff().dt.days.fillna(999)
    flagged["_incident_group"] = (flagged["_gap_days"] > 1).cumsum()

    incidents = []
    for _, grp in flagged.groupby("_incident_group"):
        start_day = grp["_day"].min()
        end_day = grp["_day"].max()

        # Peak hour for context
        day_mask = (df["_day"] >= start_day) & (df["_day"] <= end_day)
        inc_txns = df[day_mask]

        hourly = inc_txns.groupby("_hour").agg(
            txn_count=("txn_id", "count"),
            fail_count=("_is_fail", "sum"),
        ).reset_index()
        hourly["failure_rate"] = hourly["fail_count"] / hourly["txn_count"].replace(0, 1) * 100

        if len(hourly) == 0:
            continue

        hourly["severity"] = hourly["failure_rate"] * hourly["fail_count"]
        peak = hourly.loc[hourly["severity"].idxmax()]

        # Daily rate for the incident (not peak-hour rate)
        daily_rate = float(grp["failure_rate"].max())
        affected = int(grp["txn_count"].sum())

        reasons = inc_txns[inc_txns["_is_fail"]]["failure_reason"].dropna()
        top_reason = str(reasons.mode()[0]) if len(reasons) else "unknown"

        incidents.append({
            "start_time": str(start_day),
            "end_time": str(end_day + pd.Timedelta(days=1)),
            "peak_hour": str(peak["_hour"]),
            "peak_failure_rate_pct": round(daily_rate, 1),
            "affected_txns": affected,
            "top_failure_reason": top_reason,
        })

    # Sort by severity (daily_rate * affected) descending
    incidents.sort(
        key=lambda x: x["peak_failure_rate_pct"] * x["affected_txns"],
        reverse=True,
    )

    log.info("Incident detection: %d incidents found", len(incidents))
    return incidents

def generate_insights(kpis: dict, payment_mix: list[dict], incidents: list[dict], latency: list[dict]) -> list[dict]:
    """Generate template-based analytical insights."""
    insights = []

    # 1. Top payment method
    if payment_mix:
        top_pm = payment_mix[0]
        insights.append({
            "category": "Payment Methods",
            "text": f"{top_pm['payment_method']} leads with {top_pm['share_pct']:.1f}% share and {top_pm['success_rate']:.1f}% success rate."
        })

    # 2. Success rate KPI insight
    sr = kpis.get("success_rate", {})
    if sr:
        cur = sr.get("current", 0)
        chg = sr.get("change_pct", 0)
        direction = "up" if chg >= 0 else "down"
        insights.append({
            "category": "Overall Performance",
            "text": f"Success rate is {cur:.2f}% ({direction} {abs(chg):.2f}% vs prior period)."
        })

    # 3. Largest incident insight
    if incidents:
        inc = incidents[0]
        insights.append({
            "category": "Incident Alert",
            "text": f"Largest incident: {inc['start_time']} to {inc['end_time']} — {inc['peak_failure_rate_pct']}% peak failure rate across {inc['affected_txns']} txns (main cause: {inc['top_failure_reason']})."
        })

    # 4. Latency insight
    if latency:
        latest = latency[-1]
        insights.append({
            "category": "API Performance",
            "text": f"Latest month latency percentiles — p50: {latest['p50']}ms, p90: {latest['p90']}ms, p99: {latest['p99']}ms."
        })

    return insights
