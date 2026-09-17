"""
src/analysis/backtest.py

Backtests the CSD (critical slowing down) early-warning signal against
known historical Mexican economic crises: does the rolling
autocorrelation/variance trend show a distinguishable pre-crisis
pattern, compared to a placebo distribution of control windows from
calm periods?

Design notes:
  - Window B (how many pre-crisis points feed the Kendall trend test)
    is measured in POINTS of the already-computed rolling stat series,
    not calendar months — frequency-agnostic.
  - Debt is excluded: annual frequency has no rolling stat to backtest.
  - Significance is empirical, not from Kendall's theoretical p-value:
    the rolling-stat series is itself autocorrelated by construction
    (adjacent windows share most of their underlying points), which
    violates the independence assumption behind Kendall's own p-value
    and can make even a placebo control look artificially "perfect"
    (tau = ±1.0) over a short window. Instead, each real pre-crisis tau
    is compared against a placebo distribution of control-period taus,
    using the corrected permutation p-value formula from Phipson &
    Smyth (2010) — p = (b+1)/(m+1), where b = number of controls at
    least as extreme as the real value — which avoids the impossible
    p=0 result a naive percentile-to-p-value conversion would give.
  - All p-values from the full batch (every series x crisis x stat)
    are corrected together with Benjamini-Hochberg before anything is
    called "significant" — same discipline used throughout this
    project's production pipeline.
"""

from dataclasses import dataclass, field

import numpy as np
import pandas as pd
from statsmodels.stats.multitest import multipletests

from src.analysis.early_warning import (
    rolling_autocorr_lag1,
    rolling_variance,
    kendall_trend_test,
    infer_rolling_window_periods,
)

WINDOW_B_TARGET_POINTS = 24
WINDOW_B_MIN_POINTS = 12
CONTROL_WINDOW_BUFFER_MONTHS = 12
N_CONTROL_WINDOWS = 500
RANDOM_SEED = 42

ALL_NINE_SERIES = [
    "fx_rate_fix", "cetes_28d", "target_rate", "international_reserves",
    "m1", "m2", "quarterly_gdp", "unemployment_rate", "cpi",
]

KNOWN_CRISES = {
    "2008_financial_crisis": {
        "date": pd.Timestamp("2008-09-01"),
        "series": ALL_NINE_SERIES,
    },
    "2014_oil_collapse": {
        "date": pd.Timestamp("2014-06-01"),
        "series": ALL_NINE_SERIES,
    },
    "1994_tequila": {
        "date": pd.Timestamp("1994-12-01"),
        "series": ["fx_rate_fix", "quarterly_gdp", "cpi"],  # partial coverage, documented
    },
}

ALL_CRISIS_DATES = [c["date"] for c in KNOWN_CRISES.values()]


@dataclass
class BacktestResult:
    crisis_name: str
    series_key: str
    skipped: bool
    skip_reason: str | None = None
    n_points: int = 0
    ac1_tau: float | None = None
    ac1_p_empirical: float | None = None
    var_tau: float | None = None
    var_p_empirical: float | None = None
    n_controls_used: int = 0


def get_pre_window(rolling_stat: pd.Series, anchor_date: pd.Timestamp, target_points: int = WINDOW_B_TARGET_POINTS) -> pd.Series:
    """Last `target_points` observations of an already-computed rolling
    stat series, strictly before anchor_date. Point-based, not
    calendar-based — adapts automatically to series frequency."""
    pre = rolling_stat[rolling_stat.index < anchor_date].dropna()
    return pre.tail(target_points)


def empirical_p_value_rising(real_tau: float, control_taus: list[float]) -> float:
    """
    One-sided empirical p-value for 'is the real tau unusually HIGH
    (rising) compared to control periods', using the Phipson & Smyth
    (2010) correction: p = (b+1)/(m+1), b = controls at least as
    extreme as the real value, m = total controls. Never returns
    exactly 0, unlike a naive percentile-based calculation.
    """
    if not control_taus:
        return np.nan
    b = sum(1 for t in control_taus if t >= real_tau)
    m = len(control_taus)
    return (b + 1) / (m + 1)


def _trend_at_anchor(raw_series: pd.Series, anchor_date: pd.Timestamp, window: int) -> dict | None:
    ac1_series = rolling_autocorr_lag1(raw_series, window=window)
    var_series = rolling_variance(raw_series, window=window)

    ac1_pre = get_pre_window(ac1_series, anchor_date)
    var_pre = get_pre_window(var_series, anchor_date)

    n_points = min(len(ac1_pre), len(var_pre))
    if n_points < WINDOW_B_MIN_POINTS:
        return None

    ac1_trend = kendall_trend_test(ac1_pre)
    var_trend = kendall_trend_test(var_pre)
    return {"n_points": n_points, "ac1_tau": ac1_trend["tau"], "var_tau": var_trend["tau"]}


def generate_control_dates(
    raw_series: pd.Series,
    exclude_dates: list[pd.Timestamp],
    n_controls: int = N_CONTROL_WINDOWS,
    buffer_months: int = CONTROL_WINDOW_BUFFER_MONTHS,
    seed: int = RANDOM_SEED,
) -> list[pd.Timestamp]:
    """Candidate anchor dates from calm periods only — excludes any
    date within `buffer_months` of a known crisis."""
    rng = np.random.default_rng(seed)
    valid_dates = raw_series.dropna().index
    if len(valid_dates) == 0:
        return []

    candidates = pd.date_range(valid_dates.min(), valid_dates.max(), freq="MS")

    def too_close(d):
        return any(abs((d - c).days) < buffer_months * 30 for c in exclude_dates)

    candidates = [d for d in candidates if not too_close(d)]
    n = min(n_controls, len(candidates))
    if n == 0:
        return []
    chosen = rng.choice(len(candidates), size=n, replace=False)
    return sorted(candidates[i] for i in chosen)


def backtest_series(raw_series: pd.Series, crisis_name: str, series_key: str) -> BacktestResult:
    crisis_date = KNOWN_CRISES[crisis_name]["date"]
    window = infer_rolling_window_periods(raw_series)

    if window is None:
        return BacktestResult(
            crisis_name, series_key, skipped=True,
            skip_reason="annual or unrecognized frequency — no rolling stat possible",
        )

    real = _trend_at_anchor(raw_series, crisis_date, window)
    if real is None:
        return BacktestResult(
            crisis_name, series_key, skipped=True,
            skip_reason=f"fewer than {WINDOW_B_MIN_POINTS} pre-crisis points available",
        )

    control_dates = generate_control_dates(raw_series, ALL_CRISIS_DATES)
    control_results = [_trend_at_anchor(raw_series, d, window) for d in control_dates]
    control_results = [r for r in control_results if r is not None]

    ac1_controls = [r["ac1_tau"] for r in control_results]
    var_controls = [r["var_tau"] for r in control_results]

    return BacktestResult(
        crisis_name, series_key, skipped=False,
        n_points=real["n_points"],
        ac1_tau=real["ac1_tau"],
        ac1_p_empirical=empirical_p_value_rising(real["ac1_tau"], ac1_controls),
        var_tau=real["var_tau"],
        var_p_empirical=empirical_p_value_rising(real["var_tau"], var_controls),
        n_controls_used=len(control_results),
    )


def add_significance(results_df: pd.DataFrame, alpha: float = 0.05) -> pd.DataFrame:
    """
    Applies Benjamini-Hochberg FDR correction across the ENTIRE batch
    of empirical p-values (every series x crisis x stat combination at
    once) — never per row in isolation. Adds adjusted p-values and a
    combined 'flag' column: True only if BOTH ac1 and variance are
    significantly rising after correction (same combined-signal logic
    as the production critical_slowing_down_flag).
    """
    results_df = results_df.copy()
    results_df["ac1_p_adjusted"] = np.nan
    results_df["var_p_adjusted"] = np.nan
    results_df["flag"] = False

    valid = results_df["ac1_p_empirical"].notna() & results_df["var_p_empirical"].notna()
    if valid.sum() == 0:
        return results_df

    combined_p = pd.concat([
        results_df.loc[valid, "ac1_p_empirical"],
        results_df.loc[valid, "var_p_empirical"],
    ], ignore_index=False)

    _, p_adj, _, _ = multipletests(combined_p, alpha=alpha, method="fdr_bh")

    n_valid = valid.sum()
    results_df.loc[valid, "ac1_p_adjusted"] = p_adj[:n_valid]
    results_df.loc[valid, "var_p_adjusted"] = p_adj[n_valid:]

    results_df.loc[valid, "flag"] = (
        (results_df.loc[valid, "ac1_p_adjusted"] < alpha)
        & (results_df.loc[valid, "var_p_adjusted"] < alpha)
        & (results_df.loc[valid, "ac1_tau"] > 0)
        & (results_df.loc[valid, "var_tau"] > 0)
    )
    return results_df


def run_backtest(panel_long: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for crisis_name, config in KNOWN_CRISES.items():
        for series_key in config["series"]:
            raw = (
                panel_long[panel_long["series_key"] == series_key]
                .dropna(subset=["value"])
                .sort_values("date")
                .set_index("date")["value"]
            )
            result = backtest_series(raw, crisis_name, series_key)
            rows.append(vars(result))
    df = pd.DataFrame(rows)
    return add_significance(df)