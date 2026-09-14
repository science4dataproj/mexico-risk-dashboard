"""
tests/test_descriptive.py
"""

import numpy as np
import pandas as pd

from src.analysis.descriptive import compute_descriptive_stats, apply_multiple_testing_correction
from src.analysis.windows import get_full_history_window


def _make_normal_series(n=120, seed=1) -> pd.Series:
    dates = pd.date_range("2015-01-01", periods=n, freq="MS")
    values = np.random.default_rng(seed).normal(loc=100, scale=5, size=n)
    return pd.Series(values, index=dates)


def test_basic_stats_are_computed():
    series = _make_normal_series()
    window = get_full_history_window(series)
    df = compute_descriptive_stats(window, "test_series")

    stat_names = set(df["stat_name"])
    assert {"mean", "median", "std", "min", "max", "latest_value", "z_score", "percentile_rank"}.issubset(stat_names)


def test_extreme_latest_value_produces_large_zscore():
    series = _make_normal_series()
    # Inject an obviously extreme final observation
    series.iloc[-1] = series.mean() + 10 * series.std()
    window = get_full_history_window(series)
    df = compute_descriptive_stats(window, "test_series")

    z_row = df[df["stat_name"] == "z_score"].iloc[0]
    assert z_row["value"] > 5
    assert z_row["p_value"] < 0.001


def test_jarque_bera_detects_non_normal_data():
    dates = pd.date_range("2015-01-01", periods=200, freq="MS")
    skewed_values = np.random.default_rng(2).exponential(scale=2.0, size=200)  # clearly non-normal
    series = pd.Series(skewed_values, index=dates)
    window = get_full_history_window(series)
    df = compute_descriptive_stats(window, "test_series")

    jb_row = df[df["stat_name"] == "jarque_bera_normality"].iloc[0]
    assert jb_row["p_value"] < 0.01


def test_multiple_testing_correction_reduces_false_positives():
    # Build many series' worth of pure noise (no real signal) — with
    # enough series tested, some raw p-values will randomly fall below
    # 0.05 by chance. FDR correction should reduce, not increase, the
    # count of significant results.
    rng = np.random.default_rng(3)
    all_results = []
    for i in range(30):
        series = pd.Series(rng.normal(100, 5, 120), index=pd.date_range("2015-01-01", periods=120, freq="MS"))
        window = get_full_history_window(series)
        df = compute_descriptive_stats(window, f"series_{i}")
        all_results.append(df)

    combined = pd.concat(all_results, ignore_index=True)
    corrected = apply_multiple_testing_correction(combined)

    raw_significant = (combined["p_value"] < 0.05).sum()
    adjusted_significant = corrected["flag_significant"].sum()
    assert adjusted_significant <= raw_significant