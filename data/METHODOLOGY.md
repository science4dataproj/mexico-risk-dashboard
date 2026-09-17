# Methodology — Mexico Risk Dashboard

*Last substantive revision: September 16, 2026*

---

## Introduction

### Motivation

Mexican public debate holds two competing narratives about the country's economic direction since 2018, often presented without nuance. One holds that sustained minimum-wage increases, expanded social programs, and broader circulation of resources across the population represent a necessary correction relative to prior administrations. The other warns that these same policies — combined with public debt, the growth of monetary aggregates, and Banxico's monetary stance — are gradually steering the country toward an economic crisis comparable to that of the 1980s.

Both positions cite real evidence. Independent approval polling has placed presidential approval consistently between 65% and 75% throughout 2026 (Mitofsky, El Financiero, Enkoll — see, e.g., Mitofsky, February 2026), levels that, compared directly at the same point in the presidential term, exceed those of every other administration this century. At the same time, the memory of the 1982 crisis — hyperinflation, shortages, price controls — remains a legitimate reference point for what gradual economic deterioration can become if left undetected.

This project does not attempt to settle which narrative is correct — that is beyond what a statistical analysis can or should arbitrate. It starts from a different premise: that a country's economic behavior, like that of any system in which many agents adapt and react to one another, produces patterns that resist being reduced to a single account, favorable or adverse. That is, in essence, the central observation of complex systems theory, and it is the framework this project uses to approach the underlying question: are there statistical signs that the Mexican economy is becoming more fragile, independent of what either narrative assumes in advance?

### Theoretical framework, correctly attributed

The central tool used here is **critical slowing down (CSD)**: the pattern by which a system approaching a regime change — a bifurcation, in dynamical systems terms — takes progressively longer to recover from small perturbations (rising autocorrelation) and oscillates with growing amplitude (rising variance).

Its origin is worth stating precisely, since it is often attributed imprecisely. The mathematical result explaining *why* this happens — that near a bifurcation, a system's dominant eigenvalue approaches zero, mechanically slowing its recovery — was established by **Wissel (1984)**, and developed further by **Carpenter and Brock (2006)** for variance specifically and by **van Nes and Scheffer (2007)** for autocorrelation. The widely cited **Scheffer et al. (2009, *Nature*)** paper does not discover the phenomenon: it **synthesizes** these threads into a unified "early-warning signals" framework, and it is that same paper that explicitly extends applicability beyond ecology, noting in its own abstract that it applies to *"ecosystems to financial markets and the climate."*

Since then, the financial-economics community has tested this framework directly. **Diks, Hommes, and Wang (2019)** applied it to four historical episodes — Black Monday (1987), the 1997 Asian crisis, the dot-com bubble, and the 2008 crisis — finding clear evidence only in the first, with mixed or non-significant results in the others. A later finding, from **Guttal, Raghavendra, Goel, and Hoarau (2016)**, is especially relevant to this project's design: examining major historical stock market crashes, they found that variance consistently rose before each crash, **but autocorrelation did not always do so** — which questions whether requiring both signals simultaneously, as this project does, is the right criterion specifically for financial-type series. This is a recognized, unresolved limitation of the current design (see §9 and §10 below).

### Why rigor requires defining "collapse" and "critical variable" before measuring anything

Applying critical slowing down to an economy without first specifying what counts as a crisis, and which variables are mechanistically relevant to detecting it, is the most likely explanation behind the mixed results the literature reports: if the mechanism of a currency crisis operates through the exchange rate and reserves, looking for its signal in a stock index — as several of the studies cited above did — is simply looking in the wrong place.

For this reason, this project adopts explicit, externally-sourced definitions (not invented for the project's convenience) before building any indicator — developed in §1 and §2 below.

### Objective, with honestly calibrated expectations

The objective is **not** to predict whether, when, or with what magnitude an economic crisis might occur in Mexico — that ambition is not supported by the evidence available today, given the tools and data on hand (see §8 and §10). The objective, more modest and more honest, is to build a **statistical monitoring system**: an instrument that flags when an indicator's behavior departs unusually from its own historical pattern, to direct attention — not to replace expert analysis, nor to issue a verdict.

---

## 1. Defining "crisis" (collapse)

This project adopts the quantitative crisis typology from **Reinhart and Rogoff (2009, *This Time Is Different: Eight Centuries of Financial Folly*)**, the most-cited reference in economics for classifying and dating historical crises using explicit thresholds rather than subjective judgment:

| Crisis type | Quantitative threshold |
|---|---|
| Currency crisis | Annual depreciation ≥ 15% |
| Inflation crisis | Annual inflation ≥ 20% |
| Hyperinflation | Annual inflation ≥ 500% |
| Banking crisis | Bank runs leading to closure/merger/bailout, or massive state bailout without visible runs |
| Sovereign debt crisis | Default (external or domestic) |

A sixth type, not covered by Reinhart and Rogoff but well documented in the international-economics literature, is added: the **sudden stop** — **Calvo (1998)** — an abrupt reversal of capital flows driven by loss of investor confidence, quantified by Calvo et al. (2004) as a drop of at least 2 standard deviations from trend.

**This typology is explicitly not exhaustive.** It covers discrete financial crises, not phenomena like business-cycle recession (defined independently via the NBER criterion: a significant decline in GDP, income, employment, and industrial production, spread across the economy) or terms-of-trade shocks like the current Strait of Hormuz closure (for which the correct methodological reference is **Hamilton (1983, 2003)** on oil shocks specifically, not generic commodity-cycle literature). Both are documented as future work (§10).

## 2. Critical variables: current design and its acknowledged limitation

This is where the project is most transparent about its own scope. The current version does **not** assign crisis-type-specific critical variables — which would mean, for example, prioritizing the M2/reserves ratio to detect currency-crisis stress, following **Kaminsky, Lizondo, and Reinhart (1998)**, or credit growth to detect banking-crisis stress, following **Schularick and Taylor (2012)**, who found it to be the strongest historical predictor of financial crises across a 140-year, 14-country study. Instead, it applies the same critical-slowing-down criterion **agnostically** across nine general macroeconomic indicators, grouped into five domains.

**Designing crisis-type-specific critical variables — the "directed layer" — is explicitly the project's next major body of work, not something already solved.** The current design is the "agnostic layer": it does not presuppose what kind of shock might occur, at the cost of being unable to attribute a detected signal to a specific mechanism.

## 3. Domain taxonomy

| Domain | Series | In composite index? |
|---|---|---|
| External stability | Exchange rate, international reserves | Yes |
| Liquidity | M1, M2 | Yes |
| Rates & monetary policy | 28-day CETES rate, Banxico's target rate | Yes |
| Real economy | Quarterly GDP, unemployment rate | Yes |
| Prices | CPI | Yes |
| Fiscal solvency | Public debt (% of GDP, SHRFSP measure) | No — see §7 |

These five domains were **not** designed from the crisis-classification literature — they were chosen pragmatically, based on which official series (Banxico, INEGI) offered reliable, long-running, automatable data intuitively spanning distinct dimensions of economic activity. A retrospective audit against the literature cited in §1–§2 found partial, uneven alignment, honestly documented here rather than glossed over:

| Crisis type / established variable | Covered? |
|---|---|
| Currency crisis (FX, reserves) | ✅ Well covered |
| Inflation crisis | ✅ Well covered |
| Recession / growth | 🟡 Partial (no formal NBER-style rule applied yet) |
| Sovereign debt crisis | 🟡 Tracked but excluded from the index (§7) |
| Banking crisis | ❌ Not covered — no credit-growth variable |
| Sudden stop (Calvo) | ❌ Not covered — no capital-flows/balance-of-payments data |
| Exports (Kaminsky, Lizondo & Reinhart) | ❌ Not covered |
| M2/reserves ratio (KLR's best-performing indicator) | ❌ Not covered — both inputs exist in the pipeline, but the ratio itself is never computed |
| Equity prices (KLR) | ❌ Not covered — no BMV/IPC series |
| Terms-of-trade / oil shock (Hamilton) | ❌ Not covered — no oil price series, despite motivating the project |

Closing these gaps — building the "directed layer" described in §2 — is the project's most concrete, literature-grounded next step.

## 4. What gets measured per series

For every series, in two reference windows (full available history, and a rolling 10-year window), the pipeline computes several categories of statistics:

- **Location & spread**: mean, median, standard deviation — with bootstrap confidence intervals, since most of these series are not normally distributed.
- **Anomaly detection**: a z-score and a percentile rank for the most recent observation, plus a z-score on the most recent period-over-period change.
- **Distributional shape**: skewness, excess kurtosis, and a Jarque-Bera normality test.
- **Fragility trend** *(the only category feeding the domain score — see §5)*: whether rolling autocorrelation and rolling variance show a statistically significant increasing trend over time, tested with Kendall's tau.

### Significance testing: ARMA-surrogate method, not Kendall's theoretical p-value

Trend significance is **not** assessed via Kendall's tau's own theoretical p-value. An internal audit found that this theoretical p-value has a severely inflated false-positive rate when applied to rolling-window statistics: testing ~150 random reference dates per series/window, "statistically significant" results (p < 0.05) occurred 40–98% of the time across every series tested, far above the nominal 5%. Root cause: adjacent points of a rolling-window statistic mechanically share most of their underlying data, violating the independence assumption behind Kendall's asymptotic p-value — a problem long documented in hydrological trend-detection literature (Yue, Pilon, Phinney, & Cavadias, 2002).

The fix adopted is the field's own reference methodology:

> Dakos, V., Carpenter, S. R., Brock, W. A., Ellison, A. M., Guttal, V., Ives, A. R., Kéfi, S., Livina, V., Seekell, D. A., van Nes, E. H., & Scheffer, M. (2012). Methods for Detecting Early Warnings of Critical Transitions in Time Series Illustrated Using Simulated Ecological Data. *PLOS ONE*, 7(7), e41010.

The raw series is detrended, a low-order ARMA(1,1) model is fit to the residuals, 200 synthetic "surrogate" series are generated sharing the same short-term correlation structure but with no systematic trend by construction, the identical rolling-stat + Kendall's tau pipeline runs on each surrogate, and an empirical p-value is derived via the Phipson and Smyth (2010) correction (avoiding the impossible p = 0 result a naive percentile calculation would give). All p-values across the full batch are then corrected together with Benjamini-Hochberg FDR correction.

**Measured impact of this fix:** the composite fragility index dropped from 62.9 ("Trend to monitor") to 12.7 ("No notable change") once recalculated with the corrected method — see the repository's `SERIES_METADATA.md` Decisions Log for the full diagnostic.

## 5. How a domain score is calculated

A domain's fragility score is built **exclusively** from the fragility-trend statistics above — never from level statistics like z-scores or percentiles. This is deliberate: whether a high or low level is good or bad news is often genuinely ambiguous and domain-specific (is historically low unemployment reassuring, or a sign of an overheating labor market?), while "is this series becoming less stable over time" has one unambiguous interpretation regardless of domain.

For each series × window combination, two individual trend signals (rising autocorrelation, rising variance) and one combined signal (both simultaneously significant and rising — the full CSD pattern) are checked. The combined signal counts double in the weighted total.

```
weighted_active   = (# active individual trend signals) + 2 × (# active combined signals)
weighted_possible = (# individual trend signals evaluated) + 2 × (# combined signals evaluated)
domain_score = 100 × weighted_active / weighted_possible
```

### Score bands, in plain language

| Score | Label | What it means for a general reader |
|---|---|---|
| 0–33 | No notable change | The indicator is behaving about as predictably as it has, on average, throughout its history. |
| 34–66 | Trend to monitor | There are signs something is moving less predictably than usual — not alarming, but worth following. |
| 67–100 | Strong fragility signal | The indicator shows a statistically robust pattern associated, in the literature, with resilience loss — not a crisis prediction, but a signal warranting sustained attention and closer analysis. |

## 6. How the composite index is calculated

The composite index is a **simple, unweighted average** of the 5 eligible domain scores. Equal weighting is deliberate: a domain doesn't count more just because it happens to track more underlying series.

## 7. Why fiscal solvency (public debt) isn't in the index

Public debt (% of GDP) is updated only once a year (see `SERIES_METADATA.md` for why it cannot be automated). The fragility-trend statistics this methodology relies on need many overlapping rolling windows to detect a *trend* — a handful of annual data points cannot support this reliably. Rather than force an unreliable estimate, this domain is tracked and shown, but excluded from the score entirely.

## 8. What this index does — and does not — claim to measure

This index measures **statistical fragility**: whether a series is behaving in a way associated, in the complex-systems and financial-crisis literature, with reduced resilience to shocks. It does **not** measure economic performance, and it is **not** a prediction of when — or whether — a crisis will occur. A rising score means the underlying data shows a pattern of growing instability; it does not mean a downturn is certain, and a low score does not mean the economy is problem-free by other measures this index isn't designed to capture.

## 9. Related work in the literature

### 9.1 Financial applications and a critical counterpoint

Beyond the papers already discussed in the Introduction, two further references shaped this project's design:

> van den End, J. W. (2019). Applying complexity theory to interest rates: Evidence of critical transitions in the euro area. *Credit and Capital Markets*, 52(1), 1–33.

A central-bank application (De Nederlandsche Bank) directly to interest rates — the closest existing precedent to this project's "Rates & monetary policy" domain.

> Ismail, M. S., Md Noorani, M. S., Ismail, M., & Abdul Razak, F. (2022). Early warning signals of financial crises using persistent homology and critical slowing down: Evidence from different correlation tests. *Frontiers in Applied Mathematics and Statistics*, 8, 940133.

Used Kendall's tau specifically to test for trend significance — the same non-parametric test used in this project's `early_warning.py`.

### 9.2 A distinct, often-confused framework: self-organized criticality

An early inspiration for this project was Per Bak's sandpile model — **self-organized criticality (SOC)** (Bak, Tang, & Wiesenfeld, 1987): a system that self-organizes *toward* a critical point and remains there indefinitely, releasing accumulated stress through avalanches of all sizes (power-law distributed) as part of its ongoing, normal functioning.

Closer analysis revealed this is a **mathematically distinct framework** from critical slowing down, not an equivalent formulation. Under SOC, there is no "before" and "after" a transition — the system lives at the critical point continuously, and a large avalanche is not a collapse, it is the system working as designed. Under critical slowing down, by contrast, a system sits in *one* stable equilibrium away from criticality most of the time, and CSD describes the *approach* toward a genuinely different equilibrium — a rare, discrete regime shift.

Treating these as interchangeable would have been a real conceptual error. Per Bak's model is retained here only as the project's narrative origin story, not as a technical foundation — the operative framework throughout is Wissel/Carpenter-Brock/van Nes-Scheffer's bifurcation-based critical slowing down.

## 10. Project status and limitations — read this before citing any number here

This project is an ongoing personal research exercise, not a finished or validated forecasting tool.

**It has been backtested, with a null result.** Against the three Mexican crisis episodes with sufficient data coverage to test (2008–09 global financial crisis, 2014–16 oil price collapse, and — partially — the 1994 Tequila crisis), no series, in any episode, showed a statistically significant combined critical-slowing-down signal after correction for multiple testing. This null result is consistent with, not contradicted by, existing literature: Diks et al. (2019) similarly found evidence only for Black Monday (1987) among four tested episodes. Per the project's own decision criterion, this result is evidence to prioritize building the crisis-type-specific "directed layer" (§2) over further investment in the current agnostic design.

**It likely overlaps with established econometric tools.** Rising variance in a financial or economic time series is exactly what GARCH-family models (Engle, 1982; Bollerslev, 1986) are built to capture. This project has not yet been compared against a GARCH-based approach on the same data.

**It complements, rather than replaces, other economic analysis.** Outlets like México Cómo Vamos evaluate Mexico's economy against explicit normative benchmarks (e.g., is GDP growth enough to keep up with population growth). This project asks a narrower, different question — is each indicator behaving unusually relative to its own history — and is best read alongside that kind of analysis, not instead of it.

If you're using this project to evaluate the author's technical work rather than to draw conclusions about the Mexican economy: that is exactly the right way to read it right now.

---

## References

- Bak, P., Tang, C., & Wiesenfeld, K. (1987). Self-organized criticality: An explanation of the 1/f noise. *Physical Review Letters*, 59(4), 381–384.
- Bollerslev, T. (1986). Generalized autoregressive conditional heteroskedasticity. *Journal of Econometrics*, 31(3), 307–327.
- Calvo, G. A. (1998). Capital flows and capital-market crises: The simple economics of sudden stops. *Journal of Applied Economics*, 1(1), 35–54.
- Carpenter, S. R., & Brock, W. A. (2006). Rising variance: A leading indicator of ecological transition. *Ecology Letters*, 9(3), 311–318.
- Dakos, V., Carpenter, S. R., Brock, W. A., Ellison, A. M., Guttal, V., Ives, A. R., Kéfi, S., Livina, V., Seekell, D. A., van Nes, E. H., & Scheffer, M. (2012). Methods for detecting early warnings of critical transitions in time series illustrated using simulated ecological data. *PLOS ONE*, 7(7), e41010.
- Diks, C., Hommes, C., & Wang, J. (2019). Critical slowing down as an early warning signal for financial crises? *Empirical Economics*, 57(4), 1201–1228.
- Engle, R. F. (1982). Autoregressive conditional heteroscedasticity with estimates of the variance of United Kingdom inflation. *Econometrica*, 50(4), 987–1007.
- Guttal, V., Raghavendra, S., Goel, N., & Hoarau, Q. (2016). Lack of critical slowing down suggests that financial meltdowns are not critical transitions, yet rising variability could signal systemic risk. *PLOS ONE*, 11(1), e0144198.
- Hamilton, J. D. (1983). Oil and the macroeconomy since World War II. *Journal of Political Economy*, 91(2), 228–248.
- Hamilton, J. D. (2003). What is an oil shock? *Journal of Econometrics*, 113(2), 363–398.
- Ismail, M. S., Md Noorani, M. S., Ismail, M., & Abdul Razak, F. (2022). Early warning signals of financial crises using persistent homology and critical slowing down: Evidence from different correlation tests. *Frontiers in Applied Mathematics and Statistics*, 8, 940133.
- Kaminsky, G. L., Lizondo, S., & Reinhart, C. M. (1998). Leading indicators of currency crises. *IMF Staff Papers*, 45(1), 1–48.
- Kaminsky, G. L., & Reinhart, C. M. (1999). The twin crises: The causes of banking and balance-of-payments problems. *American Economic Review*, 89(3), 473–500.
- Phipson, B., & Smyth, G. K. (2010). Permutation p-values should never be zero: Calculating exact p-values when permutations are randomly drawn. *Statistical Applications in Genetics and Molecular Biology*, 9(1), Article 39.
- Reinhart, C. M., & Rogoff, K. S. (2009). *This time is different: Eight centuries of financial folly*. Princeton University Press.
- Schularick, M., & Taylor, A. M. (2012). Credit booms gone bust: Monetary policy, leverage cycles, and financial crises, 1870-2008. *American Economic Review*, 102(2), 1029–1061.
- van den End, J. W. (2019). Applying complexity theory to interest rates: Evidence of critical transitions in the euro area. *Credit and Capital Markets*, 52(1), 1–33.
- van Nes, E. H., & Scheffer, M. (2007). Slow recovery from perturbations as a generic indicator of a nearby catastrophic shift. *The American Naturalist*, 169(6), 738–747.
- Wissel, C. (1984). A universal law of the characteristic return time near thresholds. *Oecologia*, 65(1), 101–107.
- Yue, S., Pilon, P., Phinney, B., & Cavadias, G. (2002). The influence of autocorrelation on the ability to detect trend in hydrological series. *Hydrological Processes*, 16(9), 1807–1829.
