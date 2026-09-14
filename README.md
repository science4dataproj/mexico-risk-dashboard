# Mexico Risk Dashboard

A quantitative risk-monitoring pipeline for the Mexican economy, tracking
macroeconomic indicators (GDP, inflation, employment, exchange rate,
monetary aggregates, public debt) with a fully automated data pipeline,
a statistical anomaly-detection layer, and — eventually — a public
dashboard and composite risk index.

**Status: data pipeline and analysis layer complete. Public dashboard
in progress.** Data flows in unattended end-to-end, and every series is
now analyzed for statistical anomalies and early-warning signals on
each run. The public-facing dashboard (GitHub Pages) and the narrative
write-up are the current work in progress (see Roadmap).

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
Banxico API(automated, monthly cron) + INEGI API(automated, monthly cron) +  SHCP (manual) -> raw snapshots (data/raw/) -> transform/clean.py (unify to tidy panel) -> data/processed/panel_long.csv


- **Ingestion:** Banxico (SIE API) and INEGI (Indicadores API) are fully
  automated — no manual steps, ever. SHCP's public debt data has no
  stable API (see `data/SERIES_METADATA.md`), so it's refreshed manually
  ~once a year via a documented procedure, then parsed by script.
- **Transformation:** all three sources are reconciled into a single
  long-format ("tidy") panel — one row per (date, series, value) — with
  every source-specific date convention documented and handled
  explicitly (see `src/transform/clean.py` docstrings).
- **Analysis:** each series is evaluated against three reference
  windows (full history, rolling 10 years, and since the most recent
  statistically-confirmed structural break), producing descriptive
  statistics, distributional-shape diagnostics, and a critical-slowing-down
  early-warning signal. See "Analysis methodology" below.
- **CI/CD:** every push and Pull Request runs the automated test suite.
  The monthly refresh workflow fetches new data, re-runs the full
  pipeline, runs tests as a safety gate, opens a Pull Request, and
  auto-merges once checks pass — no manual intervention required for
  routine updates. `main` is protected: all changes (automated or
  manual) go through a Pull Request with passing CI.

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

## Analysis methodology

Every series is evaluated against **three reference windows**, computed
side by side rather than picking one arbitrarily:

1. **Full history** — maximum statistical power, but may mix distinct
   economic regimes.
2. **Rolling 10 years** — the conventional span of at least one full
   business cycle (expansion + contraction), avoiding a baseline
   anchored to only one phase of the cycle.
3. **Since the last confirmed structural break** — sexenio (presidential
   term) boundaries are tested individually with a Chow test (with
   Benjamini-Hochberg correction across all boundaries tested per
   series) — never assumed to be a regime change by default. The most
   recent boundary that tests significant defines this window's start.

For each (series, window), the pipeline computes:

- **Location/spread:** mean, median, std, min, max, with bootstrap
  confidence intervals.
- **Anomaly detection:** z-score and percentile rank of the latest
  observation against the window's history; a z-score on the most
  recent period-over-period change, to catch unusually sharp moves
  distinct from unusually high levels.
- **Distributional shape:** skewness, excess kurtosis, and a
  Jarque-Bera normality test — economic series are rarely normal, and
  fat tails matter directly for risk assessment.
- **Critical slowing down:** rolling autocorrelation and rolling
  variance are each tested for a significant increasing trend (Kendall's
  tau). A combined flag requires BOTH to be significantly rising — a
  pattern associated in the complex-systems literature (e.g. Scheffer
  et al.) with systems losing resilience before a regime shift. This
  signal detects growing fragility, not a deterministic prediction of
  when (or whether) a transition will occur.

All p-values across the full batch (every series × window × statistic)
are corrected together using Benjamini-Hochberg FDR correction — never
per series in isolation, to avoid false positives from testing many
things at once.

Output: [`data/processed/analysis_results.csv`](data/processed/analysis_results.csv).

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
python -m src.analysis.run_analysis

pytest tests/ -v
```

## Roadmap

- [x] Automated data pipeline (ingestion, transformation, tests, CI/CD)
- [x] Statistical analysis layer (structural breaks, reference windows,
      descriptive statistics, critical-slowing-down early-warning signal)
- [ ] Public dashboard (GitHub Pages)
- [ ] Composite risk index
- [ ] Household-level impact translation (by income decile)
- [ ] Investigating whether power-law / self-organized-criticality
      methods (inspired by Per Bak's sandpile model) could extend the
      early-warning layer beyond detecting growing fragility toward
      estimating event timing — under active research, not yet decided
      whether this is methodologically sound for economic time series

## Design decisions

Every non-obvious methodological or infrastructure decision made during
this project — including ones that were later reversed — is logged in
[`data/SERIES_METADATA.md`](data/SERIES_METADATA.md), so the reasoning
is auditable rather than only living in memory.

## License

MIT — see [LICENSE](LICENSE).