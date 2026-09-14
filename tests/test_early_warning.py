"""
tests/test_early_warning.py
"""

import numpy as np
import pandas as pd

from src.analysis.early_warning import (
    rolling_autocorr_lag1,
    rolling_variance,
    kendall_trend_test,
    compute_early_warning_stats,
)
from src.analysis.windows import get_full_history_window


def test_rolling_autocorr_detects_known_ar1_process():
    """An AR(1) process with a high coefficient should show high, roughly
    stable rolling autocorrelation — a sanity check that the calculation
    itself is correct before testing the trend-detection logic."""
    rng = np.random.default_rng(7)
    n = 300
    phi = 0.9
    values = np.zeros(n)
    for t in range(1, n):
        values[t] = phi * values[t - 1] + rng.normal(0, 1)
    series = pd.Series(values, index=pd.date_range("2000-01-01", periods=n, freq="MS"))

    ac1 = rolling_autocorr_lag1(series, window=24).dropna()
    assert ac1.mean() > 0.6  # should reflect the strong true AR(1) coefficient


def test_kendall_trend_test_detects_obvious_increasing_trend():
    series = pd.Series(np.arange(50) + np.random.default_rng(1).normal(0, 0.5, 50))
    result = kendall_trend_test(series)
    assert result["tau"] > 0.8
    assert result["p_value"] < 0.001


def test_kendall_trend_test_returns_nan_for_insufficient_data():
    series = pd.Series([1, 2, 3])
    result = kendall_trend_test(series)
    assert np.isnan(result["tau"])


def test_critical_slowing_down_flag_fires_on_injected_pattern():
    """
    Builds a synthetic series that deliberately mimics critical slowing
    down: stable/noisy for the first stretch, then increasingly
    autocorrelated AND increasingly volatile in the final stretch,
    simulating a system losing resilience before a regime shift.
    """
    rng = np.random.default_rng(5)
    n_stable, n_destabilizing = 150, 150
    stable = rng.normal(0, 1, n_stable)

    destabilizing = np.zeros(n_destabilizing)
    for t in range(1, n_destabilizing):
        # AR(1) coefficient and noise scale both ramp up over time
        phi_t = 0.1 + 0.85 * (t / n_destabilizing)
        noise_scale = 1 + 3 * (t / n_destabilizing)
        destabilizing[t] = phi_t * destabilizing[t - 1] + rng.normal(0, noise_scale)

    values = np.concatenate([stable, destabilizing])
    dates = pd.date_range("2000-01-01", periods=len(values), freq="MS")
    series = pd.Series(values, index=dates)

    window = get_full_history_window(series)
    df = compute_early_warning_stats(window, "test_series", rolling_window=24)

    flag_row = df[df["stat_name"] == "critical_slowing_down_flag"].iloc[0]
    assert flag_row["value"] == 1.0


def test_critical_slowing_down_flag_does_not_fire_on_stable_noise():
    """A pure stable noise series (no trend in AC1 or variance) should
    NOT trigger the flag — guards against false positives."""
    rng = np.random.default_rng(9)
    series = pd.Series(rng.normal(0, 1, 300), index=pd.date_range("2000-01-01", periods=300, freq="MS"))

    window = get_full_history_window(series)
    df = compute_early_warning_stats(window, "test_series", rolling_window=24)

    flag_row = df[df["stat_name"] == "critical_slowing_down_flag"].iloc[0]
    assert flag_row["value"] == 0.0