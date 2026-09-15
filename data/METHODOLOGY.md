# Methodology — Composite Fragility Index

This document explains, in plain terms but without skipping the math,
how the composite index and the six domain scores on the dashboard are
calculated. For the full statistical methodology behind every
individual number (bootstrap confidence intervals, structural break
testing, etc.), see [`series_Medatada.md`](series_Medatada.md) — this
document focuses specifically on how those individual results get
rolled up into the scorecard you see on the dashboard.

---

## 1. The five domains

Every tracked economic series is assigned to exactly one domain:

| Domain | Series it's built from | In the composite index? |
|---|---|---|
| External stability | Exchange rate, international reserves | Yes |
| Liquidity | M1, M2 | Yes |
| Rates & monetary policy | 28-day CETES rate, Banxico's target rate | Yes |
| Real economy | Quarterly GDP, unemployment rate | Yes |
| Prices | CPI | Yes |
| Fiscal solvency | Public debt (% of GDP) | No — see §5 |

## 2. What gets measured per series

For every series, in two reference windows (full available history, and
a rolling 10-year window), the pipeline computes several categories of
statistics:

- **Location & spread**: mean, median, standard deviation — with
  bootstrap confidence intervals, since most of these series are not
  normally distributed.
- **Anomaly detection**: a z-score and a percentile rank for the most
  recent observation, plus a z-score on the most recent
  period-over-period change.
- **Distributional shape**: skewness, excess kurtosis, and a
  Jarque-Bera normality test.
- **Fragility trend** *(this is the only category that feeds the
  domain score — see §3)*: whether rolling autocorrelation and rolling
  variance show a statistically significant increasing trend over
  time, tested with Kendall's tau. A combined flag fires only when
  *both* are rising and *both* are statistically significant.

All p-values across the full batch of statistics are corrected together
using Benjamini-Hochberg FDR correction before anything is treated as
"significant."

## 3. How a domain score is calculated

**A domain's fragility score is built exclusively from the fragility
trend statistics above — never from level statistics like z-scores or
percentiles.**

This is a deliberate design choice. Whether a *high* or *low* level is
good or bad news is often genuinely ambiguous and different from domain
to domain — is historically low unemployment reassuring, or a sign of
an overheating labor market? Whether a series is *becoming less
stable over time*, on the other hand, has one unambiguous
interpretation regardless of domain: higher means more fragile. Level
context is never discarded — it's shown in the accompanying narrative
text — it's just never folded into the number itself.

For each series × window combination in a domain, three trend signals
are checked:

1. Is the rolling-autocorrelation trend (`ac1_trend_tau`) positive
   **and** statistically significant?
2. Is the rolling-variance trend (`variance_trend_tau`) positive
   **and** statistically significant?
3. Is the *combined* critical-slowing-down flag active (both of the
   above true at once)?

The combined flag counts **double** in the weighted total — it
represents the stronger, joint signal (autocorrelation *and* variance
rising together), not just one indicator in isolation.

**Formula:**

```
weighted_active   = (# active individual trend signals) + 2 × (# active combined flags)
weighted_possible = (# individual trend signals evaluated) + 2 × (# combined flags evaluated)

domain_score = 100 × weighted_active / weighted_possible
```

### Worked example (illustrative — not live data)

Imagine a domain with two series, each evaluated in two windows (full
history and rolling 10-year), so there are 4 series×window
combinations in total:

| Series × window | AC1 rising & significant? | Variance rising & significant? | Combined flag active? |
|---|---|---|---|
| Series A, full history | Yes | Yes | Yes |
| Series A, rolling 10y | Yes | No | No |
| Series B, full history | No | No | No |
| Series B, rolling 10y | Yes | Yes | Yes |

- Individual trend signals evaluated: 2 stats × 4 combinations = 8.
  Active: AC1 (A-full, A-10y, B-10y) = 3, Variance (A-full, B-10y) = 2
  → 5 active.
- Combined flags evaluated: 4. Active: 2 (A-full, B-10y).

```
weighted_active   = 5 + 2×2 = 9
weighted_possible = 8 + 2×4 = 16
domain_score      = 100 × 9 / 16 = 56.3
```

### Score bands

| Score | Label |
|---|---|
| 0–33 | No notable change |
| 34–66 | Trend to monitor |
| 67–100 | Strong fragility signal |

These bands are the same ones used throughout the dashboard, including
in the plain-language explanations.

## 4. How the composite index is calculated

The composite index is a **simple, unweighted average** of the 5
eligible domain scores:

```
composite_index = (score_external + score_liquidity + score_rates + score_real_economy + score_prices) / 5
```

Equal weighting is deliberate: a domain doesn't count more in the
composite just because it happens to track more underlying series (for
example, "Prices" is built from a single series while "Liquidity" is
built from two, but each domain still contributes exactly 1/5 of the
final number).

## 5. Why fiscal solvency (public debt) isn't in the index

Public debt (% of GDP) is updated only once a year. The fragility
trend statistics this whole methodology relies on — rolling
autocorrelation and rolling variance — need many overlapping rolling
windows to detect a *trend*, which a handful of annual data points
cannot support reliably. Rather than force an unreliable trend
estimate, this domain is tracked and shown on the dashboard, but
excluded from the score entirely. How to incorporate fiscal solvency
into future versions of the index, using a method appropriate to its
frequency, is an open item — see the project roadmap in the
repository's README.

## 6. What this index does — and does not — claim to measure

This index measures **statistical fragility**: whether a series is
behaving in a way associated, in the complex-systems literature, with
reduced resilience to shocks. It does **not** measure economic
performance, and it is **not** a prediction of when — or whether — a
crisis will occur. A rising score means the underlying data shows a
pattern of growing instability; it does not mean a downturn is certain,
and a low score does not mean the economy is problem-free by other
measures (growth, equity, employment quality, etc.) that this
particular index isn't designed to capture.
