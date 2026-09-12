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