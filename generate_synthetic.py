"""
generate_synthetic.py — Generate synthetic merchants + transactions CSVs.

Reads schema.yaml as the single source of truth for column names and allowed values.
Produces data/synthetic/merchants.csv and data/synthetic/transactions.csv.

Usage:
    python generate_synthetic.py

Output logging: row counts, null percentages, duplicate counts — never data values.
"""

import os
import random
import string
import hashlib
import logging
from pathlib import Path

import numpy as np
import pandas as pd
import yaml

# ---------------------------------------------------------------------------
# Config — generation parameters (the ONLY place dates/counts are set)
# ---------------------------------------------------------------------------
SEED = 42
NUM_MERCHANTS = 400
NUM_TRANSACTIONS = 60_000  # before duplicates
NUM_DUPLICATE_TXNS = 180   # webhook retries

# Incident parameters (generation-only; the pipeline must detect this blindly)
INCIDENT_DATE = "2026-03-14"
INCIDENT_HOUR_START = 14
INCIDENT_HOUR_END = 20  # exclusive: 14:00–19:59

# Date range for transactions
TXN_DATE_START = "2025-11-01"
TXN_DATE_END = "2026-10-31"

# Merchant onboarding range
ONBOARD_START = "2019-06-01"
ONBOARD_END = "2025-09-30"

# Deliberate mess injection rates
RATE_ODD_CASING = 0.03           # 3% of categoricals get odd casing
RATE_EXTRA_WHITESPACE = 0.02     # 2% of strings get extra whitespace
NUM_BAD_AMOUNTS = 15             # negative or zero amounts
RATE_MIXED_DATE_FORMAT = 0.02    # 2% of created_at get DD-MM-YYYY format

OUTPUT_DIR = Path("data/synthetic")

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("synthetic")

# ---------------------------------------------------------------------------
# Load schema.yaml
# ---------------------------------------------------------------------------
def load_schema(path: str = "schema.yaml") -> dict:
    """Load schema.yaml — single source of truth for columns and allowed values."""
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def get_allowed(schema: dict, table: str, column: str) -> list:
    """Extract allowed_values list from schema for a table.column."""
    col_def = schema[table]["columns"][column]
    return col_def.get("allowed_values", [])


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def make_merchant_id(i: int) -> str:
    return f"MID_{i:05d}"


def make_txn_id(rng: np.random.Generator) -> str:
    """Generate a pay_XXXXXXXX transaction ID."""
    chars = string.ascii_letters + string.digits
    suffix = "".join(rng.choice(list(chars)) for _ in range(10))
    return f"pay_{suffix}"


def fake_business_name(i: int, rng: np.random.Generator) -> str:
    """Generate a unique fictional business name."""
    prefixes = [
        "Nova", "Zen", "Pixel", "Flux", "Aura", "Bolt", "Crest", "Dune",
        "Echo", "Fern", "Glow", "Hive", "Iris", "Jade", "Kite", "Luna",
        "Mint", "Nest", "Opal", "Peak", "Quad", "Reef", "Sage", "Tide",
        "Ursa", "Vibe", "Wave", "Xeno", "York", "Zara", "Apex", "Bliss",
        "Core", "Dash", "Edge", "Finn", "Grid", "Halo", "Icon", "Jazz",
    ]
    suffixes = [
        "Tech", "Labs", "Co", "Hub", "Works", "Digital", "Solutions",
        "Systems", "Pay", "Store", "Mart", "Global", "India", "Net",
        "Cloud", "App", "Plus", "One", "Pro", "Group",
    ]
    prefix = prefixes[i % len(prefixes)]
    suffix = suffixes[(i * 7 + 3) % len(suffixes)]
    # Add number to guarantee uniqueness
    return f"{prefix}{suffix} {i + 1}"


# ---------------------------------------------------------------------------
# City -> State mapping
# ---------------------------------------------------------------------------
CITY_STATE_MAP = {
    "Mumbai": "Maharashtra",
    "Delhi": "Delhi",
    "Bangalore": "Karnataka",
    "Hyderabad": "Telangana",
    "Chennai": "Tamil Nadu",
    "Kolkata": "West Bengal",
    "Pune": "Maharashtra",
    "Ahmedabad": "Gujarat",
    "Jaipur": "Rajasthan",
    "Lucknow": "Uttar Pradesh",
    "Chandigarh": "Chandigarh",
    "Kochi": "Kerala",
    "Indore": "Madhya Pradesh",
    "Guwahati": "Assam",
}
CITIES = list(CITY_STATE_MAP.keys())

# ---------------------------------------------------------------------------
# Bank lists
# ---------------------------------------------------------------------------
ISSUING_BANKS = [
    "HDFC Bank", "ICICI Bank", "SBI", "Axis Bank", "Kotak Mahindra",
    "Yes Bank", "PNB", "Bank of Baroda", "IndusInd Bank", "RBL Bank",
    "Federal Bank", "IDFC First", "Union Bank", "Canara Bank", "BOI",
]

# ---------------------------------------------------------------------------
# Generate merchants
# ---------------------------------------------------------------------------
def generate_merchants(schema: dict, rng: np.random.Generator) -> pd.DataFrame:
    """Generate merchants.csv with realistic distributions."""
    log.info("Generating merchants (target: %d rows)...", NUM_MERCHANTS)

    categories = get_allowed(schema, "merchants", "category")
    tiers = get_allowed(schema, "merchants", "tier")
    kyc_statuses = get_allowed(schema, "merchants", "kyc_status")
    risk_ratings = get_allowed(schema, "merchants", "risk_rating")

    # Tier distribution: Starter ~62%, Growth ~31%, Enterprise ~7%
    tier_weights = [0.62, 0.31, 0.07]

    # KYC: Verified ~90%, Pending ~7%, Rejected ~3%
    kyc_weights = [0.90, 0.07, 0.03]

    # Risk: Low ~70%, Medium ~22%, High ~8%
    risk_weights = [0.70, 0.22, 0.08]

    rows = []
    for i in range(NUM_MERCHANTS):
        mid = make_merchant_id(i + 1)
        name = fake_business_name(i, rng)
        category = rng.choice(categories)
        tier = rng.choice(tiers, p=tier_weights)

        # City: ~3% null
        if rng.random() < 0.03:
            city = None
            state = None
        else:
            city = rng.choice(CITIES)
            state = CITY_STATE_MAP[city]

        # Onboarding date: uniform within range
        start_ts = pd.Timestamp(ONBOARD_START).timestamp()
        end_ts = pd.Timestamp(ONBOARD_END).timestamp()
        onboard_ts = rng.uniform(start_ts, end_ts)
        onboarding_date = pd.Timestamp(onboard_ts, unit="s").strftime("%Y-%m-%d")

        kyc_status = rng.choice(kyc_statuses, p=kyc_weights)
        risk_rating = rng.choice(risk_ratings, p=risk_weights)

        # International: more likely for higher tiers
        intl_prob = {"Starter": 0.05, "Growth": 0.15, "Enterprise": 0.40}
        is_international_enabled = bool(rng.random() < intl_prob[tier])

        rows.append({
            "merchant_id": mid,
            "business_name": name,
            "category": category,
            "city": city,
            "state": state,
            "tier": tier,
            "onboarding_date": onboarding_date,
            "kyc_status": kyc_status,
            "risk_rating": risk_rating,
            "is_international_enabled": is_international_enabled,
        })

    df = pd.DataFrame(rows)

    # Inject odd casing in category (~3% of rows)
    mess_mask = rng.random(len(df)) < RATE_ODD_CASING
    for idx in df.index[mess_mask]:
        original = df.at[idx, "category"]
        variant = rng.choice(["lower", "upper", "whitespace"])
        if variant == "lower":
            df.at[idx, "category"] = original.lower()
        elif variant == "upper":
            df.at[idx, "category"] = original.upper()
        else:
            df.at[idx, "category"] = f"  {original}  "

    # Inject extra whitespace in some business names
    ws_mask = rng.random(len(df)) < RATE_EXTRA_WHITESPACE
    for idx in df.index[ws_mask]:
        df.at[idx, "business_name"] = f"  {df.at[idx, 'business_name']} "

    log.info("Merchants generated: %d rows", len(df))
    _log_null_pcts(df, "merchants")
    return df


# ---------------------------------------------------------------------------
# Generate transactions
# ---------------------------------------------------------------------------
def generate_transactions(
    schema: dict,
    merchants_df: pd.DataFrame,
    rng: np.random.Generator,
) -> pd.DataFrame:
    """Generate transactions.csv with realistic distributions and deliberate mess."""
    log.info("Generating transactions (target: ~%d rows before duplicates)...", NUM_TRANSACTIONS)

    payment_methods = get_allowed(schema, "transactions", "payment_method")
    card_networks = get_allowed(schema, "transactions", "card_network")
    statuses = get_allowed(schema, "transactions", "status")
    failure_reasons = get_allowed(schema, "transactions", "failure_reason")
    device_types = get_allowed(schema, "transactions", "device_type")

    # --- Merchant volume distribution: heavy-tailed ---
    # Enterprise merchants (~7%) get ~50% of volume
    # Growth (~31%) get ~35%, Starter (~62%) get ~15%
    merchant_ids = merchants_df["merchant_id"].values
    merchant_tiers = merchants_df.set_index("merchant_id")["tier"].to_dict()
    merchant_categories = merchants_df.set_index("merchant_id")["category"].to_dict()
    merchant_intl = merchants_df.set_index("merchant_id")["is_international_enabled"].to_dict()

    # Assign base weights by tier
    weights = []
    for mid in merchant_ids:
        tier = merchant_tiers[mid]
        if tier == "Enterprise":
            weights.append(rng.lognormal(4.0, 0.5))
        elif tier == "Growth":
            weights.append(rng.lognormal(2.5, 0.5))
        else:
            weights.append(rng.lognormal(1.0, 0.8))
    weights = np.array(weights)
    weights /= weights.sum()

    # Draw merchant for each transaction
    txn_merchant_ids = rng.choice(merchant_ids, size=NUM_TRANSACTIONS, p=weights)

    # --- Timestamps with time patterns ---
    start_dt = pd.Timestamp(TXN_DATE_START)
    end_dt = pd.Timestamp(TXN_DATE_END) + pd.Timedelta(hours=23, minutes=59, seconds=59)
    total_days = (end_dt - start_dt).days + 1

    # Generate dates with growth trend and festive uplift
    timestamps = _generate_timestamps(rng, start_dt, total_days, NUM_TRANSACTIONS)

    # --- Payment method mix ---
    # UPI ~54%, Card ~28%, Netbanking ~8%, EMI ~4%, Wallet ~4%, BNPL ~2%
    pm_weights = [0.54, 0.28, 0.08, 0.04, 0.04, 0.02]
    txn_payment_methods = rng.choice(payment_methods, size=NUM_TRANSACTIONS, p=pm_weights)

    # --- Build rows ---
    rows = []
    for i in range(NUM_TRANSACTIONS):
        mid = txn_merchant_ids[i]
        ts = timestamps[i]
        pm = txn_payment_methods[i]
        cat = merchant_categories.get(mid, "E-commerce")

        # Amount: lognormal by category
        amount = _amount_for_category(cat, rng)

        # Card network (null for non-Card)
        if pm == "Card":
            card_net = rng.choice(card_networks, p=[0.40, 0.30, 0.20, 0.10])
        else:
            card_net = None

        # Issuing bank (~5% null overall; always null for Wallet/BNPL)
        if pm in ("Wallet", "BNPL"):
            bank = None
        elif rng.random() < 0.03:
            bank = None
        else:
            bank = rng.choice(ISSUING_BANKS)

        # Status: captured ~89%, failed ~7.5%, refunded ~2.5%, partially_refunded ~1%
        status_weights = [0.89, 0.075, 0.025, 0.01]
        # Adjust for Netbanking (higher failure rate)
        if pm == "Netbanking":
            status_weights = [0.82, 0.13, 0.035, 0.015]
        # Adjust for Yes Bank / PNB (higher failure)
        if bank in ("Yes Bank", "PNB"):
            status_weights = [0.82, 0.13, 0.035, 0.015]

        status = rng.choice(statuses, p=status_weights)

        # Failure reason
        if status == "failed":
            fail_reason = rng.choice(failure_reasons)
        else:
            fail_reason = None

        # Refund amount
        if status == "refunded":
            refund_amt = round(amount, 2)
        elif status == "partially_refunded":
            refund_amt = round(amount * rng.uniform(0.1, 0.9), 2)
        else:
            refund_amt = 0.0

        # International
        is_intl = False
        if pm == "Card" and merchant_intl.get(mid, False):
            is_intl = bool(rng.random() < 0.08)

        # MDR rate by method/tier
        mdr = _mdr_rate(pm, merchant_tiers.get(mid, "Starter"), is_intl, rng)

        # Fee (only on successful statuses)
        is_success = status in ("captured", "refunded", "partially_refunded")
        fee = round(amount * mdr, 2) if is_success else 0.0
        gst = round(fee * 0.18, 2)

        # Device type
        device = rng.choice(device_types, p=[0.38, 0.22, 0.25, 0.15])

        # Customer city (~4% null)
        if rng.random() < 0.04:
            cust_city = None
        else:
            cust_city = rng.choice(CITIES)

        # Latency: lognormal, 150-15000 typical
        latency = float(rng.lognormal(5.5, 0.6))
        latency = max(80.0, min(latency, 15000.0))

        # Retry count (>0 only for failed)
        retry = int(rng.integers(1, 4)) if status == "failed" else 0

        txn_id = make_txn_id(rng)

        rows.append({
            "txn_id": txn_id,
            "merchant_id": mid,
            "created_at": ts,
            "amount_inr": round(amount, 2),
            "payment_method": pm,
            "card_network": card_net,
            "issuing_bank": bank,
            "status": status,
            "failure_reason": fail_reason,
            "refund_amount_inr": refund_amt,
            "is_international": is_intl,
            "mdr_rate": round(mdr, 5),
            "fee_inr": fee,
            "gst_on_fee_inr": gst,
            "device_type": device,
            "customer_city": cust_city,
            "api_latency_ms": round(latency, 1),
            "retry_count": retry,
        })

    df = pd.DataFrame(rows)

    # --- Plant the incident: 2026-03-14 14:00-20:00 ---
    df = _plant_incident(df, rng, failure_reasons)

    # --- Inject duplicates (webhook retries) ---
    df = _inject_duplicates(df, rng)

    # --- Inject deliberate mess ---
    df = _inject_mess(df, rng)

    # --- Refund rate adjustments: higher for E-commerce, Retail & D2C, Travel ---
    # Already partially handled by category-level adjustments in status assignment,
    # but let's boost refund rates for specific categories
    df = _boost_refunds_for_categories(df, merchants_df, rng)

    # Sort by created_at
    df = df.sort_values("created_at").reset_index(drop=True)

    log.info("Transactions generated: %d rows (including %d duplicates)", len(df), NUM_DUPLICATE_TXNS)
    _log_null_pcts(df, "transactions")
    _log_duplicate_count(df)

    return df


def _generate_timestamps(
    rng: np.random.Generator,
    start_dt: pd.Timestamp,
    total_days: int,
    n: int,
) -> list:
    """Generate timestamps with weekday/weekend patterns, evening peaks, growth, festive uplift."""
    timestamps = []
    for _ in range(n):
        # Day: weighted by growth trend + day-of-week + festive
        day_offset = _pick_day(rng, start_dt, total_days)
        dt = start_dt + pd.Timedelta(days=int(day_offset))

        # Hour: evening peak (18-22), moderate midday, low overnight
        hour = _pick_hour(rng)
        minute = int(rng.integers(0, 60))
        second = int(rng.integers(0, 60))

        ts = dt.replace(hour=hour, minute=minute, second=second)
        timestamps.append(ts.strftime("%Y-%m-%d %H:%M:%S"))

    return timestamps


def _pick_day(rng: np.random.Generator, start_dt: pd.Timestamp, total_days: int) -> int:
    """Pick a day offset with growth trend, weekday bias, and festive uplift."""
    day = int(rng.integers(0, total_days))
    dt = start_dt + pd.Timedelta(days=day)

    # Growth trend: later days more likely (linear ramp from 0.7 to 1.3)
    growth_weight = 0.7 + 0.6 * (day / total_days)

    # Weekday vs weekend: weekday ~1.2x, weekend ~0.7x
    dow = dt.dayofweek
    dow_weight = 1.2 if dow < 5 else 0.7

    # Festive uplift: October 2026 and early November 2025
    month = dt.month
    year = dt.year
    festive_weight = 1.0
    if (year == 2026 and month == 10):
        festive_weight = 1.5
    elif (year == 2025 and month == 11 and dt.day <= 15):
        festive_weight = 1.3

    # Accept-reject sampling
    weight = growth_weight * dow_weight * festive_weight
    if rng.random() < weight / (1.3 * 1.2 * 1.5):
        return day
    else:
        # Retry with simple uniform fallback
        return int(rng.integers(0, total_days))


def _pick_hour(rng: np.random.Generator) -> int:
    """Pick hour with evening peak pattern."""
    # Hour weights: low overnight, moderate midday, peak evening
    hour_weights = np.array([
        0.3, 0.2, 0.1, 0.1, 0.1, 0.2,   # 00-05: very low
        0.4, 0.6, 0.8, 1.0, 1.1, 1.2,   # 06-11: ramp up
        1.3, 1.2, 1.1, 1.0, 1.1, 1.3,   # 12-17: midday plateau
        1.6, 1.8, 2.0, 1.8, 1.5, 1.0,   # 18-23: evening peak
    ])
    hour_weights /= hour_weights.sum()
    return int(rng.choice(24, p=hour_weights))


def _amount_for_category(category: str, rng: np.random.Generator) -> float:
    """Lognormal amount with category-specific parameters."""
    # (mean_log, std_log) — higher for Travel/E-commerce, lower for Utilities
    params = {
        "Travel":            (8.0, 1.2),
        "E-commerce":        (7.0, 1.0),
        "Retail & D2C":      (6.5, 0.9),
        "SaaS":              (7.5, 0.8),
        "Fintech":           (7.0, 1.1),
        "Healthcare":        (7.0, 0.9),
        "Education":         (6.5, 1.0),
        "Gaming":            (5.5, 1.0),
        "Food & Delivery":   (5.8, 0.7),
        "Utilities & Bills": (5.5, 0.6),
        "Nonprofit":         (6.0, 1.0),
    }
    # Normalize category for lookup (strip, title case) — handle messy input
    cat_clean = category.strip().title()
    # Find match or use default
    mu, sigma = params.get(category, params.get(cat_clean, (6.5, 1.0)))
    amount = float(rng.lognormal(mu, sigma))
    # Clip to realistic range
    return max(10.0, min(amount, 190000.0))


def _mdr_rate(
    payment_method: str, tier: str, is_intl: bool, rng: np.random.Generator
) -> float:
    """MDR rate by payment method, tier, and international flag."""
    base_rates = {
        "UPI":        0.003,
        "Card":       0.018,
        "Netbanking": 0.015,
        "EMI":        0.020,
        "Wallet":     0.012,
        "BNPL":       0.025,
    }
    tier_multiplier = {"Enterprise": 0.8, "Growth": 1.0, "Starter": 1.2}
    base = base_rates.get(payment_method, 0.018)
    rate = base * tier_multiplier.get(tier, 1.0)

    # International cards get higher MDR
    if is_intl:
        rate *= 1.8

    # Add noise
    rate *= rng.uniform(0.85, 1.15)
    return max(0.001, min(rate, 0.08))


def _plant_incident(
    df: pd.DataFrame, rng: np.random.Generator, failure_reasons: list
) -> pd.DataFrame:
    """Plant a failure-rate spike incident on the configured date/hours."""
    log.info("Planting incident on %s, hours %d-%d...", INCIDENT_DATE, INCIDENT_HOUR_START, INCIDENT_HOUR_END)

    # Parse timestamps to identify incident window
    created = pd.to_datetime(df["created_at"])
    incident_mask = (
        (created.dt.strftime("%Y-%m-%d") == INCIDENT_DATE)
        & (created.dt.hour >= INCIDENT_HOUR_START)
        & (created.dt.hour < INCIDENT_HOUR_END)
    )

    incident_count = incident_mask.sum()
    log.info("Transactions in incident window: %d", incident_count)

    if incident_count == 0:
        log.warning("No transactions found in incident window — skipping incident planting")
        return df

    # For transactions in the incident window:
    # 1. Double the failure rate (flip ~40% of captured to failed)
    # 2. Double the latency
    # 3. Yes Bank / PNB get even more failures
    for idx in df.index[incident_mask]:
        # Double latency
        df.at[idx, "api_latency_ms"] = round(df.at[idx, "api_latency_ms"] * 2.0, 1)

        # Flip some successful transactions to failed
        if df.at[idx, "status"] in ("captured", "refunded", "partially_refunded"):
            flip_prob = 0.40
            # Yes Bank / PNB get extra failure boost
            if df.at[idx, "issuing_bank"] in ("Yes Bank", "PNB"):
                flip_prob = 0.65

            if rng.random() < flip_prob:
                df.at[idx, "status"] = "failed"
                df.at[idx, "failure_reason"] = "bank_server_down"
                df.at[idx, "fee_inr"] = 0.0
                df.at[idx, "gst_on_fee_inr"] = 0.0
                df.at[idx, "refund_amount_inr"] = 0.0
                df.at[idx, "retry_count"] = int(rng.integers(1, 5))

    affected = incident_mask.sum()
    new_failures = ((df.loc[incident_mask, "status"] == "failed").sum())
    log.info("Incident planted: %d txns in window, %d now failed", affected, new_failures)
    return df


def _inject_duplicates(df: pd.DataFrame, rng: np.random.Generator) -> pd.DataFrame:
    """Inject ~180 duplicate rows (webhook retries) by duplicating random rows."""
    log.info("Injecting %d duplicate txn_id rows (webhook retries)...", NUM_DUPLICATE_TXNS)
    dup_indices = rng.choice(df.index, size=NUM_DUPLICATE_TXNS, replace=False)
    duplicates = df.loc[dup_indices].copy()
    # Shift timestamps slightly (1-30 seconds later) to simulate retry
    for idx in duplicates.index:
        orig_ts = pd.Timestamp(duplicates.at[idx, "created_at"])
        retry_ts = orig_ts + pd.Timedelta(seconds=int(rng.integers(1, 31)))
        duplicates.at[idx, "created_at"] = retry_ts.strftime("%Y-%m-%d %H:%M:%S")
    df = pd.concat([df, duplicates], ignore_index=True)
    return df


def _inject_mess(df: pd.DataFrame, rng: np.random.Generator) -> pd.DataFrame:
    """Inject deliberate data quality issues."""
    n = len(df)

    # 1. Odd casing in payment_method (~3%)
    casing_mask = rng.random(n) < RATE_ODD_CASING
    for idx in df.index[casing_mask]:
        original = df.at[idx, "payment_method"]
        variant = rng.choice(["lower", "upper", "whitespace"])
        if variant == "lower":
            df.at[idx, "payment_method"] = original.lower()
        elif variant == "upper":
            df.at[idx, "payment_method"] = original.upper()
        else:
            df.at[idx, "payment_method"] = f" {original} "
    log.info("Odd casing injected in payment_method: %d rows", casing_mask.sum())

    # 2. Odd casing in status (~2%)
    status_mess_mask = rng.random(n) < 0.02
    for idx in df.index[status_mess_mask]:
        original = df.at[idx, "status"]
        df.at[idx, "status"] = f"  {original.upper()}  " if rng.random() < 0.5 else original.title()
    log.info("Odd casing injected in status: %d rows", status_mess_mask.sum())

    # 3. Bad amounts (negative/zero) — small count
    bad_amt_indices = rng.choice(df.index, size=min(NUM_BAD_AMOUNTS, n), replace=False)
    for i, idx in enumerate(bad_amt_indices):
        if i < NUM_BAD_AMOUNTS // 2:
            df.at[idx, "amount_inr"] = round(float(rng.uniform(-500, -1)), 2)
        else:
            df.at[idx, "amount_inr"] = 0.0
    log.info("Bad amounts injected: %d rows (negative/zero)", NUM_BAD_AMOUNTS)

    # 4. Mixed date formats (~2%)
    date_mess_mask = rng.random(n) < RATE_MIXED_DATE_FORMAT
    for idx in df.index[date_mess_mask]:
        try:
            ts = pd.Timestamp(df.at[idx, "created_at"])
            # Switch to DD-MM-YYYY HH:MM:SS format
            df.at[idx, "created_at"] = ts.strftime("%d-%m-%Y %H:%M:%S")
        except Exception:
            pass
    log.info("Mixed date formats injected: %d rows", date_mess_mask.sum())

    # 5. Extra whitespace in device_type (~2%)
    ws_mask = rng.random(n) < RATE_EXTRA_WHITESPACE
    for idx in df.index[ws_mask]:
        df.at[idx, "device_type"] = f"  {df.at[idx, 'device_type']}  "
    log.info("Extra whitespace in device_type: %d rows", ws_mask.sum())

    return df


def _boost_refunds_for_categories(
    df: pd.DataFrame, merchants_df: pd.DataFrame, rng: np.random.Generator
) -> pd.DataFrame:
    """Boost refund rates for E-commerce, Retail & D2C, Travel."""
    mid_to_cat = merchants_df.set_index("merchant_id")["category"].to_dict()

    high_refund_cats = {"E-commerce", "Retail & D2C", "Travel",
                        "e-commerce", "retail & d2c", "travel"}  # handle messy casing

    for idx in df.index:
        cat = mid_to_cat.get(df.at[idx, "merchant_id"], "")
        cat_clean = cat.strip().lower() if cat else ""

        if cat_clean in {c.lower() for c in high_refund_cats}:
            # 5% chance to flip captured -> refunded
            if df.at[idx, "status"] == "captured" and rng.random() < 0.05:
                amt = df.at[idx, "amount_inr"]
                if rng.random() < 0.7:
                    df.at[idx, "status"] = "refunded"
                    df.at[idx, "refund_amount_inr"] = round(abs(amt), 2)
                else:
                    df.at[idx, "status"] = "partially_refunded"
                    df.at[idx, "refund_amount_inr"] = round(abs(amt) * rng.uniform(0.1, 0.9), 2)

    return df


# ---------------------------------------------------------------------------
# Logging helpers (metadata only — no data values!)
# ---------------------------------------------------------------------------
def _log_null_pcts(df: pd.DataFrame, table_name: str) -> None:
    """Log null percentage per column — metadata only."""
    null_pcts = (df.isnull().sum() / len(df) * 100).round(2)
    cols_with_nulls = null_pcts[null_pcts > 0]
    if len(cols_with_nulls) > 0:
        log.info("[%s] Null percentages:", table_name)
        for col, pct in cols_with_nulls.items():
            log.info("  %-25s %6.2f%%", col, pct)
    else:
        log.info("[%s] No null values found", table_name)


def _log_duplicate_count(df: pd.DataFrame) -> None:
    """Log duplicate txn_id count — metadata only."""
    dup_count = df.duplicated(subset=["txn_id"], keep=False).sum()
    unique_dups = df[df.duplicated(subset=["txn_id"], keep=False)]["txn_id"].nunique()
    log.info("Duplicate txn_id rows: %d total (%d unique IDs with duplicates)", dup_count, unique_dups)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main():
    log.info("=" * 60)
    log.info("Synthetic Data Generator")
    log.info("Seed: %d", SEED)
    log.info("=" * 60)

    rng = np.random.default_rng(SEED)
    random.seed(SEED)

    schema = load_schema("schema.yaml")
    log.info("Schema loaded: merchants (%d columns), transactions (%d columns)",
             len(schema["merchants"]["columns"]),
             len(schema["transactions"]["columns"]))

    # Create output directory
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    log.info("Output directory: %s", OUTPUT_DIR.resolve())

    # Generate merchants
    merchants_df = generate_merchants(schema, rng)
    merchants_path = OUTPUT_DIR / "merchants.csv"
    merchants_df.to_csv(merchants_path, index=False)
    log.info("Saved: %s (%d rows, %d columns)", merchants_path, len(merchants_df), len(merchants_df.columns))

    # Generate transactions
    txn_df = generate_transactions(schema, merchants_df, rng)
    txn_path = OUTPUT_DIR / "transactions.csv"
    txn_df.to_csv(txn_path, index=False)
    log.info("Saved: %s (%d rows, %d columns)", txn_path, len(txn_df), len(txn_df.columns))

    # Final summary
    log.info("=" * 60)
    log.info("GENERATION COMPLETE")
    log.info("  merchants.csv:    %d rows × %d columns", len(merchants_df), len(merchants_df.columns))
    log.info("  transactions.csv: %d rows × %d columns", len(txn_df), len(txn_df.columns))
    log.info("  Output dir:       %s", OUTPUT_DIR.resolve())

    # Verify FK integrity
    txn_mids = set(txn_df["merchant_id"].unique())
    merch_mids = set(merchants_df["merchant_id"].unique())
    orphans = txn_mids - merch_mids
    if orphans:
        log.error("FK VIOLATION: %d transaction merchant_ids not in merchants table!", len(orphans))
    else:
        log.info("  FK integrity:     OK (all transaction merchant_ids exist in merchants)")

    log.info("=" * 60)


if __name__ == "__main__":
    main()
