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
| `unemployment_rate` | 444603 | National unemployment rate (Tasa de desocupación), population 15+, original series | Monthly | Sourced from ENOE. Confirmed via test query 2026-09-12: value 2.9% for 2026-07, consistent with independently checked external estimates for the same period. **This series is only methodologically consistent from 2005 onward** — see Comparability Limitations below. |
| `quarterly_gdp` | 735879 | GDP, constant 2018 pesos ("Valores a precios de 2018"), original series | Quarterly | Confirmed real (not nominal) by growth-rate sanity check: ~2.5x growth from 1980 to 2026 is consistent with ~2% average real annual growth, whereas nominal GDP would have grown by orders of magnitude given Mexico's historical high-inflation periods (1980s-1990s). |
| `cpi` | 910392 | INPC — General Index (Índice general, not subyacente/no subyacente), monthly, base 2018 | Monthly | Deliberately chose the level/index, not any pre-calculated inflation rate variant, so that inflation rates are computed in-house with a documented method (see Decisions Log). |

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

## 3. SHCP (Public Debt / GDP)

**Status:** Not yet implemented.
**Access:** No formal REST API. Data is published as downloadable Excel/CSV
files under "Estadísticas Oportunas de Finanzas Públicas." Ingestion will
require direct file download + parsing rather than a standard API client.
**Note:** This module will need more manual maintenance than the Banxico/
INEGI ingestors, since source file structure/URLs may change without a
versioned API contract.

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