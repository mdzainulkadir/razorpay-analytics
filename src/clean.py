"""
src/clean.py — Clean datasets: deduplicate, parse dates, standardize categoricals, filter edge periods and invalid amounts.
"""

import logging
import pandas as pd
import numpy as np

log = logging.getLogger("pipeline.clean")


def clean_data(merchants_df: pd.DataFrame, txn_df: pd.DataFrame, config: dict) -> tuple[pd.DataFrame, pd.DataFrame, dict]:
    """
    Clean merchants and transactions DataFrames.
    - Merchants: trim strings, standardize category/tier casing.
    - Transactions: deduplicate txn_id, parse dates robustly, standardize categoricals,
      detect & remove implausible edge periods (volume < threshold of median monthly volume),
      filter out invalid amounts, add derived columns.
    """
    log.info("Starting data cleaning...")

    m_clean = _clean_merchants(merchants_df)
    t_clean, edge_stats = _clean_transactions(txn_df, config)

    log.info("Cleaning complete. Merchants: %d rows, Transactions: %d rows", len(m_clean), len(t_clean))
    return m_clean, t_clean, edge_stats


def _clean_merchants(df: pd.DataFrame) -> pd.DataFrame:
    """Clean merchants DataFrame."""
    df = df.copy()

    str_cols = df.select_dtypes(include=["object", "string"]).columns
    for col in str_cols:
        df[col] = df[col].astype(str).str.strip()
        df[col] = df[col].replace({"nan": None, "None": None, "": None})

    if "category" in df.columns:
        df["category"] = df["category"].str.title()
    if "tier" in df.columns:
        df["tier"] = df["tier"].str.title()
    if "kyc_status" in df.columns:
        df["kyc_status"] = df["kyc_status"].str.title()
    if "risk_rating" in df.columns:
        df["risk_rating"] = df["risk_rating"].str.title()

    if "onboarding_date" in df.columns:
        df["onboarding_date"] = pd.to_datetime(df["onboarding_date"], errors="coerce")

    log.info("Cleaned merchants table: %d rows", len(df))
    return df


def _clean_transactions(df: pd.DataFrame, config: dict) -> tuple[pd.DataFrame, dict]:
    """Clean transactions DataFrame and filter implausible edge periods."""
    df = df.copy()
    initial_count = len(df)

    # 1. Deduplicate txn_id
    dedup_subset = config.get("cleaning", {}).get("dedup_subset", ["txn_id"])
    dedup_keep = config.get("cleaning", {}).get("dedup_keep", "first")

    if "txn_id" in df.columns:
        df["txn_id"] = df["txn_id"].astype(str).str.strip()
        dupes_mask = df.duplicated(subset=dedup_subset, keep=False)
        dupe_count = int(dupes_mask.sum())
        if dupe_count > 0:
            log.info("Found %d duplicate rows by txn_id (webhook retries). Keeping '%s'.", dupe_count, dedup_keep)
            df = df.drop_duplicates(subset=dedup_subset, keep=dedup_keep).reset_index(drop=True)

    # 2. Trim string columns
    str_cols = df.select_dtypes(include=["object"]).columns
    for col in str_cols:
        df[col] = df[col].astype(str).str.strip()
        df[col] = df[col].replace({"nan": None, "None": None, "": None})

    # 3. Robust date parsing
    if "created_at" in df.columns:
        df["created_at"] = _parse_mixed_dates(df["created_at"])

    # Drop rows with unparseable dates
    df = df.dropna(subset=["created_at"]).reset_index(drop=True)

    # 4. Standardize categoricals
    if "status" in df.columns:
        df["status"] = df["status"].str.lower().str.strip()
    if "payment_method" in df.columns:
        df["payment_method"] = df["payment_method"].str.title().str.strip()
    if "device_type" in df.columns:
        df["device_type"] = df["device_type"].str.strip()
    if "card_network" in df.columns:
        df["card_network"] = df["card_network"].str.title().str.strip()
    if "issuing_bank" in df.columns:
        df["issuing_bank"] = df["issuing_bank"].str.strip()
    if "failure_reason" in df.columns:
        df["failure_reason"] = df["failure_reason"].str.lower().str.strip()

    # 5. Filter out invalid amounts
    min_amt = config.get("cleaning", {}).get("min_amount_inr", 1.0)
    max_amt = config.get("cleaning", {}).get("max_amount_inr", 500000.0)

    if "amount_inr" in df.columns:
        df["amount_inr"] = pd.to_numeric(df["amount_inr"], errors="coerce")
        valid_amt_mask = (df["amount_inr"] >= min_amt) & (df["amount_inr"] <= max_amt)
        invalid_amt_count = int((~valid_amt_mask).sum())
        if invalid_amt_count > 0:
            log.warning("Dropping %d transactions with invalid amount_inr (outside [%.1f, %.1f])", invalid_amt_count, min_amt, max_amt)
            df = df[valid_amt_mask].reset_index(drop=True)

    # 6. Data-driven edge period detection & filtering
    # Detect leading/trailing months whose volume is below threshold (default 2%) of median monthly volume. Never drop interior months.
    edge_fraction = config.get("cleaning", {}).get("edge_volume_fraction_threshold", 0.02)
    df["_month_period"] = df["created_at"].dt.to_period("M")
    monthly_counts = df.groupby("_month_period").size()

    edge_stats = {
        "excluded_edge_rows": 0,
        "detected_window_start": None,
        "detected_window_end": None,
    }

    if len(monthly_counts) > 0:
        median_vol = monthly_counts.median()
        threshold = median_vol * edge_fraction

        periods = monthly_counts.index.sort_values()
        start_idx = 0
        end_idx = len(periods) - 1

        # Scan leading edge (forward)
        while start_idx <= end_idx and monthly_counts.iloc[start_idx] < threshold:
            start_idx += 1

        # Scan trailing edge (backward)
        while end_idx >= start_idx and monthly_counts.iloc[end_idx] < threshold:
            end_idx -= 1

        if start_idx <= end_idx:
            valid_periods = periods[start_idx : end_idx + 1]
            start_p = valid_periods[0]
            end_p = valid_periods[-1]

            edge_stats["detected_window_start"] = str(start_p.start_time.date())
            edge_stats["detected_window_end"] = str(end_p.end_time.date())

            mask_in_window = df["_month_period"].isin(valid_periods)
            excluded_count = int((~mask_in_window).sum())
            if excluded_count > 0:
                log.info("Dropping %d implausible edge period transactions outside window [%s, %s]", excluded_count, edge_stats["detected_window_start"], edge_stats["detected_window_end"])
                df = df[mask_in_window].reset_index(drop=True)
            edge_stats["excluded_edge_rows"] = excluded_count

    df = df.drop(columns=["_month_period"])

    # 7. Add derived columns
    success_statuses = {"captured", "refunded", "partially_refunded"}
    df["is_success"] = df["status"].isin(success_statuses)

    if "refund_amount_inr" in df.columns:
        df["refund_amount_inr"] = pd.to_numeric(df["refund_amount_inr"], errors="coerce").fillna(0.0)
        df["net_amount_inr"] = df["amount_inr"] - df["refund_amount_inr"]
    else:
        df["refund_amount_inr"] = 0.0
        df["net_amount_inr"] = df["amount_inr"]

    df["date"] = df["created_at"].dt.date.astype(str)
    df["month"] = df["created_at"].dt.to_period("M").astype(str)
    df["hour"] = df["created_at"].dt.hour
    df["day_of_week"] = df["created_at"].dt.day_name()

    log.info("Cleaned transactions table: %d rows (dropped %d invalid/duplicate/edge rows)", len(df), initial_count - len(df))
    return df, edge_stats


def _parse_mixed_dates(series: pd.Series) -> pd.Series:
    """Parse a series containing mixed date formats (e.g. YYYY-MM-DD and DD-MM-YYYY)."""
    parsed = pd.to_datetime(series, errors="coerce", format="mixed")
    unparseable = parsed.isna().sum()
    if unparseable > 0:
        log.warning("Could not parse %d date values; trying dayfirst format", unparseable)
        remaining_mask = parsed.isna()
        if remaining_mask.any():
            parsed2 = pd.to_datetime(series[remaining_mask], errors="coerce", dayfirst=True)
            parsed.update(parsed2)
    return parsed
