"""
tests/test_pipeline.py — Pytest test suite for validation, cleaning, analytics, and export privacy.
"""

import sys
from pathlib import Path
import pytest
import pandas as pd
import numpy as np

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.load import load_config
from src.validate import validate_schemas, SchemaValidationError
from src.clean import clean_data
from src.analyze import compute_all_analyses
from src.export import verify_privacy_compliance


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

    # Verify error message contains metadata only, NO data values
    err_msg = str(exc_info.value)
    assert "amount_inr" in err_msg or "missing" in err_msg.lower()


def test_clean_data_dedup_and_dates():
    config = load_config("config.yaml")
    merchants_df = pd.read_csv("data/synthetic/merchants.csv")
    txn_df = pd.read_csv("data/synthetic/transactions.csv")

    m_clean, t_clean = clean_data(merchants_df, txn_df, config)
    assert len(m_clean) == len(merchants_df)
    assert len(t_clean) < len(txn_df)  # due to dupes & invalid amounts dropped
    assert pd.api.types.is_datetime64_any_dtype(t_clean["created_at"])


def test_analytics_computation():
    config = load_config("config.yaml")
    merchants_df = pd.read_csv("data/synthetic/merchants.csv")
    txn_df = pd.read_csv("data/synthetic/transactions.csv")
    m_clean, t_clean = clean_data(merchants_df, txn_df, config)

    results = compute_all_analyses(m_clean, t_clean, config)
    assert "kpis" in results
    assert "daily_trend" in results
    assert "payment_mix" in results
    assert "incidents" in results
    assert "insights" in results


def test_export_privacy_compliance():
    config = load_config("config.yaml")
    output_dir = Path(config["outputs"]["dashboard_data_dir"])
    min_group_size = config.get("analysis", {}).get("min_group_size", 10)
    assert verify_privacy_compliance(output_dir, min_group_size) is True
