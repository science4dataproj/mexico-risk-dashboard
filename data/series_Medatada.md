# Series Metadata & Design Decisions

This document records exactly which data series were selected, why,
and every methodological decision made during pipeline design. It exists
so the project can be audited or resumed months later without having to
reconstruct reasoning from memory.

Last updated: 2026-09-12

---

## 1. Banxico (SIE — Sistema de Información Económica)

**Access:** Free public API, requires a personal token generated at
https://www.banxico.org.mx/SieAPIRest/service/v1/token
**Base URL:** `https://www.banxico.org.mx/SieAPIRest/service/v1/series`
**Verified against official catalog:** https://www.banxico.org.mx/SieAPIRest/service/v1/doc/catalogoSeries

| Key (`config.py`) | Series ID | Description | Native frequency | Data starts | Why it starts there |
|---|---|---|---|---|---|
| `fx_rate_fix` | SF43718 | MXN per USD, FIX rate | Daily | 1991-11 | FIX methodology was established during the gradual liberalization of exchange controls |
| `cetes_28d` | SF60633 | 28-day CETES rate | Weekly | 2006-09 | Methodology change in how the reference rate is calculated/published; older CETES data exists under different series IDs, not used here |
| `target_rate` | SF61745 | Banxico overnight interbank target rate | Daily | 2008-01 | Banxico adopted this rate as its monetary policy instrument in Jan 2008 (previously used the "corto" mechanism, a different instrument not comparable to this series) |
| `international_reserves` | SF43707 | International reserves | Weekly | 1995-12 | Post-1994 crisis reporting reforms increased reserve transparency/frequency |
| `m1` | SF311408 | Monetary aggregate M1 | Monthly | 2000-12 | Earliest available under current M1/M2 redefinition methodology |
| `m2` | SF311418 | Monetary aggregate M2 | Monthly | 2000-12 | Same as above |

**Key design decision:** All 6 series are fetched in a single API call
(`GET .../series/SF43718,SF60633,.../datos/{start}/{end}`) rather than
one call per series, to minimize API calls and reduce the number of
failure points. See `src/ingestion/banxico.py`.

**Important:** requesting data from `HIST_START_DATE = "1988-01-01"`
does NOT cause an error for series that don't go back that far — the
API simply returns data starting from whenever the series actually
began. This is expected behavior, not a bug. Confirmed 2026-09-12 by
inspecting `data/raw/banxico_20260912T155258Z.json`.

---

## 2. INEGI (Banco de Indicadores / API de Indicadores)

**Access:** Free public API, requires a personal token registered at
https://www.inegi.org.mx/servicios/api_indicadores.html
**Base URL:** `https://www.inegi.org.mx/app/api/indicadores/desarrolladores/jsonxml/INDICATOR`

| Key (`config.py`) | Indicator ID | Description | Native frequency | Notes |
|---|---|---|---|---|
| `unemployment_rate` | 444603 | National unemployment rate (Tasa de desocupación), population 15+, original series | Monthly | Sourced from ENOE. Confirmed via test query 2026-09-12: value 2.9% for 2026-07, consistent with independently checked external estimates for the same period. **This series is only methodologically consistent from 2005 onward** — see Decisions Log #3. |
| `quarterly_gdp` | 735879 | GDP, constant 2018 pesos ("Valores a precios de 2018"), original series | Quarterly | Confirmed real (not nominal) by growth-rate sanity check: ~2.5x growth from 1980 to 2026 is consistent with ~2% average real annual growth, whereas nominal GDP would have grown by orders of magnitude given Mexico's historical high-inflation periods (1980s-1990s). |
| `cpi` | 910392 | INPC — General Index (Índice general, not subyacente/no subyacente), monthly, base 2018 | Monthly | Deliberately chose the level/index, not any pre-calculated inflation rate variant, so that inflation rates are computed in-house with a documented method (see Decisions Log #1). |

**Indicators explicitly rejected during series selection** (kept here so
we don't re-investigate them by mistake later):
- INEGI "Tasa de ocupación, desocupación..." **quarterly** variant — rejected in favor of the monthly version, for consistency with the project's monthly pipeline granularity.
- "Tasa de ocupación parcial y desocupación (TOPD1)" — a different, complementary indicator (partial underemployment + unemployment combined), not the standard unemployment rate.
- "Índice nacional de precios productor" (INPP) — producer prices, not consumer prices. Wrong indicator entirely.
- "Paridades de poder de compra... OCDE" — GDP cross-country PPP comparison tool, unrelated to this project.
- CPI "Subyacente" / "No subyacente" — core/non-core CPI variants. Not used in v0, but flagged as a strong candidate for a future monetary-policy-decision module (Banxico itself watches core CPI closely for rate decisions).
- Any pre-calculated "Inflación mensual / interanual / acumulada" or "Variación anual" GDP series — rejected in favor of raw levels, for the same reason as CPI above.
- "Incidencias" (CPI component-level contribution breakdown) — a decomposition by spending category, not the general index.

---

## 3. SHCP — Public Debt (SHRFSP, % of GDP)

**Status:** Manually updated, ~once per year. NOT part of the automated
cron pipeline — the source (presto.hacienda.gob.mx) is an interactive
JSP dashboard with no export button, static file, or API. Scripting it
would require full browser automation (Selenium/Playwright) disproportionate
to a once-a-year update — deliberately not pursued (see Decisions Log #8).

**Metric used:** Saldo Histórico de los Requerimientos Financieros del
Sector Público (SHRFSP) — the broad public debt measure, as %GDP
(SHCP's own calculation, base 2018 GDP). This is the correct metric per
the project's original scope (broad debt, not just central government).

### How to manually retrieve the data (repeat ~annually)

1. Go to https://www.finanzaspublicas.hacienda.gob.mx/
2. Click "Estadísticas Oportunas de Finanzas Públicas"
   → opens http://presto.hacienda.gob.mx/EstoporLayout/estadisticas.jsp
3. Click "Saldo Histórico de los Requerimientos Financieros del Sector
   Público" — a popup shows available files (currently one file
   covering 2000-2026).
4. Select:
   - Cuadro: **Saldo Multianual**
   - Cifras en: **Porcentajes del PIB**
   - Years: select full available range
5. Copy the resulting table (row "Saldo histórico de los RFSP", the
   aggregate, unqualified total — do NOT use the "Interno"/"Externo"
   or sector-specific sub-rows) into
   `data/raw/shcp_debt_pct_gdp_manual_{YYYY}.csv`.
6. Preserve the footnotes exactly as published:
   - n.d. = no disponible (not available)
   - n.s. = no significativo (not significant)
   - -o- = greater than 500 or less than -500 percent
   - Figures are preliminary for the most recent year shown.

**Data confirmed available:** 1990–2025 (2026 preliminary), annual.
Note this starts 2 years after the project's general historical window
(1988) — a minor, documented gap, not treated as an error.

---

## 4. World Bank Open Data API — Debt Fallback

**Access:** Free, no token required.
**Base URL:** `https://api.worldbank.org/v2/country/mx/indicator`
**Indicator:** `GC.DOD.TOTL.GD.ZS` — "Central government debt, total (% of GDP)".

**Role: freshness fallback / cross-check only — NEVER merged or
substituted with SHRFSP.** These are different metrics by definition:
SHRFSP is the broad measure (federal government + paraestatales +
development banking + trusts + historical bailouts like IPAB);
`GC.DOD.TOTL.GD.ZS` is central government only, a narrower scope. They
will systematically differ, and that difference is expected, not an
error. See Decisions Log #9 for how each is used.

**Trade-off accepted:** annual frequency, with typical publication lag
of 1-2 years (source is IMF/World Bank WDI, not real-time). Acceptable
here because public debt/GDP is a slow-moving stock variable, not a
high-frequency signal — losing monthly granularity costs little
information for this specific indicator.
---
---

## 5. Reporting Layer — Domain Fragility Scorecard & Composite Index

**Location:** `src/reporting/domains.py`, `composite_index.py`, `narrative.py`, `run_reporting.py`
**Output:** `data/processed/risk_scorecard.json`

### Domain taxonomy

| Domain | Series | In composite? |
|---|---|---|
| External stability | fx_rate_fix, international_reserves | Yes |
| Liquidity | m1, m2 | Yes |
| Rates & monetary policy | cetes_28d, target_rate | Yes |
| Real economy | quarterly_gdp, unemployment_rate | Yes |
| Prices | cpi | Yes |
| Fiscal solvency | debt_shrfsp_broad_pct_gdp | **No** — annual frequency provides no rolling-window trend statistics, and the fragility score is built exclusively from trend signals. Level context for debt is not currently surfaced in the scorecard at all (a known gap — see README Roadmap). |

### Domain fragility score (0–100)

Built **exclusively** from `ac1_trend_tau` and `variance_trend_tau` (and
the combined `critical_slowing_down_flag`), each counted only when
`flag_significant` is True — sign alone is never sufficient. This was
the subject of a real bug found during manual QA: the narrative
generator initially classified a trend as "consistent" based only on
the sign of both taus, which meant a statistically insignificant tau as
small as +0.017 was being treated identically to a strongly significant
+0.686. Fixed by requiring significance, not just sign, before
describing any trend as consistent — both in the composite score (which
was correct from the start) and in the narrative text (which was not,
until this fix).

The `critical_slowing_down_flag` counts double in the weighted score,
reflecting that it's the stronger, combined signal (both autocorrelation
and variance rising together), not just one trend statistic in
isolation.

**Score thresholds:**

| Score | Label |
|---|---|
| 0–33 | Sin cambios relevantes |
| 34–66 | Tendencia a monitorear |
| 67–100 | Señal fuerte de fragilidad |

### Composite index

Unweighted average of the 5 eligible domain scores. Equal weighting is
a deliberate, documented choice — no domain counts more just because it
happens to track more series (e.g. "Prices" has 1 series, "Liquidity"
has 2, but each contributes equally to the composite).

### Why the score is trend-only, never level-based

A domain score built from raw levels (z-scores, percentiles) would
require deciding, for every single indicator, whether a high or low
level represents *more* or *less* risk — and that judgment is often
genuinely ambiguous (is historically low unemployment reassuring, or a
sign of an overheating labor market that could itself be a leading risk
indicator?). Building the score exclusively from trend/stability signals
sidesteps this: "is this series becoming less stable over time" has an
unambiguous interpretation (higher = more fragile) regardless of the
domain or the direction economists would normally read into the level.
Level context is preserved and shown, but only in the narrative text,
where it can carry the necessary nuance in plain language rather than
being silently folded into a number.

### Narrative generation

Template-based, not free text — the same input statistics always
produce the same sentence, which keeps the output testable
(`tests/test_narrative.py` validates both grammar correctness and
substantive correctness against real, previously-verified production
data, not only synthetic fixtures).
---

## Decisions Log

Chronological record of methodological choices made during pipeline design,
independent of any single series.

1. **Original series over seasonally adjusted / pre-calculated rates**, across
   every source. Raw levels are stored in `data/raw`; any seasonal
   adjustment, growth rate, or index transformation is computed in
   `src/transform/`, using a documented, reproducible method — rather than
   depending on INEGI/Banxico's own (less transparent) adjustment
   methodology.

2. **Historical periodization uses six-year presidential terms (sexenios)
   as candidate structural break points**, not as an assumed axiom. Each
   sexenio boundary will be tested statistically (Chow test / Bai-Perron
   multiple breakpoint test) per series, rather than assumed a priori to
   represent a genuine regime change. This keeps the analysis empirically
   neutral rather than politically framed.

3. **Employment/informality data comparability limitation:** INEGI's ENOE
   survey only provides consistent, continuous monthly methodology from
   2005 onward. Prior surveys (ENEU 1985–2004, urban-only; ENE, sporadic
   before 2000) are not directly comparable. Historical window for this
   indicator is therefore effectively 2005–present, despite the project's
   general historical window starting in 1988. This limitation must be
   stated explicitly in any published analysis, not hidden.

4. **Exchange rate regime change (Dec 1994):** Mexico's peso was under a
   fixed/controlled exchange regime before the 1994 crisis and free-floating
   after. Any volatility analysis on the FX series must account for this
   as a genuine structural break, not an artifact.

5. **Reporting/pipeline architecture:** GitHub Actions (public repo — free,
   unlimited minutes) + data committed directly to the repo (versioned,
   auditable via git history) + GitHub Pages for the published dashboard.
   No cloud provider (Azure/AWS) is used for storage or compute at this
   stage — data volume is trivial (a handful of macro time series) and
   does not justify the added complexity or cost. Revisit only if the
   project later requires a dynamic backend or heavier compute.

6. **Git workflow:** trunk-based development (`main` + short-lived feature
   branches), not long-lived GitFlow-style dev/test/prod branches.
   Dev/test/prod separation is implemented via GitHub Environments
   (deployment targets + protection rules), not via permanent branches.

7. **Language convention:** all code, comments, docstrings, commit
   messages, and repository documentation are in English (international/
   remote hiring audience). Substack content remains in Spanish
   (Mexican audience).

8. **SHCP public debt is manually refreshed (~annual), not part of the
   automated cron.** The source (presto.hacienda.gob.mx) is an
   interactive dashboard without a stable static URL, export button, or
   API, making full automation disproportionate to a once-a-year update.
   This is a deliberate exception to the "fully automated pipeline"
   design goal — documented rather than hidden, and paired with an
   automated World Bank series as a lower-frequency, always-available
   fallback (see #9).

9. **Never merge or average the two public-debt metrics (SHRFSP vs.
   World Bank central-government debt).** They measure different scopes
   by definition and will systematically diverge — this is expected,
   not an inconsistency to reconcile. Each is stored and labeled as a
   distinct indicator (`debt_shrfsp_broad_pct_gdp` vs.
   `debt_central_gov_narrow_pct_gdp`). SHRFSP is the primary indicator
   used in the composite risk index. The World Bank series is used only
   to programmatically flag staleness (e.g., "SHRFSP last manually
   updated: [date] — over 14 months ago") — never as a substitute value.

10. **Monthly data refresh runs fully unattended — no manual approval
   gate.** An earlier iteration used a `production` GitHub Environment
   requiring manual approval before the job could run at all, which
   contradicted the actual goal (updates should complete without the
   maintainer's presence). The design was revised: automated tests
   (`pytest`) are the real safety gate — they run before the PR is
   opened, and again as a required status check before GitHub
   auto-merges it. This is a deliberate trade-off: full automation,
   backed by test coverage, instead of a human-in-the-loop approval
   that would defeat the point of automating the pipeline at all.

11. **The `since_last_break` reference window and its Chow-test-based
   structural break detection were retired from the production
   pipeline (2026-09-14).** Diagnosis: for most series, the "since last
   break" window anchored to the Sheinbaum administration's start
   (Oct 2024) or, in one case (quarterly_gdp), to AMLO's start
   (Dec 2018). Manual investigation of the latter revealed the true
   driver was the COVID-19 shock (which fell within the post-boundary
   segment), not the change of administration itself: re-running the
   Chow test at the actual COVID crash date (Apr 2020) produced a far
   stronger break (F=22.4, p=2.1e-9) than the Dec-2018 boundary
   (F=9.0, p=1.9e-4), and excluding COVID-period quarters from the
   post-boundary segment made the Dec-2018 break disappear entirely
   (F=0.23, p=0.80).

   Investigating whether the Sheinbaum boundary had the same problem
   led to a more fundamental finding: a placebo test — comparing the
   real boundary's F-statistic against F-statistics from 30 arbitrary
   control dates in the same series — showed the real boundary was
   NOT distinguishable from noise. For `target_rate`, the real
   boundary's F-statistic (217.3) ranked in only the 10th percentile
   of the placebo distribution; for `m2`, the 17th percentile — i.e.,
   most random dates produced a stronger apparent "break" than the
   actual sexenio boundary. Root cause: with a very long "before"
   segment (thousands of daily/monthly observations spanning 20-35
   non-linear years) fit to a single straight line, almost ANY recent
   cutoff date will appear to diverge from that line — not because
   that specific date is special, but because a straight line is a
   poor global model for decades of non-linear macro history. The
   Chow test implementation itself is correct; the error was applying
   it without first validating that the test is well-specified for
   this use case.

   Decision: `since_last_break` removed from `get_all_windows()` (the
   production window set). `structural_breaks.py` and
   `get_since_break_window()` are retained in the codebase, explicitly
   marked as research/reference material, not production-validated.
   `full_history` and `rolling_10y` are unaffected by this issue (they
   don't depend on searching for or testing a candidate break date)
   and remain the two production reference windows.

   This finding also prompted a reconsideration of the underlying
   question the project was trying to answer with structural breaks:
   rather than asking "did a break occur at this specific political
   boundary" (which conflates timing with attribution — e.g., COVID
   happened during AMLO's term but wasn't caused by his policies), a
   richer and better-specified question is "how did Mexico's economy
   behave, in terms of volatility and resilience, during each full
   sexenio, and how did that compare to external shocks of known,
   externally-measured magnitude (oil prices, global risk indices)
   during the same period." This reframing is documented as a future
   research direction in the README, not yet implemented.

12. **Domain fragility scores and narrative text require statistical
    significance, never sign alone, before describing a trend.** A bug
    was found where narrative.py classified trends as "consistent"
    based only on whether both `ac1_trend_tau` and `variance_trend_tau`
    were positive/negative, ignoring `flag_significant` entirely — a
    tau of +0.017 (noise) was described identically to a tau of +0.686
    (strong, highly significant). composite_index.py already applied
    this correctly; narrative.py did not, until fixed. Both modules now
    consistently require significance, not just sign.

13. **The composite fragility index and domain scores are built
    exclusively from trend/stability statistics (rolling autocorrelation
    and variance trends), never from level statistics (z-scores,
    percentiles).** This avoids having to encode, inside a single
    number, a domain-specific and often ambiguous judgment about
    whether a high or low level represents more or less risk. Level
    context is preserved only in the plain-language narrative text,
    where it can be explained with appropriate nuance.

14. **The public dashboard (GitHub Pages) requires no separate build or
    deploy step.** It's a single static `index.html` at the repo root
    that fetches `data/processed/risk_scorecard.json` directly at
    page-load time. Because the monthly automated pipeline already
    commits updated data to `main`, the live site reflects new data
    automatically on the next page load — publishing and data-freshness
    are the same event, by design.
15. **The dashboard and reporting layer support Spanish and English
   through a single source of truth per phrase, not two parallel
   systems.** Motivation: the project's audience includes international/
   remote-hiring recruiters (see README), who need to read the same
   content a Spanish-speaking user sees, not a separate, potentially
   inconsistent translation.

   **Design principle:** every user-facing string is computed once, in
   the same function call, from the same underlying numbers — never
   translated after the fact by a second, independent code path. In
   `src/reporting/domains.py` and `composite_index.py`, this means
   `display_name`, `description`, and score-band labels are stored as
   `{"es": ..., "en": ...}` dicts directly in the data structures
   (`DomainInfo`, `ScoreLabel`), rather than as separate `_en.py` files
   that could silently drift out of sync as the project grows. In
   `src/reporting/narrative.py`, a single `PHRASES` dict (keyed by
   language) supplies the building blocks for both languages'
   sentences, generated from the same statistics in the same call
   (`generate_series_narrative(..., lang="es")` and `lang="en"` always
   read the same `ac1_tau`/`var_tau`/`percentile` values — they can
   differ only in wording, never in substance).

   **Known language-specific details handled explicitly, not
   generically:** grammatical number can differ by language for the
   same series (e.g. CETES is phrased as a plural subject in Spanish —
   "los CETES... están" — but as a singular noun phrase in natural
   English — "the 28-day CETES rate is"), so `SERIES_DISPLAY_NAMES`
   stores `(name, is_plural)` per language, not a single shared flag.
   English percentile phrasing needs correct ordinal suffixes (the
   `_ordinal_en()` helper: "21st", "4th", with the 11–13 exception) —
   Spanish percentile phrasing doesn't need this at all, since
   "percentil 21" needs no suffix; treating this as a shared/generic
   formatting rule would have produced "the 21th percentile," a
   visible error to a native reader.

   **JSON output schema:** `risk_scorecard.json` carries `display_name`,
   `label`, `narrative`, and (once added, see #17) `narrative_stakeholder`
   as `{"es": ..., "en": ...}` objects (labels additionally carry a
   language-independent `status_id` — see #17 for why). The frontend
   (`index.html`) selects which key to render via a language toggle
   button, re-rendering from the same already-fetched JSON — no second
   network request, no separate English page to keep in sync.

   **Regression coverage:** `tests/test_domains.py` and
   `tests/test_composite_index.py` include tests that fail if a new
   domain, score band, or phrase is added with only one language
   filled in (`test_every_domain_has_both_languages`,
   `test_every_score_label_has_both_languages`), specifically to catch
   the kind of silent drift this single-source design is meant to
   prevent.

16. **Kendall's theoretical p-value, used throughout production for
   trend significance (`ac1_trend_tau`, `variance_trend_tau`,
   `critical_slowing_down_flag`), was found to have a massively
   inflated false-positive rate and was replaced with ARMA-surrogate
   significance testing.**

   **Diagnosis:** an audit generating ~150 random reference dates per
   series/window and computing Kendall's theoretical p-value at each
   found that "statistically significant" (p < 0.05) results occurred
   far more often than the nominal 5% false-positive rate the test
   claims — ranging from 40% (`m1`, rolling_10y) to **98%**
   (`target_rate`, full_history), across every series and window
   tested. Root cause: `ac1_trend_tau`/`variance_trend_tau` test for a
   trend in a *derived, already-smoothed* rolling statistic (rolling
   autocorrelation/variance), not in raw data. Adjacent points of a
   rolling-window statistic mechanically share most of their
   underlying data, violating the independence assumption behind
   Kendall's asymptotic p-value — a problem long documented in the
   hydrology trend-detection literature:

   > Yue, S., Pilon, P., Phinney, B., & Cavadias, G. (2002). The
   > influence of autocorrelation on the ability to detect trend in
   > hydrological series. *Hydrological Processes*, 16(9), 1807-1829.

   An initial attempt to fix this with an empirical placebo test
   (comparing the real trend statistic against statistics computed at
   real historical control dates — the same technique already used to
   retire `since_last_break`, see #11) also failed: real historical
   dates aren't a valid null distribution, because real economic
   history has its own genuine dynamics (past volatility episodes,
   cycles) and isn't noise. This was confirmed by generating 500
   control dates for `fx_rate_fix`: 57.7% of them showed
   `|tau| > 0.9`, showing near-perfect monotonic trends are *common*,
   not rare, in this series' history — control dates showed the same
   inflation as crisis dates.

   **Fix:** adopted the field's own reference methodology instead of
   further ad hoc correction:

   > Dakos, V., Carpenter, S. R., Brock, W. A., Ellison, A. M.,
   > Guttal, V., Ives, A. R., Kéfi, S., Livina, V., Seekell, D. A.,
   > van Nes, E. H., & Scheffer, M. (2012). Methods for Detecting
   > Early Warnings of Critical Transitions in Time Series Illustrated
   > Using Simulated Ecological Data. *PLOS ONE*, 7(7), e41010.

   Implemented in `src/analysis/surrogates.py`: detrend the raw series
   (Gaussian kernel smoother), fit a fixed-order ARMA(1,1) model to the
   residuals, generate 200 synthetic surrogate series sharing the same
   short-term correlation structure but with no systematic trend by
   construction, run the identical rolling-stat + Kendall's tau
   pipeline on each surrogate, and derive an empirical p-value via the
   Phipson & Smyth (2010) correction (`p = (b+1)/(m+1)`, avoiding the
   impossible p=0 result a naive percentile calculation would give):

   > Phipson, B., & Smyth, G. K. (2010). Permutation P-values Should
   > Never Be Zero: Calculating Exact P-values When Permutations Are
   > Randomly Drawn. *Statistical Applications in Genetics and
   > Molecular Biology*, 9(1), Article 39.

   `n_surrogates=200` (not Dakos et al.'s 1,000) is a documented
   cost/benefit tradeoff — the minimum possible p-value with 200
   surrogates (~0.005) remains comfortably below the 0.05 threshold
   after FDR correction, and 1,000 surrogates × 9 series × 2 windows ×
   2 stats was judged too slow for routine monthly-cron execution.

   **Measured impact:** re-running the full pipeline with the
   corrected method dropped the composite fragility index from
   **62.9 ("Tendencia a monitorear") to 12.7 ("Sin cambios
   relevantes")**, and the count of statistically significant flags in
   `analysis_results.csv` from 66 to 26 — with the reduction
   concentrated specifically in `ac1_trend_tau`/`variance_trend_tau`/
   `critical_slowing_down_flag` rows, not in the unrelated descriptive
   statistics (z-score, skewness, etc.), confirming the fix targeted
   the actual broken component. The version of the public dashboard
   showing 62.9 was live and incorrect; this is documented rather than
   quietly corrected, consistent with this project's ongoing practice
   of disclosing its own errors (see #11).

17. **`is_csd_active()` (`src/reporting/composite_index.py`) is now the
   single source of truth for whether the combined critical-slowing-
   down signal is active — decided only from the post-FDR-correction
   significance of the two individual trend stats, never from
   `critical_slowing_down_flag`'s own `value` column.** That column is
   computed in `early_warning.py` *before* the batch-wide FDR
   correction exists (which only runs later, in `run_analysis.py`), so
   it could disagree with the corrected result. Found in production
   2026-09-16: `cetes_28d`/`full_history` had `critical_slowing_down_flag
   = 1.0` (pre-correction), while neither individual stat survived FDR
   — the domain score was counting a signal the corrected statistics
   didn't actually support, and the narrative correctly said "no
   significant trend" while the score silently counted it anyway. Same
   root-cause pattern as #12 (deciding significance from an
   uncorrected source instead of the batch-corrected one), recurring
   one layer deeper in the pipeline than where it was first fixed.

18. **`generate_series_narrative()` now selects between `rolling_10y`
   and `full_history` per series, instead of always describing
   `rolling_10y`.** The domain fragility score (`compute_domain_
   fragility_score()`) has always considered both windows, but the
   narrative text only ever described one — for a series where a
   signal exists only in `full_history` (found in production for `m1`:
   full_history showed a significant combined CSD flag, rolling_10y
   did not), the score and the narrative silently told different
   stories. Fix: if `rolling_10y` shows no CSD signal but
   `full_history` does, the narrative switches to `full_history` and
   says so explicitly ("esta señal aparece al ver la historia
   completa, no en la última década por sí sola"), keeping the score
   and its explanation consistent.

19. **Backtest against known historical crises (2008-09, 2014-16 oil,
   1994 Tequila), using the corrected surrogate method, found NO
   statistically significant combined CSD signal in any of the three
   episodes, in any of the available series, after Benjamini-Hochberg
   correction.** Some individual indicators came close in isolation
   (e.g. `fx_rate_fix` ac1 in 2008: p=0.05 before correction; `fx_rate_fix`
   in 1994: tau≈1.0 but p=0.09), but none cleared both the individual
   significance bar and the paired (AC1 + variance) requirement.

   This null result is consistent with, not contradicted by, the
   existing literature on CSD applied to financial crises — Diks et
   al. (2019) found evidence of critical slowing down before Black
   Monday (1987) but mixed/non-significant results for the Asian
   crisis (1997), the dot-com crash (2000), and the 2008 crisis. Two
   design bugs were found and fixed during this backtest before
   reaching this result, both now covered by regression tests
   (`tests/test_backtest.py`): (a) an early version tested for a trend
   across the *entire* available pre-crisis history (e.g. 17 years for
   `fx_rate_fix` in 2008) instead of a recent lookback window,
   answering "was there ever a trend" rather than "was there a recent
   destabilization" — fixed by trimming to `window +
   BACKTEST_LOOKBACK_TARGET_POINTS` (24) raw points before the crisis
   date; (b) Benjamini-Hochberg correction across the full batch of
   backtest p-values was accidentally omitted when `backtest.py` was
   simplified to call `surrogate_trend_test()` directly — added back
   via `add_significance()`.

   **Implication:** per the project's own decision criterion (if the
   agnostic CSD approach shows real detection capability, keep
   refining it; if not, prioritize the crisis-type-specific "dirigido"
   system — see the domain-literature-mapping discussion), this null
   result across all three testable episodes is evidence to prioritize
   building the directed, crisis-type-specific detection layer (the 7
   crisis-type groups with dedicated literature-backed variables) over
   further investment in the agnostic layer's current design.

20. **ARMA order selection for CSD surrogates was migrated from a fixed,
   undefended ARMA(1,1) to an AICc-based adaptive search — sample-size
   scaled, not applied blindly to every series alike.**

   The original `(1,1)` default (see #16) was never validated against
   any series-specific evidence. Two candidate fixes were considered
   and one was rejected before landing on the final design:

   - **Rejected: Schwert's (1989) rule** for maximum lag length
     (`12*(T/100)^0.25`) — designed specifically for augmented
     Dickey-Fuller unit-root test lag selection, not general ARMA
     order selection. Applying it directly would have suggested
     absurd orders for small samples (e.g., order 9 for this
     project's 41-observation quarterly GDP series) — the same class
     of cross-context tool misapplication already caught in this
     project's Chow-test (#11) and SOC-vs-critical-transitions
     episodes.
   - **Adopted:** `max_arma_order_for_sample(n)` caps the AICc grid
     search at `min(5, n // 15)` — a conservative, sample-size-aware
     heuristic (not attributed to one canonical source), combined
     with a global practicality ceiling of 5. AICc (not plain AIC) is
     used for the comparison, correcting for small-sample bias
     (Hurvich, C. M., & Tsai, C.-L. (1989). Regression and time series
     model selection in small samples. *Biometrika*, 76(2), 297-307).
     Ljung-Box adequacy lags are similarly sample-size-scaled via
     `h = min(10, T/5)`, following Hyndman's own 2023 revision of his
     earlier fixed h=10 rule (Hyndman & Athanasopoulos, 2018), after a
     power-simulation study showed the fixed version performs poorly
     for small T (https://robjhyndman.com/hyndsight/ljung-box-test/).

   **Measured impact:** re-running the full pipeline with adaptive
   order selection moved the composite index from 12.7 to **11.4**.
   The driver: `international_reserves`'s partial trend signal (one
   of two indicators significant) disappeared once the correctly
   selected order replaced the fixed `(1,1)` — the "Estabilidad
   externa" domain score dropped from 12.5 to 6.2 as a direct result.
   This confirms the fixed order was materially affecting conclusions,
   not just a cosmetic simplification.

   **M1's ARMA(4,5) selection was independently validated, not assumed
   correct by default:** its selected order landed at the search
   ceiling (`max_arma_order_for_sample(121) = 5`), which could indicate
   either a genuinely richer short-term structure or overfitting at
   the boundary of the search space. Comparison against a simple
   ARMA(1,1): AICc difference of **-12.34** in favor of (4,5) (well
   above the ~2-point threshold conventionally used to distinguish a
   real improvement from noise), and Ljung-Box on the (4,5) residuals
   passed cleanly (p=0.95). The added complexity is genuinely
   justified for this series, not an artifact of a wide search grid —
   though note the selected order sits exactly at the adaptive cap,
   so a higher true order cannot be ruled out; not pursued further.

21. **GARCH(1,1) conditional-volatility trend comparison against CSD's
   variance signal was implemented and run — addressing the open
   limitation noted since the project's methodology was first written
   (rising variance is exactly what GARCH models, Engle 1982;
   Bollerslev 1986, were built to capture, and this had never been
   tested until now).**

   Design: the same AICc-selected ARMA order used for CSD surrogates
   (#20) is fit first to pre-whiten each series' mean structure, then
   GARCH(1,1) with `mean="Zero"` is fit to the ARMA residuals — this
   two-step design was adopted after an earlier `mean="AR", lags=1`
   approach produced degenerate persistence estimates (pinned at 1.0)
   by forcing unexplained mean structure into the variance equation.
   Significance of the conditional-volatility trend uses the same
   Phipson & Smyth (2010) empirical p-value approach as CSD, but with
   the null distribution generated from the FITTED GARCH model's own
   native simulator (synthetic, trend-free by construction), not
   borrowed ARMA surrogates.

   **On `full_history`:** persistence (α+β) was pinned at ~1.000 for 5
   of 9 series, with an `InitialValueWarning` confirming a
   misspecified, non-stationary fit. Diagnosed via Lamoureux & Lastrapes
   (1990, *Journal of Business & Economic Statistics*, 8(2), 225-234):
   fitting a single GARCH model across a sample that spans genuine
   regime changes (fixed vs. floating exchange rate, 1994, 2008, COVID)
   mechanically inflates apparent persistence — the same root-cause
   pattern as the Chow-test misspecification in #11, recurring in a
   different model class.

   **On `rolling_10y` (the reliable comparison):** among series with
   non-degenerate fits, GARCH and CSD's `variance_trend_tau` agreed on
   3 of 4 clean cases (target_rate, international_reserves,
   unemployment_rate all agreed "no rising trend"; `cetes_28d` was the
   one genuine disagreement — GARCH flagged rising volatility, CSD did
   not). `cpi` failed to converge with **α pinned at exactly 0** (a
   corner solution, not an error) under two independent mean
   specifications (`mean="AR",lags=1` and the AICc-selected ARMA(1,1))
   — a robust finding: no ARCH effect exists beyond INPC's own
   short-term mean structure. `m1` and `quarterly_gdp` also failed to
   converge (insufficient sample/complexity mismatch).

22. **GARCH was cross-validated against the same pre-crisis backtest
   windows used for CSD (2008-09, 2014-16, 1994 Tequila) — result: 0
   of 4 valid comparisons significant after Benjamini-Hochberg
   correction, consistent with CSD's own null backtest result (#19),
   not contradicting it.**

   `fx_rate_fix` (1994 Tequila) showed a promising raw p-value of
   0.0255 before correction; after batching with the other 3 valid
   comparisons and applying BH, it rose to 0.102 — the same discipline
   (never decide significance before batch correction) that has
   already been enforced elsewhere in this project (#12, #17).

   **16 of 20 combinations (80%) failed to converge**, overwhelmingly
   with the "alpha pinned at 0" corner solution. This is not an
   implementation defect — it is a well-documented, precisely
   quantified small-sample limitation of GARCH maximum-likelihood
   estimation:

   > Hwang, S., & Valls Pereira, P. L. (2006). Small sample properties
   > of GARCH estimates and persistence. *The European Journal of
   > Finance*, 12(6-7), 473-494.

   Their finding: at least 250 observations are needed for a reliable
   ARCH(1) fit, and 500 for GARCH(1,1); below that, estimates are
   negatively biased and convergence under Bollerslev's non-negativity
   constraints frequently fails outright. This project's backtest
   windows (32-528 observations, most well under 200) are
   overwhelmingly below this threshold — explaining, with one external,
   independently-derived cause, both this backtest's convergence
   failures AND the earlier `rolling_10y` failures for `m1` and `cpi`
   (121 observations, also below the ARCH(1) minimum of 250).

   **Conclusion:** GARCH(1,1), as implemented here, is not a suitable
   tool for short-window (pre-crisis backtest style) analysis of
   Mexican macroeconomic series, given realistic data availability —
   a genuine, literature-grounded methodological finding, not a
   failure to be patched further. It remains usable, with caveats, on
   `rolling_10y`-length windows for series with sufficient observations
   (daily/weekly series comfortably clear the threshold; most monthly
   and all quarterly series in this project's panel do not).
   **GARCH is not integrated into the production pipeline** — its role
   remains strictly as a cross-validation exercise against CSD,
   documented here and in `METHODOLOGY.md`, not as a second production
   signal.

23. **Warning suppression (`src/analysis/_quiet_warnings.py`) filters
   ONLY four specific, individually diagnosed benign warning messages
   by exact text match, not by broad category or source module** —
   deliberately, to avoid hiding a future, genuinely new warning that
   might signal a real problem (the same instinct that surfaced the
   `cpi` alpha=0 corner solution and the M1 ARMA(4,5) boundary case).
   Imported once, for its side effect, at the top of each runnable
   entry point (`run_analysis.py`, `run_backtest.py`,
   `run_garch_comparison.py`).

24. **`src/analysis/run_backtest.py` was added as a proper runnable
   entry point**, matching the `python3 -m src.analysis.run_X` pattern
   already used by `run_analysis.py`, `run_reporting.py`, and
   `run_garch_comparison.py`. `backtest.py` itself never had one —
   it was always invoked via an inline `python3 -c "..."` snippet, an
   inconsistency found and fixed 2026-09-17.
---

## Appendix: Confirmed Data Ranges (as of first successful pull, 2026-09-12)

| Source | Series/Indicator | Confirmed range | Observations |
|---|---|---|---|
| Banxico | SF43718 (FX FIX) | 1991-11 to 2026-09 | 8,756 (daily) |
| Banxico | SF60633 (CETES 28d) | 2006-09 to 2026-09 | 1,043 (weekly) |
| Banxico | SF61745 (target rate) | 2008-01 to 2026-09 | 6,714 (daily) |
| Banxico | SF43707 (reserves) | 1995-12 to 2026-09 | 1,602 (weekly) |
| Banxico | SF311408 (M1) | 2000-12 to 2026-07 | 308 (monthly) |
| Banxico | SF311418 (M2) | 2000-12 to 2026-07 | 308 (monthly) |
| INEGI | 735879 (quarterly GDP) | 1980-Q1 to 2026-Q2 | 186 (quarterly) |
| INEGI | 910392 (CPI) | 1969-01 to 2026-08 | 692 (monthly) |
| INEGI | 444603 (unemployment) | 2005-01 to 2026-07 | 259 (monthly) — confirms documented ENOE comparability limitation |
| SHCP | SHRFSP (%GDP) | 1990 to 2025 (2026 preliminary) | annual, manual |