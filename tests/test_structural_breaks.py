"""
tests/test_structural_breaks.py
"""

import numpy as np
import pandas as pd

from src.analysis.structural_breaks import chow_test, most_recent_significant_break


def _make_series_with_break(break_date: str, n_years: int = 20, jump: float = 50.0) -> pd.Series:
    """Builds a synthetic series with a known, deliberate level shift."""
    dates = pd.date_range("2004-01-01", periods=n_years * 12, freq="MS")
    values = np.linspace(0, 10, len(dates))  # mild trend
    break_idx = dates.get_indexer([pd.Timestamp(break_date)], method="nearest")[0]
    values[break_idx:] += jump  # inject an obvious level shift
    return pd.Series(values, index=dates)


def test_chow_test_detects_an_obvious_break():
    series = _make_series_with_break("2012-12-01", jump=100.0)
    result = chow_test(series, pd.Timestamp("2012-12-01"))
    assert result is not None
    assert result["p_value"] < 0.01  # should be an overwhelmingly clear break


def test_chow_test_returns_none_with_insufficient_data():
    short_series = pd.Series([1, 2, 3], index=pd.date_range("2020-01-01", periods=3, freq="MS"))
    result = chow_test(short_series, pd.Timestamp("2020-02-01"))
    assert result is None


def test_most_recent_significant_break_finds_the_injected_break():
    series = _make_series_with_break("2018-12-01", n_years=25, jump=200.0)
    result = most_recent_significant_break(series)
    assert result == pd.Timestamp("2018-12-01")