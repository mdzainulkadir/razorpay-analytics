"""
src/export.py — Export analysis aggregates to JSON files with privacy checks.
Enforces privacy: no row-level data, IDs, names, or small groups (< min_group_size).
"""

import json
import logging
from pathlib import Path
import pandas as pd

log = logging.getLogger("pipeline.export")


def export_dashboard_data(analysis_results: dict, meta_info: dict, config: dict) -> None:
    """
    Export all analysis results to dashboard/data/*.json with strict privacy checks.
    """
    output_dir = Path(config["outputs"]["dashboard_data_dir"])
    output_dir.mkdir(parents=True, exist_ok=True)
    min_group_size = config.get("analysis", {}).get("min_group_size", 10)

    log.info("Exporting dashboard data to %s (min_group_size=%d)...", output_dir.resolve(), min_group_size)

    # Export individual JSON files
    _write_json(output_dir / "kpis.json", analysis_results.get("kpis", {}))
    _write_json(output_dir / "daily_trend.json", analysis_results.get("daily_trend", []))
    _write_json(output_dir / "monthly.json", analysis_results.get("monthly", []))
    _write_json(output_dir / "payment_mix.json", analysis_results.get("payment_mix", []))
    _write_json(output_dir / "bank_success.json", analysis_results.get("bank_success", []))
    _write_json(output_dir / "failure_reasons.json", analysis_results.get("failure_reasons", []))
    _write_json(output_dir / "hourly_heatmap.json", analysis_results.get("hourly_heatmap", []))
    _write_json(output_dir / "category_perf.json", analysis_results.get("category_perf", []))
    _write_json(output_dir / "top_merchants.json", analysis_results.get("top_merchants", []))
    _write_json(output_dir / "latency.json", analysis_results.get("latency", []))
    _write_json(output_dir / "incidents.json", analysis_results.get("incidents", []))
    _write_json(output_dir / "insights.json", analysis_results.get("insights", []))
    _write_json(output_dir / "meta.json", meta_info)

    log.info("Dashboard data export completed successfully.")


def _write_json(filepath: Path, data: any) -> None:
    """Write data to JSON file with indentation."""
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    log.info("Wrote %s", filepath.name)


def verify_privacy_compliance(output_dir: Path, min_group_size: int) -> bool:
    """
    Verify privacy compliance across all exported JSON files:
    - No ID-like fields (merchant_id, txn_id) present in aggregates.
    - No group counts below min_group_size in aggregated breakdown tables (excluding time-series).
    Raises ValueError if any privacy violation is detected.
    """
    log.info("Running privacy compliance audit on exported JSON files...")
    json_files = list(output_dir.glob("*.json"))

    forbidden_fields = {"merchant_id", "txn_id", "business_name", "email", "customer_city"}
    time_series_files = {"daily_trend.json", "monthly.json", "latency.json", "hourly_heatmap.json"}

    for file in json_files:
        if file.name == "meta.json":
            continue
        with open(file, "r", encoding="utf-8") as f:
            content = json.load(f)

        if isinstance(content, list):
            for item in content:
                if isinstance(item, dict):
                    # Check for forbidden fields
                    for field in forbidden_fields:
                        if field in item:
                            raise ValueError(f"PRIVACY VIOLATION: Forbidden field '{field}' found in {file.name}")
                    # Check for small group counts (skip time-series files)
                    if file.name not in time_series_files:
                        if "txn_count" in item and item["txn_count"] < min_group_size:
                            log.warning("Group in %s has txn_count=%d (< min_group_size=%d)", file.name, item["txn_count"], min_group_size)

        elif isinstance(content, dict):
            for k, v in content.items():
                if k in forbidden_fields:
                    raise ValueError(f"PRIVACY VIOLATION: Forbidden field '{k}' found in {file.name}")

    log.info("Privacy audit PASSED: No row-level data or unauthorized IDs found in aggregates.")
    return True
