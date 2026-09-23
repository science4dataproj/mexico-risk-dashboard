"""
src/transform/derived_series.py

Derived (computed, not directly ingested) series — variables built
from combinations of already-cleaned series in panel_long.csv, rather
than pulled fresh from Banxico/INEGI.
"""

import pandas as pd


def compute_m2_reserves_ratio(panel_long: pd.DataFrame) -> pd.Series:
    """
    M2 / international reserves — the single best-performing leading
    indicator for currency crises identified by Kaminsky, Lizondo &
    Reinhart (1998), never previously computed in this project despite
    both inputs (m1... m2, international_reserves) being available
    since the panel's earliest data engineering (see SERIES_METADATA.md
    Decisions Log).

    Frequency reconciliation: M2 is monthly (Banxico SF311418);
    reserves is weekly (SF43707). Both are grouped by calendar
    year-month from their own native date stamps (not resampled by a
    fixed date label), taking the LAST reading of each series within
    that month — an end-of-period stock convention, consistent with
    how M2 itself is reported. This avoids assuming both series share
    the same day-of-month labeling convention.

    Coverage limitation, stated explicitly: M2 begins 2000-12, so this
    ratio CANNOT be computed for the 1994 Tequila crisis at all —
    despite that being the canonical currency-crisis case this
    indicator is meant to detect. Only testable against 2008-09 and
    2014-16 in this project's backtest.
    """
    m2 = panel_long[panel_long.series_key == "m2"].dropna(subset=["value"]).sort_values("date").copy()
    reserves = panel_long[panel_long.series_key == "international_reserves"].dropna(subset=["value"]).sort_values("date").copy()

    m2["period"] = m2["date"].dt.to_period("M")
    reserves["period"] = reserves["date"].dt.to_period("M")

    m2_monthly = m2.drop_duplicates("period", keep="last").set_index("period")["value"]
    reserves_monthly = reserves.groupby("period")["value"].last()

    merged = pd.DataFrame({"m2": m2_monthly, "reserves": reserves_monthly}).dropna()
    ratio = (merged["m2"] / merged["reserves"]).sort_index()
    ratio.index = ratio.index.to_timestamp()
    return ratio