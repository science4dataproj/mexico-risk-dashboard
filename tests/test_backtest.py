"""
tests/test_backtest.py
"""

import numpy as np
import pandas as pd

from src.analysis.backtest import backtest_series, KNOWN_CRISES


def test_backtest_series_skips_annual_series():
    dates = pd.date_range("1990-01-01", periods=30, freq="YS")
    series = pd.Series(np.random.default_rng(1).normal(50, 5, 30), index=dates)
    result = backtest_series(series, "2008_financial_crisis", "fake_annual")
    assert result["skipped"]
    assert "annual" in result["skip_reason"]


def test_backtest_series_skips_insufficient_pre_crisis_history():
    dates = pd.date_range("2008-06-01", periods=5, freq="MS")  # starts just before the 2008 anchor
    series = pd.Series(np.random.default_rng(1).normal(0, 1, 5), index=dates)
    result = backtest_series(series, "2008_financial_crisis", "fake_short")
    assert result["skipped"]


def test_backtest_series_only_uses_data_strictly_before_crisis_date():
    """Regression test: confirms no look-ahead — data after the crisis
    date must never influence the result."""
    dates = pd.date_range("2000-01-01", periods=400, freq="MS")
    values = np.random.default_rng(3).normal(0, 1, 400)
    series = pd.Series(values, index=dates)

    result_before = backtest_series(series, "2014_oil_collapse", "test")

    # Corrupt only the post-crisis tail — result must be identical
    series_corrupted = series.copy()
    crisis_date = KNOWN_CRISES["2014_oil_collapse"]["date"]
    series_corrupted[series_corrupted.index >= crisis_date] = 9999.0
    result_after = backtest_series(series_corrupted, "2014_oil_collapse", "test")

    if not result_before["skipped"] and not result_after["skipped"]:
        assert result_before["ac1_tau"] == result_after["ac1_tau"]

def test_add_significance_applies_bh_correction_across_full_batch():
    """Regression test: the backtest must never decide 'flag' from raw
    p-values alone — BH correction across the full batch was
    accidentally omitted when backtest.py was simplified to use
    surrogate_trend_test directly (found 2026-09-16, see
    SERIES_METADATA.md Decisions Log)."""
    from src.analysis.backtest import add_significance
    import pandas as pd

    # A single borderline p-value (0.04) that would pass alone, but
    # should NOT survive correction once batched with many others.
    rows = [{"crisis_name": "x", "series_key": "a", "skipped": False,
             "ac1_tau": 0.5, "ac1_p": 0.04, "var_tau": 0.5, "var_p": 0.04}]
    rows += [{"crisis_name": "x", "series_key": f"filler_{i}", "skipped": False,
              "ac1_tau": 0.1, "ac1_p": 0.9, "var_tau": 0.1, "var_p": 0.9} for i in range(20)]
    df = pd.DataFrame(rows)
    result = add_significance(df)
    assert "ac1_p_adjusted" in result.columns
    assert not result.loc[0, "flag"]  # 0.04 crudo no debe sobrevivir batch de 21