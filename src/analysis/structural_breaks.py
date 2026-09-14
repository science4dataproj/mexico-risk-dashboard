"""
src/analysis/structural_breaks.py

Tests whether sexenio (Mexican presidential term) boundaries correspond
to genuine structural breaks in each time series, using the Chow test.
Boundaries are NEVER assumed to be breaks by default (see
SERIES_METADATA.md, Decisions Log #2) — each is tested statistically,
per series, independently.

This module also identifies the most recent significant break per
series, which src/analysis/windows.py uses to build the "since last
break" rolling window.
"""

import numpy as np
import pandas as pd
import statsmodels.api as sm
from scipy import stats as scipy_stats
from statsmodels.stats.multitest import multipletests

# Sexenio (6-year presidential term) start dates covering the project's
# historical window. The Sheinbaum entry starts Oct 1, not Dec 1,
# reflecting the 2024 constitutional change that moved the presidential
# inauguration date.
SEXENIO_BOUNDARIES = {
    "Salinas": pd.Timestamp("1988-12-01"),
    "Zedillo": pd.Timestamp("1994-12-01"),
    "Fox": pd.Timestamp("2000-12-01"),
    "Calderon": pd.Timestamp("2006-12-01"),
    "Pena_Nieto": pd.Timestamp("2012-12-01"),
    "AMLO": pd.Timestamp("2018-12-01"),
    "Sheinbaum": pd.Timestamp("2024-10-01"),
}

# Minimum observations required on EACH side of a candidate break for
# the test to be considered valid — too few points on either side makes
# the OLS fit unreliable regardless of what the F-test says.
MIN_OBS_PER_SEGMENT = 8


def chow_test(series: pd.Series, break_date: pd.Timestamp) -> dict | None:
    """
    Runs a Chow test for a structural break at `break_date` on a single
    time series indexed by date.

    H0: one linear trend fits the whole series equally well on both
        sides of break_date.
    H1: the trend (level and/or slope) differs before vs. after.

    Returns:
        dict with {f_stat, p_value, n_before, n_after}, or None if
        there isn't enough data on either side to test reliably.
    """
    series = series.dropna().sort_index()
    before = series[series.index < break_date]
    after = series[series.index >= break_date]

    if len(before) < MIN_OBS_PER_SEGMENT or len(after) < MIN_OBS_PER_SEGMENT:
        return None

    def _fit_ols(sub_series: pd.Series):
        t = np.arange(len(sub_series))
        X = sm.add_constant(t)
        return sm.OLS(sub_series.values, X).fit()

    full_t = np.arange(len(series))
    pooled = sm.OLS(series.values, sm.add_constant(full_t)).fit()
    rss_pooled = pooled.ssr

    model_before = _fit_ols(before)
    model_after = _fit_ols(after)
    rss_split = model_before.ssr + model_after.ssr

    k = 2  # intercept + slope, per segment
    n = len(series)
    denominator = rss_split / (n - 2 * k)
    if denominator == 0:
        return None

    f_stat = ((rss_pooled - rss_split) / k) / denominator
    p_value = 1 - scipy_stats.f.cdf(f_stat, k, n - 2 * k)

    return {
        "f_stat": f_stat,
        "p_value": p_value,
        "n_before": len(before),
        "n_after": len(after),
    }


def test_all_boundaries(series: pd.Series, alpha: float = 0.05) -> pd.DataFrame:
    """
    Tests every sexenio boundary against a single series, applying a
    Benjamini-Hochberg correction across all boundaries tested for that
    series (multiple hypotheses on the same data).

    Returns:
        DataFrame: sexenio, break_date, f_stat, p_value,
        p_value_adjusted, significant.
    """
    results = []
    for sexenio_name, break_date in SEXENIO_BOUNDARIES.items():
        result = chow_test(series, break_date)
        if result is not None:
            results.append({"sexenio": sexenio_name, "break_date": break_date, **result})

    columns = ["sexenio", "break_date", "f_stat", "p_value", "p_value_adjusted", "significant"]
    if not results:
        return pd.DataFrame(columns=columns)

    df = pd.DataFrame(results)
    rejected, p_adjusted, _, _ = multipletests(df["p_value"], alpha=alpha, method="fdr_bh")
    df["p_value_adjusted"] = p_adjusted
    df["significant"] = rejected
    return df.sort_values("break_date").reset_index(drop=True)[columns]


def most_recent_significant_break(series: pd.Series, alpha: float = 0.05) -> pd.Timestamp | None:
    """
    Returns the most recent sexenio boundary that tests as a
    significant structural break for this series, or None if no
    boundary is significant. This is what windows.py will call to
    build the "since last break" window.
    """
    results = test_all_boundaries(series, alpha=alpha)
    significant = results[results["significant"]]
    if significant.empty:
        return None
    return significant.sort_values("break_date").iloc[-1]["break_date"]