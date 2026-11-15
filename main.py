"""
main.py — Single entry point for the Razorpay Payments Analytics pipeline.
Usage:
    python main.py --config config.yaml [--dry-run]
"""

import argparse
import subprocess
import sys


def main():
    parser = argparse.ArgumentParser(description="Razorpay Payments Analytics Pipeline Entry Point")
    parser.add_argument("--config", default="config.yaml", help="Path to configuration file")
    parser.add_argument("--dry-run", action="store_true", help="Run validation and cleaning only without export")
    args = parser.parse_args()

    cmd = [sys.executable, "build_dashboard_data.py", "--config", args.config]
    if args.dry_run:
        cmd.append("--dry-run")

    print(f"Running pipeline command: {' '.join(cmd)}")
    result = subprocess.run(cmd)
    sys.exit(result.returncode)


if __name__ == "__main__":
    main()
