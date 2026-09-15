"""
tests/test_windows.py
"""

import numpy as np
import pandas as pd

from src.analysis.windows import (
    get_full_history_window,
    get_rolling_window,
    get_since_break_window,
    get_all_windows,
)


def _make_flat_series(n_years: int = 20) -> pd.Series:
    """A series with no structural break at all — used to test fallback."""
    dates = pd.date_range("2004-01-01", periods=n_years * 12, freq="MS")
    values = np.random.default_rng(42).normal(loc=10, scale=1, size=len(dates))
    return pd.Series(values, index=dates)


def _make_series_with_break(break_date: str, n_years: int = 25, jump: float = 200.0) -> pd.Series:
    dates = pd.date_range("2000-01-01", periods=n_years * 12, freq="MS")
    values = np.linspace(0, 10, len(dates))
    break_idx = dates.get_indexer([pd.Timestamp(break_date)], method="nearest")[0]
    values[break_idx:] += jump
    return pd.Series(values, index=dates)


def test_full_history_window_covers_entire_series():
    series = _make_flat_series()
    result = get_full_history_window(series)
    assert result.start_date == series.index.min()
    assert result.end_date == series.index.max()
    assert len(result.data) == len(series)


def test_rolling_window_is_approximately_10_years():
    series = _make_flat_series(n_years=20)
    result = get_rolling_window(series, years=10)
    span_years = (result.end_date - result.start_date).days / 365.25
    assert 9.5 <= span_years <= 10.5


def test_since_break_window_starts_at_the_detected_break():
    series = _make_series_with_break("2018-12-01")
    result = get_since_break_window(series)
    assert not result.used_fallback
    assert result.start_date == pd.Timestamp("2018-12-01")


def test_since_break_window_falls_back_when_no_break_found():
    series = _make_flat_series()
    result = get_since_break_window(series)
    assert result.used_fallback is True
    assert "fallback" in result.label


def test_get_all_windows_returns_two_production_windows():
    """
    Production pipeline uses only full_history and rolling_10y.
    since_last_break was retired — see windows.py docstring and
    SERIES_METADATA.md Decisions Log #11.
    """
    series = _make_series_with_break("2012-12-01")
    windows = get_all_windows(series)
    assert len(windows) == 2
    window_types = {w.window_type for w in windows}
    assert window_types == {"full_history", "rolling_10y"}


def test_since_break_window_still_available_for_research_use():
    """
    get_since_break_window() is retained for research/reference use,
    even though it's no longer called by get_all_windows(). This test
    confirms it still works correctly on its own — the function isn't
    broken, it was just misapplied in production.
    """
    series = _make_series_with_break("2018-12-01")
    result = get_since_break_window(series)
    assert not result.used_fallback
    assert result.start_date == pd.Timestamp("2018-12-01")