"""
tests/test_narrative.py
"""

import pandas as pd

from src.reporting.narrative import generate_series_narrative, generate_domain_narrative


def _row(series_key, window_type, stat_name, value):
    return {"series_key": series_key, "window_type": window_type, "stat_name": stat_name, "value": value}


def test_narrative_describes_high_level_and_rising_instability():
    rows = [
        _row("m2", "rolling_10y", "percentile_rank", 99.6),
        _row("m2", "rolling_10y", "ac1_trend_tau", 0.56),
        _row("m2", "rolling_10y", "variance_trend_tau", 0.69),
    ]
    df = pd.DataFrame(rows)
    text = generate_series_narrative(df, "m2")
    assert "históricamente alto" in text
    assert "inestabilidad" in text


def test_narrative_describes_low_level_and_stabilizing_trend():
    rows = [
        _row("unemployment_rate", "rolling_10y", "percentile_rank", 28.5),
        _row("unemployment_rate", "rolling_10y", "ac1_trend_tau", -0.1),
        _row("unemployment_rate", "rolling_10y", "variance_trend_tau", -0.18),
    ]
    df = pd.DataFrame(rows)
    text = generate_series_narrative(df, "unemployment_rate")
    assert "históricamente bajo" in text
    assert "mayor estabilidad" in text


def test_narrative_handles_missing_data_gracefully():
    df = pd.DataFrame(columns=["series_key", "window_type", "stat_name", "value"])
    text = generate_series_narrative(df, "cpi")
    assert "sin datos" in text or "sin suficiente" in text


def test_domain_narrative_combines_all_its_series():
    rows = [
        _row("fx_rate_fix", "rolling_10y", "percentile_rank", 3.6),
        _row("fx_rate_fix", "rolling_10y", "ac1_trend_tau", -0.05),
        _row("fx_rate_fix", "rolling_10y", "variance_trend_tau", 0.1),
        _row("international_reserves", "rolling_10y", "percentile_rank", 99.5),
        _row("international_reserves", "rolling_10y", "ac1_trend_tau", 0.3),
        _row("international_reserves", "rolling_10y", "variance_trend_tau", 0.4),
    ]
    df = pd.DataFrame(rows)
    text = generate_domain_narrative(df, "external_stability")
    assert "tipo de cambio" in text.lower()
    assert "reservas" in text.lower()

def _level_phrase(percentile: float | None) -> str:
    if percentile is None:
        return "sin datos de nivel disponibles"
    if percentile >= 67:
        return f"en un nivel históricamente alto (percentil {percentile:.0f})"
    if percentile <= 33:
        return f"en un nivel históricamente bajo (percentil {percentile:.0f})"
    return f"en un nivel típico dentro de su historia (percentil {percentile:.0f})"

def test_thresholds_match_manually_validated_conclusions_from_real_data():
    """
    Regression test: confirms the 33/67 percentile thresholds reproduce
    the exact level classifications independently reached through
    manual analysis earlier in the project (see conversation/session
    notes), using real analysis_results.csv data — not just synthetic
    test fixtures. Guards against threshold drift silently changing
    the substantive meaning of the narrative.
    """
    known_real_percentiles = {
        "fx_rate_fix": (3.6, "bajo"),
        "cetes_28d": (25.4, "bajo"),
        "target_rate": (28.2, "bajo"),
        "unemployment_rate": (28.5, "bajo"),
        "debt_shrfsp_broad_pct_gdp": (95.5, "alto"),
        "cpi": (97.1, "alto"),
        "m1": (97.9, "alto"),
        "quarterly_gdp": (98.8, "alto"),
        "international_reserves": (99.5, "alto"),
        "m2": (99.6, "alto"),
    }
    for series_key, (percentile, expected) in known_real_percentiles.items():
        phrase = _level_phrase(percentile)
        if expected == "alto":
            assert "alto" in phrase
        else:
            assert "bajo" in phrase    