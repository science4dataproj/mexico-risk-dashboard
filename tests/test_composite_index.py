"""
tests/test_composite_index.py
"""

import pandas as pd

from src.reporting.composite_index import (
    compute_domain_fragility_score,
    compute_composite_index,
    label_for_score,
    SCORE_LABELS,
)


def _row(series_key, window_type, stat_name, value, flag_significant=False):
    return {
        "series_key": series_key,
        "window_type": window_type,
        "stat_name": stat_name,
        "value": value,
        "flag_significant": flag_significant,
    }


def test_label_thresholds_and_status_ids():
    assert label_for_score(0).status_id == "stable"
    assert label_for_score(0).text["es"] == "Sin cambios relevantes"
    assert label_for_score(34).status_id == "monitor"
    assert label_for_score(67).status_id == "fragile"
    assert label_for_score(100).status_id == "fragile"


def test_every_score_label_has_both_languages():
    for _, status_id, text in SCORE_LABELS:
        assert "es" in text and "en" in text
        assert status_id in ("stable", "monitor", "fragile")


def test_domain_with_all_signals_off_scores_zero_and_stable():
    rows = [
        _row("fx_rate_fix", "full_history", "ac1_trend_tau", -0.2, flag_significant=False),
        _row("fx_rate_fix", "full_history", "variance_trend_tau", 0.1, flag_significant=False),
        _row("fx_rate_fix", "full_history", "critical_slowing_down_flag", 0.0),
        _row("international_reserves", "rolling_10y", "ac1_trend_tau", -0.1, flag_significant=False),
    ]
    df = pd.DataFrame(rows)
    result = compute_domain_fragility_score(df, "external_stability")
    assert result.score == 0.0
    assert result.label.status_id == "stable"


def test_domain_with_all_signals_firing_scores_high_and_fragile():
    rows = [
        _row("fx_rate_fix", "full_history", "ac1_trend_tau", 0.5, flag_significant=True),
        _row("fx_rate_fix", "full_history", "variance_trend_tau", 0.6, flag_significant=True),
        _row("fx_rate_fix", "full_history", "critical_slowing_down_flag", 1.0),
        _row("international_reserves", "rolling_10y", "ac1_trend_tau", 0.4, flag_significant=True),
    ]
    df = pd.DataFrame(rows)
    result = compute_domain_fragility_score(df, "external_stability")
    assert result.score == 100.0
    assert result.label.status_id == "fragile"


def test_fiscal_solvency_never_enters_composite_average():
    rows = [
        _row("debt_shrfsp_broad_pct_gdp", "full_history", "z_score", 5.0),
        _row("fx_rate_fix", "full_history", "ac1_trend_tau", -0.1, flag_significant=False),
    ]
    df = pd.DataFrame(rows)
    result = compute_composite_index(df)
    domain_keys = [d.domain_key for d in result.domain_scores]
    assert "fiscal_solvency" not in domain_keys
    assert len(result.domain_scores) == 5


def test_composite_is_unweighted_average_of_domain_scores():
    rows = [
        _row("fx_rate_fix", "full_history", "ac1_trend_tau", 0.5, flag_significant=True),
        _row("fx_rate_fix", "full_history", "variance_trend_tau", 0.5, flag_significant=True),
    ]
    df = pd.DataFrame(rows)
    result = compute_composite_index(df)
    manual_avg = round(sum(d.score for d in result.domain_scores) / 5, 1)
    assert result.composite_score == manual_avg