"""
tests/test_derived_series.py
"""

import pandas as pd
import pytest

from src.transform.derived_series import compute_m2_reserves_ratio


def _panel(m2_rows, reserves_rows):
    rows = (
        [{"series_key": "m2", "date": pd.Timestamp(d), "value": v} for d, v in m2_rows]
        + [{"series_key": "international_reserves", "date": pd.Timestamp(d), "value": v} for d, v in reserves_rows]
    )
    return pd.DataFrame(rows)


def test_ratio_computes_correctly_for_a_simple_aligned_month():
    panel = _panel(
        m2_rows=[("2020-01-31", 100.0)],
        reserves_rows=[("2020-01-03", 20.0), ("2020-01-10", 25.0), ("2020-01-31", 50.0)],
    )
    ratio = compute_m2_reserves_ratio(panel)
    assert len(ratio) == 1
    # Reserves takes the LAST weekly reading within the month (50.0), not the first or an average.
    assert ratio.iloc[0] == pytest.approx(100.0 / 50.0)


def test_ratio_drops_months_where_either_series_is_missing():
    """A month with M2 but no reserves reading (or vice versa) must not
    appear in the output — never silently fabricated from a stale value."""
    panel = _panel(
        m2_rows=[("2020-01-31", 100.0), ("2020-02-29", 110.0)],
        reserves_rows=[("2020-01-15", 50.0)],  # no February reserves reading
    )
    ratio = compute_m2_reserves_ratio(panel)
    assert len(ratio) == 1
    assert ratio.index[0].month == 1


def test_ratio_index_is_a_proper_monthly_timestamp_not_a_period():
    """Downstream code (early_warning.py, backtest.py) expects a
    DatetimeIndex, like every other series in this project's panel —
    not a pandas Period, which would break comparisons like
    `raw_series.index < crisis_date`."""
    panel = _panel(m2_rows=[("2020-01-31", 100.0)], reserves_rows=[("2020-01-15", 50.0)])
    ratio = compute_m2_reserves_ratio(panel)
    assert isinstance(ratio.index, pd.DatetimeIndex)


def test_ratio_is_empty_before_m2_series_starts():
    """Regression check for the real coverage gap this ratio has: no
    rows should be produced for dates before M2 data exists (2000-12),
    even if reserves data exists further back — this is what makes the
    ratio untestable against the 1994 Tequila crisis (see
    SERIES_METADATA.md Decisions Log #25)."""
    panel = _panel(
        m2_rows=[("2001-01-31", 100.0)],
        reserves_rows=[("1996-01-15", 30.0), ("2001-01-15", 50.0)],
    )
    ratio = compute_m2_reserves_ratio(panel)
    assert ratio.index.min().year >= 2001


def test_ratio_sorted_chronologically():
    panel = _panel(
        m2_rows=[("2020-03-31", 120.0), ("2020-01-31", 100.0), ("2020-02-29", 110.0)],
        reserves_rows=[("2020-01-15", 50.0), ("2020-02-15", 52.0), ("2020-03-15", 55.0)],
    )
    ratio = compute_m2_reserves_ratio(panel)
    assert list(ratio.index) == sorted(ratio.index)