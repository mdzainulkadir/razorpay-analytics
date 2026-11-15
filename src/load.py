"""
src/load.py — Load CSV datasets from data_path with encoding fallback and metadata logging.
Hard rule: No data values in logs or errors. Log only row counts, column names, dtypes, null percentages.
"""

import logging
from pathlib import Path
import pandas as pd
import yaml

log = logging.getLogger("pipeline.load")


def load_config(config_path: str = "config.yaml") -> dict:
    """Load configuration from YAML file."""
    path = Path(config_path)
    if not path.exists():
        raise FileNotFoundError(f"Config file not found: {config_path}")
    with open(path, "r", encoding="utf-8") as f:
        config = yaml.safe_load(f)
    log.info("Loaded configuration from %s", config_path)
    return config


def load_datasets(config: dict) -> tuple[pd.DataFrame, pd.DataFrame]:
    """
    Load merchants.csv and transactions.csv from data_path specified in config.
    Handles encoding fallbacks (utf-8, utf-8-sig, latin1).
    Returns (merchants_df, transactions_df).
    """
    data_dir = Path(config["data"]["data_path"])
    merchants_file = data_dir / config["data"]["merchants_filename"]
    txn_file = data_dir / config["data"]["transactions_filename"]

    if not merchants_file.exists():
        raise FileNotFoundError(f"Merchants file not found: {merchants_file}")
    if not txn_file.exists():
        raise FileNotFoundError(f"Transactions file not found: {txn_file}")

    merchants_df = _read_csv_robust(merchants_file, "merchants")
    txn_df = _read_csv_robust(txn_file, "transactions")

    return merchants_df, txn_df


def _read_csv_robust(file_path: Path, table_name: str) -> pd.DataFrame:
    """Read CSV trying multiple encodings (utf-8, utf-8-sig, latin1)."""
    encodings = ["utf-8", "utf-8-sig", "latin1"]
    df = None
    used_encoding = None

    for enc in encodings:
        try:
            df = pd.read_csv(file_path, encoding=enc, low_memory=False)
            used_encoding = enc
            break
        except UnicodeDecodeError:
            continue
        except Exception as e:
            log.warning("Error reading %s with encoding %s: %s", file_path, enc, type(e).__name__)
            continue

    if df is None:
        raise RuntimeError(f"Failed to read {file_path} with any supported encoding.")

    log.info(
        "Loaded table '%s' from %s: %d rows, %d columns (encoding: %s)",
        table_name,
        file_path.name,
        len(df),
        len(df.columns),
        used_encoding,
    )

    # Log column metadata (dtypes and null counts — NO data values)
    for col in df.columns:
        null_count = df[col].isnull().sum()
        null_pct = (null_count / len(df)) * 100 if len(df) > 0 else 0.0
        log.info("  column: %-25s dtype: %-10s nulls: %6.2f%%", col, str(df[col].dtype), null_pct)

    return df
