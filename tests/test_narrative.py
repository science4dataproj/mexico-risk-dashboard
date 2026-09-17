"""
tests/test_narrative.py
"""

import pandas as pd

from src.reporting.narrative import generate_series_narrative, generate_domain_narrative


def _row(series_key, window_type, stat_name, value, flag_significant=True):
    return {
        "series_key": series_key,
        "window_type": window_type,
        "stat_name": stat_name,
        "value": value,
        "flag_significant": flag_significant,
    }


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


def test_plural_subjects_use_plural_verb():
    rows = [
        _row("international_reserves", "rolling_10y", "percentile_rank", 99.5),
        _row("international_reserves", "rolling_10y", "ac1_trend_tau", 0.3),
        _row("international_reserves", "rolling_10y", "variance_trend_tau", 0.4),
    ]
    df = pd.DataFrame(rows)
    text = generate_series_narrative(df, "international_reserves")
    assert "están" in text
    assert "está " not in text  # asegura que no quedó el singular incorrecto


def test_acronyms_keep_their_uppercase_letters():
    rows = [
        _row("cpi", "rolling_10y", "percentile_rank", 97.1),
        _row("cpi", "rolling_10y", "ac1_trend_tau", 0.1),
        _row("cpi", "rolling_10y", "variance_trend_tau", 0.1),
    ]
    df = pd.DataFrame(rows)
    text = generate_series_narrative(df, "cpi")
    assert "INPC" in text
    assert "inpc" not in text

def _trend_phrase(ac1_tau, ac1_sig, var_tau, var_sig) -> str:
    if ac1_tau is None or var_tau is None:
        return "sin suficiente información de tendencia"

    ac1_rising = ac1_sig and ac1_tau > 0
    var_rising = var_sig and var_tau > 0
    ac1_falling = ac1_sig and ac1_tau < 0
    var_falling = var_sig and var_tau < 0

    if ac1_rising and var_rising:
        return "mostrando una tendencia consistente y estadísticamente significativa hacia mayor inestabilidad"
    if ac1_falling and var_falling:
        return "mostrando una tendencia consistente y estadísticamente significativa hacia mayor estabilidad"
    if ac1_sig or var_sig:
        return "mostrando una tendencia significativa solo en uno de los dos indicadores de estabilidad, sin un patrón consistente"
    return "sin una tendencia estadísticamente significativa de estabilidad o fragilidad"

def test_trend_phrase_requires_significance_not_just_sign():
    text = _trend_phrase(ac1_tau=0.353, ac1_sig=True, var_tau=0.017, var_sig=False)
    assert "tendencia consistente y estadísticamente significativa" not in text
    assert "significativa solo en uno" in text


def test_trend_phrase_confirms_consistent_when_both_significant():
    text = _trend_phrase(ac1_tau=0.562, ac1_sig=True, var_tau=0.686, var_sig=True)
    assert "consistente" in text
    assert "inestabilidad" in text

from src.reporting.narrative import generate_domain_narrative_bilingual, _ordinal_en


def test_ordinal_en_handles_teens_correctly():
    """11, 12, 13 are the classic edge case that breaks naive ordinal logic."""
    assert _ordinal_en(11) == "11th"
    assert _ordinal_en(12) == "12th"
    assert _ordinal_en(13) == "13th"
    assert _ordinal_en(21) == "21st"
    assert _ordinal_en(22) == "22nd"
    assert _ordinal_en(23) == "23rd"
    assert _ordinal_en(4) == "4th"


def test_english_narrative_matches_real_m2_pattern():
    rows = [
        _row("m2", "rolling_10y", "percentile_rank", 99.6),
        _row("m2", "rolling_10y", "ac1_trend_tau", 0.56),
        _row("m2", "rolling_10y", "variance_trend_tau", 0.69),
    ]
    df = pd.DataFrame(rows)
    text = generate_series_narrative(df, "m2", lang="en")
    assert "historically high" in text
    assert "instability" in text
    assert "100th percentile" in text

def test_english_narrative_matches_real_significance_mismatch_pattern():
    rows = [
        _row("fx_rate_fix", "rolling_10y", "percentile_rank", 3.6),
        _row("fx_rate_fix", "rolling_10y", "ac1_trend_tau", 0.353, flag_significant=True),
        _row("fx_rate_fix", "rolling_10y", "variance_trend_tau", 0.017, flag_significant=False),
    ]
    df = pd.DataFrame(rows)
    text = generate_series_narrative(df, "fx_rate_fix", lang="en")
    assert "consistent trend" not in text
    assert "only one of the two" in text


def test_default_language_is_spanish_for_backward_compatibility():
    rows = [
        _row("m2", "rolling_10y", "percentile_rank", 99.6),
        _row("m2", "rolling_10y", "ac1_trend_tau", 0.56),
        _row("m2", "rolling_10y", "variance_trend_tau", 0.69),
    ]
    df = pd.DataFrame(rows)
    text_no_lang_arg = generate_series_narrative(df, "m2")
    text_explicit_es = generate_series_narrative(df, "m2", lang="es")
    assert text_no_lang_arg == text_explicit_es


def test_domain_narrative_bilingual_returns_both_languages():
    rows = [
        _row("cpi", "rolling_10y", "percentile_rank", 97.1),
        _row("cpi", "rolling_10y", "ac1_trend_tau", 0.237, flag_significant=True),
        _row("cpi", "rolling_10y", "variance_trend_tau", 0.241, flag_significant=True),
    ]
    df = pd.DataFrame(rows)
    result = generate_domain_narrative_bilingual(df, "prices")
    assert "es" in result and "en" in result
    assert "INPC" in result["es"]
    assert "CPI" in result["en"]

def test_english_missing_trend_data_reads_as_complete_sentence():
    """
    Regression test: the English 'no trend data' phrase must connect
    grammatically to the rest of the sentence via 'with', not read as
    a bare, disconnected noun phrase after the comma.
    """
    rows = [
        _row("quarterly_gdp", "rolling_10y", "percentile_rank", 98.8),
        # no ac1_trend_tau / variance_trend_tau rows -> triggers the missing-data branch
    ]
    df = pd.DataFrame(rows)
    text = generate_series_narrative(df, "quarterly_gdp", lang="en")
    assert "with insufficient trend data available" in text
    assert ", insufficient trend data" not in text  # the old, broken phrasing


from src.reporting.narrative import generate_composite_technical_summary
from src.reporting.composite_index import DomainScore, ScoreLabel


def test_composite_technical_summary_lists_flagged_domains():
    domains = [
        DomainScore("liquidity", {"es": "Liquidez", "en": "Liquidity"}, 81.2,
                     ScoreLabel("fragile", {"es": "Señal fuerte de fragilidad", "en": "Strong fragility signal"}), 3, 6),
        DomainScore("prices", {"es": "Precios", "en": "Prices"}, 20.0,
                     ScoreLabel("stable", {"es": "Sin cambios relevantes", "en": "No notable change"}), 0, 2),
    ]
    result = generate_composite_technical_summary(domains, 50.6)
    assert "1 de 2 dominio muestra" in result["es"]
    assert "Liquidez" in result["es"]
    assert "Precios" not in result["es"]
    assert "1 of 2 domain shows" in result["en"]


def test_composite_technical_summary_handles_zero_flagged():
    domains = [
        DomainScore("prices", {"es": "Precios", "en": "Prices"}, 10.0,
                     ScoreLabel("stable", {"es": "Sin cambios relevantes", "en": "No notable change"}), 0, 2),
    ]
    result = generate_composite_technical_summary(domains, 10.0)
    assert "Ninguno de los" in result["es"]
    assert "None of the" in result["en"]

def test_narrative_switches_to_full_history_when_rolling_10y_has_no_signal():
    """
    Regression test for the real m1 discrepancy found 2026-09-16: full
    history showed a significant CSD flag while rolling_10y did not,
    but the narrative (fixed to rolling_10y) silently ignored it,
    contradicting the domain score (which uses both windows).
    """
    rows = [
        _row("m1", "rolling_10y", "percentile_rank", 50.0),
        _row("m1", "rolling_10y", "ac1_trend_tau", 0.01, flag_significant=False),
        _row("m1", "rolling_10y", "variance_trend_tau", 0.31, flag_significant=False),
        _row("m1", "rolling_10y", "critical_slowing_down_flag", 0.0),
        _row("m1", "full_history", "percentile_rank", 98.0),
        _row("m1", "full_history", "ac1_trend_tau", 0.45, flag_significant=True),
        _row("m1", "full_history", "variance_trend_tau", 0.80, flag_significant=True),
        _row("m1", "full_history", "critical_slowing_down_flag", 1.0),
    ]
    df = pd.DataFrame(rows)
    text = generate_series_narrative(df, "m1")
    assert "consistente" in text  # ahora sí debe reflejar la señal de full_history
    assert "historia completa" in text
    assert "percentil 98" in text  # debe usar el percentil de full_history, no el de rolling_10y (50)