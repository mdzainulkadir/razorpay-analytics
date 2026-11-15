"""
tests/test_pipeline.py — Comprehensive pytest test suite for validation, cleaning, reconciliation, privacy, and incident detection.
"""

import sys
from pathlib import Path
import pytest
import pandas as pd
import json

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.load import load_config
from src.validate import validate_schemas, SchemaValidationError
from src.clean import clean_data
from src.export import verify_privacy_compliance
from build_dashboard_data import run_pipeline


def test_config_loading():
    config = load_config("config.yaml")
    assert "data" in config
    assert "outputs" in config
    assert "cleaning" in config
    assert "analysis" in config


def test_schema_validation_success():
    merchants_df = pd.read_csv("data/synthetic/merchants.csv")
    txn_df = pd.read_csv("data/synthetic/transactions.csv")
    assert validate_schemas(merchants_df, txn_df, "schema.yaml") is True


def test_schema_validation_failure_missing_column():
    merchants_df = pd.read_csv("data/synthetic/merchants.csv")
    txn_df = pd.read_csv("data/synthetic/transactions.csv").drop(columns=["amount_inr"])

    with pytest.raises(SchemaValidationError) as exc_info:
        validate_schemas(merchants_df, txn_df, "schema.yaml")

    err_msg = str(exc_info.value)
    assert "amount_inr" in err_msg or "missing" in err_msg.lower()


def test_clean_data_edge_periods_no_interior_drop():
    config = load_config("config.yaml")
    merchants_df = pd.read_csv("data/synthetic/merchants.csv")
    txn_df = pd.read_csv("data/synthetic/transactions.csv")

    _, t_clean, edge_stats = clean_data(merchants_df, txn_df, config)
    assert isinstance(edge_stats, dict)
    assert "excluded_edge_rows" in edge_stats

    # Verify interior months are never dropped (months between start and end window must all be present)
    months_present = t_clean["created_at"].dt.to_period("M").unique()
    if len(months_present) > 0:
        min_p = months_present.min()
        max_p = months_present.max()
        all_expected_periods = pd.period_range(min_p, max_p, freq="M")
        for p in all_expected_periods:
            assert p in months_present


def test_cube_reconciliation_and_totals():
    """Test that marginal cubes reconcile with total cleaned transaction sums."""
    config = load_config("config.yaml")
    t_clean, analysis_results, _ = run_pipeline("config.yaml")

    total_attempts_txn = len(t_clean)
    total_success_txn = int(t_clean["is_success"].sum())
    total_gmv_txn = float(t_clean.loc[t_clean["is_success"], "amount_inr"].sum())

    # Check daily_method_cube reconciliation
    dm_cube = analysis_results.get("daily_method_cube", {})
    if dm_cube and "data" in dm_cube:
        assert sum(dm_cube["data"]["attempts"]) == total_attempts_txn
        assert sum(dm_cube["data"]["successes"]) == total_success_txn
        assert abs(sum(dm_cube["data"]["gmv"]) - total_gmv_txn) < 0.01

    # Check monthly_cube reconciliation
    m_cube = analysis_results.get("monthly_cube", {})
    if m_cube and "data" in m_cube:
        assert sum(m_cube["data"]["attempts"]) == total_attempts_txn
        assert sum(m_cube["data"]["successes"]) == total_success_txn
        assert abs(sum(m_cube["data"]["gmv"]) - total_gmv_txn) < 0.01


def test_incidents_detected_on_synthetic_data():
    """Test that incidents are successfully detected on synthetic data."""
    _, analysis_results, _ = run_pipeline("config.yaml")
    incidents = analysis_results.get("incidents", [])
    assert len(incidents) > 0
    for inc in incidents:
        assert "start_time" in inc
        assert "end_time" in inc
        assert "peak_failure_rate_pct" in inc
        assert "affected_txns" in inc


def test_export_privacy_compliance():
    config = load_config("config.yaml")
    output_dir = Path(config["outputs"]["dashboard_data_dir"])
    min_group_size = config.get("analysis", {}).get("min_group_size", 10)
    assert verify_privacy_compliance(output_dir, min_group_size) is True
