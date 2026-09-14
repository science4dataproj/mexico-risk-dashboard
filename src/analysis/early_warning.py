"""
src/analysis/early_warning.py

Implements "critical slowing down" detection: the empirical finding
(from complex-systems/resilience literature — e.g. Scheffer et al. on
early-warning signals for critical transitions) that systems approaching
a regime shift often show RISING autocorrelation and RISING variance in
the period beforehand — the system takes longer to "bounce back" from
small perturbations.

This is conceptually different from the z-score anomaly detection in
descriptive.py: that asks "is the current LEVEL unusual?"; this asks
"is the system becoming structurally more fragile over time?" — a
trend-based signal, not a point-in-time one.

Design note on statistical method: trend significance is assessed with
Kendall's tau (a nonparametric rank-correlation test against time),
NOT bootstrap. The rolling autocorrelation/variance series are built
from overlapping windows, so consecutive values are mechanically
correlated with each other — an i.i.d. bootstrap resample would violate
that structure and give a misleadingly narrow (or wide) interval.
Kendall's tau's own p-value is used directly instead.
"""

import numpy as np
import pandas as pd
from scipy import stats as scipy_stats

from src.analysis.windows import WindowResult

EWS_ROLLING_WINDOW = 24  # ~2 years of monthly data per rolling AC1/variance estimate
MIN_ROLLING_POINTS_FOR_TREND = 12  # need enough rolling estimates to test a trend on them



FREQUENCY_ROLLING_WINDOWS = {
    "daily": 504,      # ~2 trading/calendar years
    "weekly": 104,     # ~2 years
    "monthly": 24,     # ~2 years
    "quarterly": 8,    # ~2 years
}

MIN_TOTAL_OBS_FOR_EWS = 60  # below this, trend estimation is too unstable to report


def infer_frequency_label(series: pd.Series) -> str:
    """
    Infers a series' native frequency from the median gap between
    observations, so the rolling window used for critical-slowing-down
    detection represents a consistent CALENDAR span (~2 years) across
    series of very different native frequencies — a fixed period count
    (e.g. "24 periods") means 24 days for a daily series but 2 years
    for a monthly one, which would silently produce meaningless results
    if left unadjusted.
    """
    clean = series.dropna().sort_index()
    if len(clean) < 3:
        return "unknown"
    median_gap_days = clean.index.to_series().diff().dt.days.median()

    if median_gap_days <= 3:
        return "daily"
    elif median_gap_days <= 10:
        return "weekly"
    elif median_gap_days <= 45:
        return "monthly"
    elif median_gap_days <= 100:
        return "quarterly"
    else:
        return "annual"


def infer_rolling_window_periods(series: pd.Series) -> int | None:
    """
    Returns the rolling window (in number of observations) that
    represents ~2 calendar years for this series' frequency, or None
    if the frequency is annual/unknown — annual series (e.g. public
    debt) don't have enough resolution for this technique; critical
    slowing down needs many overlapping windows to detect a TREND in
    autocorrelation/variance, which a handful of annual points cannot
    support.
    """
    freq = infer_frequency_label(series)
    return FREQUENCY_ROLLING_WINDOWS.get(freq)  # None for "annual"/"unknown"

def rolling_autocorr_lag1(series: pd.Series, window: int = EWS_ROLLING_WINDOW) -> pd.Series:
    """
    Lag-1 autocorrelation computed on a trailing rolling window.
    Rising values over time = the series is becoming more "sticky"
    (slower to revert after a shock) — the core critical-slowing-down signal.
    """
    def _ac1(x: np.ndarray) -> float:
        if len(x) < 3 or np.std(x) == 0:
            return np.nan
        return np.corrcoef(x[:-1], x[1:])[0, 1]

    return series.rolling(window=window, min_periods=window).apply(_ac1, raw=True)


def rolling_variance(series: pd.Series, window: int = EWS_ROLLING_WINDOW) -> pd.Series:
    """Variance on a trailing rolling window — the second half of the signal."""
    return series.rolling(window=window, min_periods=window).var()


def kendall_trend_test(series: pd.Series) -> dict:
    """
    Tests whether `series` has a significant monotonic trend against
    time, using Kendall's tau. Returns NaNs if there isn't enough data.
    """
    clean = series.dropna()
    if len(clean) < MIN_ROLLING_POINTS_FOR_TREND:
        return {"tau": np.nan, "p_value": np.nan, "n": len(clean)}

    time_index = np.arange(len(clean))
    tau, p_value = scipy_stats.kendalltau(time_index, clean.values)
    return {"tau": tau, "p_value": p_value, "n": len(clean)}


def compute_early_warning_stats(
    window: WindowResult, series_key: str, rolling_window: int = EWS_ROLLING_WINDOW
) -> pd.DataFrame:
    """
    Computes the critical-slowing-down diagnostic for one series over
    one reference window. Returns a tidy DataFrame matching the same
    schema as descriptive.compute_descriptive_stats (series_key,
    window_type, window_label, stat_name, value, ci_low, ci_high,
    p_value), so both can be concatenated into one combined results table.

    ci_low/ci_high are always NaN here — see module docstring for why
    bootstrap isn't used for this particular statistic.
    """
    data = window.data.dropna()

    ac1_series = rolling_autocorr_lag1(data, window=rolling_window)
    var_series = rolling_variance(data, window=rolling_window)

    ac1_trend = kendall_trend_test(ac1_series)
    var_trend = kendall_trend_test(var_series)

    rows = [
        {
            "stat_name": "ac1_trend_tau",
            "value": ac1_trend["tau"],
            "ci_low": np.nan,
            "ci_high": np.nan,
            "p_value": ac1_trend["p_value"],
        },
        {
            "stat_name": "variance_trend_tau",
            "value": var_trend["tau"],
            "ci_low": np.nan,
            "ci_high": np.nan,
            "p_value": var_trend["p_value"],
        },
    ]

    # The combined "critical slowing down" flag requires BOTH signals to
    # be significantly increasing — either alone is weaker evidence and
    # more likely to be a false positive from an unrelated trend.
    both_significant_and_rising = (
        not np.isnan(ac1_trend["p_value"])
        and not np.isnan(var_trend["p_value"])
        and ac1_trend["tau"] > 0
        and var_trend["tau"] > 0
        and ac1_trend["p_value"] < 0.05
        and var_trend["p_value"] < 0.05
    )
    rows.append(
        {
            "stat_name": "critical_slowing_down_flag",
            "value": float(both_significant_and_rising),
            "ci_low": np.nan,
            "ci_high": np.nan,
            "p_value": max(ac1_trend["p_value"], var_trend["p_value"]) if both_significant_and_rising else np.nan,
        }
    )

    df = pd.DataFrame(rows)
    df.insert(0, "series_key", series_key)
    df.insert(1, "window_type", window.window_type)
    df.insert(2, "window_label", window.label)
    return df