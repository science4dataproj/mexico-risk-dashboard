# Mexico Risk Dashboard

A quantitative risk-monitoring pipeline for the Mexican economy, tracking
macroeconomic indicators (GDP, inflation, employment, exchange rate,
monetary aggregates, public debt) with a fully automated data pipeline
and — eventually — a public dashboard and composite risk index.

**Status: infrastructure complete, analysis in progress.** The data
pipeline described below runs unattended end-to-end. The composite risk
index, statistical analysis, and public dashboard are the current work
in progress (see Roadmap).

---

## Why this project exists

Mexico's economy has been navigating a stretch of major policy shifts
(minimum wage increases, debt levels, monetary policy) and external
shocks (recent disruptions to global energy shipping routes). This
project builds a transparent, data-driven, and explicitly non-partisan
way to monitor economic risk — the goal is to expose what the data
shows, with documented uncertainty and limitations, not to argue for or
against any policy position.

## Architecture
Banxico API ─┐
INEGI API ───┼──> ingestion (automated, monthly cron) ──> raw snapshots (data/raw/)
SHCP (manual)┘ 
│
v
transform/clean.py (unify to tidy panel)
│
v
data/processed/panel_long.csv


- **Ingestion:** Banxico (SIE API) and INEGI (Indicadores API) are fully
  automated — no manual steps, ever. SHCP's public debt data has no
  stable API (see `data/SERIES_METADATA.md`), so it's refreshed manually
  ~once a year via a documented procedure, then parsed by script.
- **Transformation:** all three sources are reconciled into a single
  long-format ("tidy") panel — one row per (date, series, value) — with
  every source-specific date convention documented and handled
  explicitly (see `src/transform/clean.py` docstrings).
- **CI/CD:** every push and Pull Request runs the automated test suite.
  The monthly refresh workflow fetches new data, re-runs the full
  pipeline, runs tests as a safety gate, and opens a Pull Request that
  auto-merges once checks pass — no manual intervention required for
  routine updates.

## Current indicators (v0)

| Indicator | Source | Frequency |
|---|---|---|
| GDP (constant 2018 pesos) | INEGI | Quarterly |
| CPI (general index) | INEGI | Monthly |
| Unemployment rate | INEGI (ENOE) | Monthly |
| FX rate (peso/USD, FIX) | Banxico | Daily |
| CETES 28-day rate | Banxico | Weekly |
| Banxico target rate | Banxico | Daily |
| International reserves | Banxico | Weekly |
| Monetary aggregates M1, M2 | Banxico | Monthly |
| Public debt (SHRFSP, % GDP) | SHCP | Annual, manual |

Full methodology, rejected alternatives, and known data-comparability
limitations (e.g. unemployment data is only consistent from 2005
onward) are documented in [`data/SERIES_METADATA.md`](data/SERIES_METADATA.md).

## Running it locally

```bash
git clone https://github.com/science4dataproj/mexico-risk-dashboard.git
cd mexico-risk-dashboard
pip install -r requirements.txt

cp .env.example .env
# add your own free Banxico and INEGI API tokens to .env

python -m src.ingestion.banxico
python -m src.ingestion.inegi
python -m src.transform.clean

pytest tests/ -v
```

## Roadmap

- [x] Automated data pipeline (ingestion, transformation, tests, CI/CD)
- [ ] Descriptive statistics layer (mean, median, dispersion, z-scores
      vs. historical distribution)
- [ ] Structural break analysis around sexenio (presidential term)
      boundaries — tested statistically, not assumed
- [ ] Composite risk index
- [ ] Complexity-science layer (entropy, DFA) on selected series
- [ ] Public dashboard (GitHub Pages)
- [ ] Household-level impact translation (by income decile)

## Design decisions

Every non-obvious methodological or infrastructure decision made during
this project — including ones that were later reversed — is logged in
[`data/SERIES_METADATA.md`](data/SERIES_METADATA.md), so the reasoning
is auditable rather than only living in memory.

## License

MIT — see [LICENSE](LICENSE).