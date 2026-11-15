# PROJECT: Synthetic-First Payments Analytics + Public Dashboard

## Vision
I am building an end-to-end data analytics project for a hypothetical Razorpay-style
payments business, using a "synthetic-first" workflow.

You (Claude Code) build and test everything on SYNTHETIC data only. You never see,
read, or need the real dataset. When the work is done, I run your pipeline myself on
the real data by changing ONE config value (`data_path`), then redeploy the dashboard.

The final output is a beautiful, interactive web dashboard on a public link.
Do NOT use Power BI, Tableau, or any desktop BI tool.

## Workflow
1. The real dataset lives outside this project folder. Never ask for it, search for
   it, list directories outside this project, or try to read it. If you notice a
   path to it anywhere, ignore it and tell me.
2. The only description of the data you get is `DATA_DICTIONARY.md` (schema, types,
   null rates, distributions, relationships). From it, write `schema.yaml` and
   `generate_synthetic.py` to create realistic synthetic data in `data/synthetic/`.
3. Build and test the whole pipeline on the synthetic data:
   load -> validate -> clean -> analyze -> export aggregates -> dashboard.
4. I swap `data_path` and run the real data myself in my own terminal. You see real
   data or real outputs only if I paste back non-sensitive metadata or error text.

## Dataset context
Two tables: `merchants` (one row per merchant) and `transactions` (one row per payment
attempt, linked by `merchant_id`). Period: about 12 months. Currency: INR.
Full details are in `DATA_DICTIONARY.md`.

## Hard rules
- NO hardcoded paths, column names, category lists, thresholds, or date ranges.
  Everything lives in `config.yaml`. Swapping datasets must need only `data_path`.
- Write a schema contract (`schema.yaml`, enforced with pandera or pydantic) and a
  validation step that runs first. On mismatch, fail loudly with an error containing
  ONLY metadata (column names, dtypes, counts), never data values.
- Never rely on anything true only of the synthetic data. Handle unseen categories,
  different null rates, different row counts and scales, mixed date formats,
  encoding issues, extra columns (ignore them) and missing optional columns (skip
  the related charts and report it).
- No data values in logs, errors, or printed output. Log only aggregates and
  metadata (row counts, column names, dtypes, null percentages).
- Never hardcode facts about the data in code, templates, or the dashboard (for
  example a specific incident date, a bank name, or a number inside an insight).
- Reproducible: `requirements.txt`, fixed seed for synthetic generation, and one
  entry point: `python main.py --config config.yaml` (support `--dry-run` for
  validate-only).
- `.gitignore` must exclude real data paths, `outputs_real/`, `.venv/`, and `.env`.
- Clear, commented code over clever code. Small modules, small functions.

## Pipeline (src/)
- `load.py`: read CSVs from `data_path`, handle encodings, return DataFrames.
- `validate.py`: enforce `schema.yaml` (metadata-only errors).
- `clean.py`: de-duplicate `txn_id` (keep first, log count), parse dates, trim and
  standardize categories, flag invalid amounts, add derived columns
  (`is_success`, `net_amount`, `date`, `month`, `hour`, `day_of_week`).
- `analyze.py`: one small function per metric.
- `export.py` and `build_dashboard_data.py`: write aggregates to `dashboard/data/*.json`
  and enforce privacy checks (below).

## Analysis requirements
KPIs: GMV, success rate, net revenue (fees), refund rate, average ticket size, active
merchants, each with change versus the previous period.

Analyses: daily and monthly trends; payment method mix and success rate by method;
bank-wise success rate; failure reasons; hour-by-weekday heatmap; category
performance; merchant concentration (top N share); latency percentiles (p50, p90,
p99) over time; incident detection.

Incident detection must be data-driven, not hardcoded: compute hourly failure rate,
flag hours exceeding the rolling mean by `anomaly_zscore` standard deviations with a
minimum volume threshold, merge adjacent flagged hours into incidents, and export
start, end, peak failure rate, and top failure reason.

Insights: template-based sentences filled from the aggregates (never hardcoded
numbers or names).

Export files: `kpis.json`, `daily_trend.json`, `monthly.json`, `payment_mix.json`,
`bank_success.json`, `failure_reasons.json`, `hourly_heatmap.json`,
`category_perf.json`, `top_merchants.json`, `latency.json`, `incidents.json`,
`insights.json`, `meta.json`.
Decide early which filter combinations the dashboard needs (for example daily data
split by category and payment method) and export those, since the dashboard filters
pre-aggregated data, not rows.

## Dashboard (static site in dashboard/, hosted on a public link)
Architecture:
- HTML, CSS, vanilla JS, Plotly.js from a CDN. No backend.
- Loads `dashboard/data/*.json` with `fetch`. Never touches row-level data.
- Builds filters, labels, and charts dynamically from the JSON so the real data works
  with zero dashboard code changes.

Design (must look genuinely beautiful):
- Clean, modern SaaS-analytics look in the spirit of Stripe / Linear dashboards.
  One accent color, soft neutrals, red/green only for status.
- Inter for text, tabular numbers for KPIs. Rounded cards, subtle shadows, generous
  spacing, 12-column grid.
- Top row of KPI cards with big numbers and up/down change indicators.
- 8 to 10 polished interactive charts, each with a clear title, units, and a
  one-line insight caption. Tooltips formatted in INR with separators.
- Global filters (date range, category, payment method) updating every chart.
- Dark/light mode toggle, remembered between visits.
- Fully responsive; single column under 768px; must look great at 375px width.
- Skeleton loaders, graceful empty states, smooth transitions, no layout breakage.
- "Key insights" strip and an incident timeline section.
- Footer note: "Demo built on synthetic data" when `meta.json` says the data is
  synthetic.

## Privacy for the public link
- Aggregates only. No row-level data, IDs, names, emails, or exact timestamps tied to
  individuals in any JSON.
- Suppress or merge any group smaller than `min_group_size` (default 10).
- `build_dashboard_data.py` must FAIL the run if it detects ID-like fields, small
  groups, or anything suspicious.

## Deployment
- Configure for Vercel; document Netlify and GitHub Pages as alternatives.
- Preview locally with `python -m http.server` inside `dashboard/`.
- Write `DEPLOY.md` with exact steps to deploy the synthetic demo first, and to
  redeploy after my real-data run.

## Testing
Write `pytest` tests on synthetic data, including: schema validation passes and fails
correctly, new unseen category, all-null column, tiny dataset (50 rows) with
small-group suppression, large dataset, duplicate IDs, mixed date formats, export
privacy check, and "error messages contain no data values".

## Deliverables
`generate_synthetic.py`, `config.yaml`, `schema.yaml`, `src/`, `build_dashboard_data.py`,
`dashboard/` (index.html, styles.css, app.js, data/), `tests/`, `main.py`,
`README.md`, `DEPLOY.md`, and `ASSUMPTIONS.md` (everything that could differ in real
data: category lists, date ranges, amount scales, null rates, timezone, currency).

## Stack
Python (pandas, numpy, pyyaml, pandera, pytest, scipy optional), HTML/CSS/JS with
Plotly.js. SQL only where it genuinely helps.

## How to start
Do NOT write code yet.
1. Read `DATA_DICTIONARY.md` and ask me any schema questions you still have.
2. Propose the project structure, KPI list, and dashboard layout.
3. Wait for my explicit approval, then build phase by phase, running tests after each
   phase and summarizing what changed.
