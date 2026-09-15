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
    "fx_rate_fix": "el tipo de cambio",
    "international_reserves": "las reservas internacionales",
    "m1": "M1",
    "m2": "M2",
    "cetes_28d": "los CETES a 28 días",
    "target_rate": "la tasa objetivo de Banxico",
    "quarterly_gdp": "el PIB trimestral",
    "unemployment_rate": "la tasa de desocupación",
    "cpi": "el INPC",
}


def _get_stat(results_df: pd.DataFrame, series_key: str, window_type: str, stat_name: str):
    match = results_df[
        (results_df["series_key"] == series_key)
        & (results_df["window_type"] == window_type)
        & (results_df["stat_name"] == stat_name)
    ]
    return match["value"].iloc[0] if not match.empty else None


def _level_phrase(percentile: float | None) -> str:
    if percentile is None:
        return "sin datos de nivel disponibles"
    if percentile >= 67:
        return f"en un nivel históricamente alto (percentil {percentile:.0f})"
    if percentile <= 33:
        return f"en un nivel históricamente bajo (percentil {percentile:.0f})"
    return f"en un nivel típico dentro de su historia (percentil {percentile:.0f})"


def _trend_phrase(ac1_tau: float | None, var_tau: float | None) -> str:
    if ac1_tau is None or var_tau is None:
        return "sin suficiente información de tendencia"
    if ac1_tau > 0 and var_tau > 0:
        return "mostrando una tendencia consistente hacia mayor inestabilidad"
    if ac1_tau < 0 and var_tau < 0:
        return "mostrando una tendencia hacia mayor estabilidad"
    return "sin una tendencia clara y consistente de estabilidad o fragilidad"


def generate_series_narrative(results_df: pd.DataFrame, series_key: str, window_type: str = "rolling_10y") -> str:
    """Builds one plain-language sentence describing a single series."""
    display_name = SERIES_DISPLAY_NAMES.get(series_key, series_key)
    percentile = _get_stat(results_df, series_key, window_type, "percentile_rank")
    ac1_tau = _get_stat(results_df, series_key, window_type, "ac1_trend_tau")
    var_tau = _get_stat(results_df, series_key, window_type, "variance_trend_tau")

    level = _level_phrase(percentile)
    trend = _trend_phrase(ac1_tau, var_tau)

    return f"{display_name.capitalize()} está {level}, {trend}."


def generate_domain_narrative(results_df: pd.DataFrame, domain_key: str, window_type: str = "rolling_10y") -> str:
    """Builds the full narrative for a domain by combining its series' sentences."""
    domain_series = [k for k, v in DOMAIN_MAP.items() if v == domain_key]
    sentences = [
        generate_series_narrative(results_df, key, window_type)
        for key in domain_series
        if key in SERIES_DISPLAY_NAMES  # skip debt, which has no display name / trend stats
    ]
    return " ".join(sentences)