# Deployment Guide

This dashboard is a fully static site (HTML, CSS, vanilla JS, Plotly.js) requiring **no backend server** — it loads pre-aggregated JSON files from `dashboard/data/`.

## Primary Deployment: Vercel

1. **Install Vercel CLI (optional) or connect via GitHub:**
   ```bash
   npm i -g vercel
   ```
2. **Deploy from project root:**
   ```bash
   vercel --prod
   ```
   *(When prompted, set the root directory to `dashboard` or configure build settings to point to `dashboard/`)*.

Alternatively, connect your GitHub repository to Vercel and set:
- **Root Directory:** `dashboard`
- **Build Command:** `python ../build_dashboard_data.py` (if running build on deploy, or just commit pre-built `dashboard/data/*.json`)
- **Output Directory:** `.`

---

## Alternative Deployments

### Netlify
1. Drag and drop the `dashboard/` folder into Netlify Drop, or connect your Git repository with base directory `dashboard`.
2. Static export requires zero build steps if `dashboard/data/*.json` are committed.

### GitHub Pages
1. Push project to GitHub.
2. Enable GitHub Pages in repository settings, pointing to the `dashboard/` folder branch.

---

## Redeploying with Real Data
1. Update `data_path` in `config.yaml` to point to your real dataset directory.
2. Run the pipeline in your terminal:
   ```bash
   python main.py --config config.yaml
   ```
3. Commit and push the newly generated JSON files in `dashboard/data/` or trigger your Vercel redeploy.
