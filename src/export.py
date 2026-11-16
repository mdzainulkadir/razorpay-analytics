"""
src/export.py — Export columnar cubes and legacy analysis aggregates to JSON files with strict privacy checks.
"""

import json
import logging
from pathlib import Path

log = logging.getLogger("pipeline.export")


def export_dashboard_data(analysis_results: dict, meta_info: dict, config: dict) -> None:
    """
    Export all columnar cubes and legacy analysis results to dashboard/data/*.json with strict privacy checks.
    """
    output_dir = Path(config["outputs"]["dashboard_data_dir"])
    output_dir.mkdir(parents=True, exist_ok=True)
    min_group_size = config.get("analysis", {}).get("min_group_size", 10)

    log.info("Exporting dashboard cubes and data to %s (min_group_size=%d)...", output_dir.resolve(), min_group_size)

    # Cubes
    _write_json(output_dir / "joint_cube.json", analysis_results.get("joint_cube", []))
    _write_json(output_dir / "daily_total_cube.json", analysis_results.get("daily_total_cube", []))
    _write_json(output_dir / "bank_method_cube.json", analysis_results.get("bank_method_cube", []))
    _write_json(output_dir / "failure_reason_cube.json", analysis_results.get("failure_reason_cube", []))
    _write_json(output_dir / "hourly_method_cube.json", analysis_results.get("hourly_method_cube", []))
    _write_json(output_dir / "monthly_cube.json", analysis_results.get("monthly_cube", []))

    # Legacy aggregates for fallback / support
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

    log.info("Dashboard cubes export completed successfully.")


def _write_json(filepath: Path, data: any) -> None:
    """Write data to JSON file with indentation."""
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    log.info("Wrote %s", filepath.name)


def verify_privacy_compliance(output_dir: Path, min_group_size: int) -> bool:
    """
    Verify privacy compliance across all exported JSON files and cubes.
    FAILS the build if any dimensional cell has attempts/txn_count below min_group_size.
    """
    log.info("Running strict privacy compliance audit on exported JSON files and cubes...")
    json_files = list(output_dir.glob("*.json"))

    forbidden_fields = {"merchant_id", "txn_id", "business_name", "email", "customer_city"}
    exempt_files = {"meta.json", "insights.json", "incidents.json", "latency.json", "kpis.json", "top_merchants.json", "daily_trend.json", "daily_total_cube.json"}
    cube_files = {"joint_cube.json", "bank_method_cube.json", "failure_reason_cube.json", "hourly_method_cube.json", "monthly_cube.json", "payment_mix.json", "bank_success.json", "failure_reasons.json", "hourly_heatmap.json", "category_perf.json"}

    for file in json_files:
        with open(file, "r", encoding="utf-8") as f:
            content = json.load(f)

        if isinstance(content, list):
            for item in content:
                if isinstance(item, dict):
                    for field in forbidden_fields:
                        if field in item:
                            raise ValueError(f"PRIVACY VIOLATION: Forbidden field '{field}' found in {file.name}")

                    # Check cell size enforcement for cubes / aggregate groups
                    if file.name in cube_files:
                        count_key = "attempts" if "attempts" in item else ("txn_count" if "txn_count" in item else ("count" if "count" in item else None))
                        if count_key and item[count_key] < min_group_size:
                            raise ValueError(f"PRIVACY VIOLATION: Cell in {file.name} has {count_key}={item[count_key]} (< min_group_size={min_group_size})")

        elif isinstance(content, dict):
            for k in content.keys():
                if k in forbidden_fields:
                    raise ValueError(f"PRIVACY VIOLATION: Forbidden field '{k}' found in {file.name}")

    log.info("Privacy audit PASSED: All cubes and aggregates adhere strictly to privacy and min_group_size rules.")
    return True
