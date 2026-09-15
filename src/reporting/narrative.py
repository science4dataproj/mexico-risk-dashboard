"""
src/reporting/narrative.py

Generates deterministic, template-based narrative text for each domain,
using the underlying level statistics (percentile_rank, z_score) from
analysis_results.csv. Template-based, not free text generation, so the
output is reproducible and auditable on every pipeline run — the same
input data always produces the same sentence.

This is where level/direction context lives (e.g. "unemployment is
historically low, which is reassuring") — the composite score in
composite_index.py deliberately never encodes this kind of directional
judgment; this module is the only place it appears, and always as
plain-language text a stakeholder reads directly, never as a hidden
weight in a number.
"""

import pandas as pd

from src.reporting.domains import DOMAIN_MAP

# Human-readable series names for narrative text.
SERIES_DISPLAY_NAMES = {
    "fx_rate_fix": ("el tipo de cambio", False),
    "international_reserves": ("las reservas internacionales", True),
    "m1": ("M1", False),
    "m2": ("M2", False),
    "cetes_28d": ("los CETES a 28 días", True),
    "target_rate": ("la tasa objetivo de Banxico", False),
    "quarterly_gdp": ("el PIB trimestral", False),
    "unemployment_rate": ("la tasa de desocupación", False),
    "cpi": ("el INPC", False),
}


def _get_stat(results_df: pd.DataFrame, series_key: str, window_type: str, stat_name: str):
    match = results_df[
        (results_df["series_key"] == series_key)
        & (results_df["window_type"] == window_type)
        & (results_df["stat_name"] == stat_name)
    ]
    return match["value"].iloc[0] if not match.empty else None


def _get_significance(results_df: pd.DataFrame, series_key: str, window_type: str, stat_name: str) -> bool:
    """Returns whether a stat's flag_significant is True. Defaults to
    False if the row is missing OR the flag_significant column itself
    isn't present (e.g. minimal test fixtures) — never assumes
    significance when it can't be confirmed."""
    match = results_df[
        (results_df["series_key"] == series_key)
        & (results_df["window_type"] == window_type)
        & (results_df["stat_name"] == stat_name)
    ]
    if match.empty or "flag_significant" not in match.columns:
        return False
    val = match["flag_significant"].iloc[0]
    return bool(val) if pd.notna(val) else False


def generate_series_narrative(results_df: pd.DataFrame, series_key: str, window_type: str = "rolling_10y") -> str:
    """Builds one plain-language sentence describing a single series."""
    display_name, is_plural = SERIES_DISPLAY_NAMES.get(series_key, (series_key, False))
    verb = "están" if is_plural else "está"

    percentile = _get_stat(results_df, series_key, window_type, "percentile_rank")
    ac1_tau = _get_stat(results_df, series_key, window_type, "ac1_trend_tau")
    ac1_sig = _get_significance(results_df, series_key, window_type, "ac1_trend_tau")
    var_tau = _get_stat(results_df, series_key, window_type, "variance_trend_tau")
    var_sig = _get_significance(results_df, series_key, window_type, "variance_trend_tau")

    level = _level_phrase(percentile)
    trend = _trend_phrase(ac1_tau, ac1_sig, var_tau, var_sig)

    sentence = f"{display_name} {verb} {level}, {trend}."
    return sentence[0].upper() + sentence[1:]


def _level_phrase(percentile: float | None) -> str:
    if percentile is None:
        return "sin datos de nivel disponibles"
    if percentile >= 67:
        return f"en un nivel históricamente alto (percentil {percentile:.0f})"
    if percentile <= 33:
        return f"en un nivel históricamente bajo (percentil {percentile:.0f})"
    return f"en un nivel típico dentro de su historia (percentil {percentile:.0f})"


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



def generate_domain_narrative(results_df: pd.DataFrame, domain_key: str, window_type: str = "rolling_10y") -> str:
    """Builds the full narrative for a domain by combining its series' sentences."""
    domain_series = [k for k, v in DOMAIN_MAP.items() if v == domain_key]
    sentences = [
        generate_series_narrative(results_df, key, window_type)
        for key in domain_series
        if key in SERIES_DISPLAY_NAMES  # skip debt, which has no display name / trend stats
    ]
    return " ".join(sentences)