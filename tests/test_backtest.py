"""
tests/test_backtest.py
"""
import pytest
import numpy as np
import pandas as pd

from src.analysis.backtest import (
    get_pre_window,
    backtest_series,
    generate_control_dates,
    KNOWN_CRISES,
)


def test_get_pre_window_is_point_based_not_calendar_based():
    dates = pd.date_range("2000-01-01", periods=100, freq="QS")  # quarterly
    series = pd.Series(np.arange(100.0), index=dates)
    anchor = dates[50]
    window = get_pre_window(series, anchor, target_points=24)
    assert len(window) == 24
    assert window.index.max() < anchor


def test_get_pre_window_returns_fewer_points_if_insufficient_history():
    dates = pd.date_range("2000-01-01", periods=10, freq="MS")
    series = pd.Series(np.arange(10.0), index=dates)
    anchor = dates[5]
    window = get_pre_window(series, anchor, target_points=24)
    assert len(window) <= 5


def test_backtest_series_skips_annual_series():
    dates = pd.date_range("1990-01-01", periods=30, freq="YS")
    series = pd.Series(np.random.default_rng(1).normal(50, 5, 30), index=dates)
    result = backtest_series(series, "2008_financial_crisis", "fake_annual_series")
    assert result.skipped
    assert "annual" in result.skip_reason


def test_backtest_series_detects_obvious_pre_crisis_instability():
    """Synthetic series: stable noise, then deliberately destabilizing
    right before the crisis anchor — should show high ac1/variance tau
    and a high percentile against controls."""
    rng = np.random.default_rng(3)
    dates = pd.date_range("2000-01-01", periods=200, freq="MS")
    values = np.zeros(200)
    crisis_idx = 150
    for t in range(1, 200):
        if t < crisis_idx - 24:
            values[t] = rng.normal(0, 1)
        else:
            phi = 0.1 + 0.8 * ((t - (crisis_idx - 24)) / 24)
            noise = 1 + 3 * ((t - (crisis_idx - 24)) / 24)
            values[t] = phi * values[t - 1] + rng.normal(0, max(noise, 0.1))
    series = pd.Series(values, index=dates)

    fake_crisis_date = dates[crisis_idx]
    import src.analysis.backtest as bt
    bt.KNOWN_CRISES = {**KNOWN_CRISES, "_test_crisis": {"date": fake_crisis_date, "series": []}}
    result = bt.backtest_series(series, "_test_crisis", "synthetic")

    assert not result.skipped
    assert result.ac1_tau > 0
    assert result.var_tau > 0


def test_generate_control_dates_excludes_buffer_around_crises():
    dates = pd.date_range("1990-01-01", periods=400, freq="MS")
    series = pd.Series(np.random.default_rng(2).normal(0, 1, 400), index=dates)
    crisis_dates = [pd.Timestamp("2008-09-01")]
    controls = generate_control_dates(series, crisis_dates, n_controls=30, buffer_months=12)
    for c in controls:
        assert abs((c - crisis_dates[0]).days) >= 12 * 30

from src.analysis.backtest import empirical_p_value_rising, add_significance


def test_empirical_p_value_never_zero_even_if_real_beats_all_controls():
    """Phipson & Smyth (2010): p must never be exactly 0, even when the
    real value exceeds every single control."""
    controls = [0.1, 0.2, 0.3, 0.15, 0.25]  # all lower than real
    p = empirical_p_value_rising(real_tau=0.9, control_taus=controls)
    assert p > 0
    assert p == pytest.approx(1 / 6)  # b=0, m=5 -> (0+1)/(5+1)


def test_empirical_p_value_is_high_when_real_is_lower_than_controls():
    """A real tau lower than all controls (e.g. target_rate 2014,
    which fell rather than rose) should NOT read as significant for
    the 'rising' hypothesis."""
    controls = [0.5, 0.6, 0.7, 0.55, 0.65]
    p = empirical_p_value_rising(real_tau=-1.0, control_taus=controls)
    assert p == 1.0  # all 5 controls >= -1.0 -> (5+1)/(5+1)


def test_add_significance_flags_only_when_both_stats_significant_and_rising():
    df = pd.DataFrame([
        {"crisis_name": "x", "series_key": "a", "ac1_tau": 0.9, "ac1_p_empirical": 0.01,
         "var_tau": 0.9, "var_p_empirical": 0.01},
        {"crisis_name": "x", "series_key": "b", "ac1_tau": 0.9, "ac1_p_empirical": 0.01,
         "var_tau": -0.9, "var_p_empirical": 0.9},  # only one rising -> no flag
    ])
    result = add_significance(df)
    assert result.loc[0, "flag"] == True
    assert result.loc[1, "flag"] == False