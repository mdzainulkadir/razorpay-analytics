# Razorpay Payments Analytics & Incident Monitor

An end-to-end data analytics project and public web dashboard built using a "synthetic-first" workflow.

## Vision & Workflow
- **Synthetic-First**: Developed and tested entirely on high-fidelity synthetic data mimicking Razorpay payment volumes, success rates, latency patterns, and bank outages.
- **Zero Code Changes for Real Data**: Swapping datasets requires only updating `data_path` in `config.yaml`.
- **Privacy First**: Strict aggregation and suppression (`min_group_size = 10`) ensure zero PII or raw transactional IDs ever reach the public dashboard JSONs.

## Project Structure
- `config.yaml`: Single source of truth for configuration, paths, and thresholds.
- `schema.yaml`: Pandera schema contract for merchants and transactions.
- `generate_synthetic.py`: Generates synthetic data in `data/synthetic/`.
- `build_dashboard_data.py`: Pipeline runner (load -> validate -> clean -> analyze -> export -> audit).
- `main.py`: Single entry point (`python main.py --config config.yaml [--dry-run]`).
- `src/`: Pipeline modules (`load.py`, `validate.py`, `clean.py`, `analyze.py`, `export.py`).
- `dashboard/`: Static web application (`index.html`, `styles.css`, `app.js`, `data/`).
- `tests/`: Pytest test suite.

## Quick Start

1. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

2. **Generate synthetic data:**
   ```bash
   python generate_synthetic.py
   ```

3. **Run data pipeline:**
   ```bash
   python main.py --config config.yaml
   ```

4. **Preview dashboard locally:**
   ```bash
   python -m http.server --directory dashboard 8000
   ```
   Open `http://localhost:8000` in your browser.
