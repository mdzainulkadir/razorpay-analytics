"""
build_dashboard_data.py — Root script to build dashboard JSON data from raw CSVs.
Orchestrates: load -> validate -> clean -> analyze -> export -> verify privacy.
"""

import argparse
import logging
import sys
from pathlib import Path
import pandas as pd

# Ensure src/ is in path
sys.path.insert(0, str(Path(__file__).parent))

from src.load import load_config, load_datasets
from src.validate import validate_schemas
from src.clean import clean_data
from src.analyze import compute_all_analyses
from src.export import export_dashboard_data, verify_privacy_compliance

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("build_dashboard_data")


def main():
    parser = argparse.ArgumentParser(description="Build dashboard aggregated JSON data.")
    parser.add_argument("--config", default="config.yaml", help="Path to config.yaml")
    parser.add_argument("--dry-run", action="store_true", help="Validate only, do not export")
    args = parser.parse_args()

    log.info("=" * 60)
    log.info("Razorpay Dashboard Data Builder")
    log.info("Config: %s | Dry-run: %s", args.config, args.dry_run)
    log.info("=" * 60)

    try:
        config = load_config(args.config)

        # 1. Load
        merchants_df, txn_df = load_datasets(config)

        # 2. Validate
        validate_schemas(merchants_df, txn_df)

        # 3. Clean
        merchants_clean, txn_clean = clean_data(merchants_df, txn_df, config)

        if args.dry_run:
            log.info("Dry-run mode enabled. Validation & cleaning passed successfully. Exiting without export.")
            return

        # 4. Analyze
        analysis_results = compute_all_analyses(merchants_clean, txn_clean, config)

        # 5. Build meta info (detect synthetic vs real based on path name)
        data_path = str(config["data"]["data_path"])
        is_synthetic = "synthetic" in data_path.lower()

        meta_info = {
            "data_type": "synthetic" if is_synthetic else "real",
            "generated_at": pd.Timestamp.now().strftime("%Y-%m-%d %H:%M:%S"),
            "merchants_count": len(merchants_clean),
            "transactions_count": len(txn_clean),
            "currency": config.get("dashboard", {}).get("currency", "INR"),
            "symbol": config.get("dashboard", {}).get("symbol", "₹"),
        }

        # 6. Export
        export_dashboard_data(analysis_results, meta_info, config)

        # 7. Privacy audit
        output_dir = Path(config["outputs"]["dashboard_data_dir"])
        min_group_size = config.get("analysis", {}).get("min_group_size", 10)
        verify_privacy_compliance(output_dir, min_group_size)

        log.info("=" * 60)
        log.info("SUCCESS: Dashboard data built and verified successfully.")
        log.info("=" * 60)

    except Exception as e:
        log.error("Pipeline FAILED: %s", str(e), exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
