"""
src/reporting/narrative.py

Generates deterministic, template-based narrative text for each domain,
using the underlying level statistics (percentile_rank, z_score) from
analysis_results.csv. Template-based, not free text generation, so the
output is reproducible and auditable on every pipeline run.

Bilingual design (2026-09): every phrase is pulled from a central
PHRASES dict keyed by language code, computed from the same underlying
numbers in the same function call — the two languages can never say
substantively different things about the data, only differ in wording.
See SERIES_METADATA.md, Decisions Log #15.
"""

import pandas as pd

from src.reporting.domains import DOMAIN_MAP, SUPPORTED_LANGUAGES

# series_key -> {lang: (display_name, is_plural)}
# Grammatical number can legitimately differ by language (e.g. CETES is
# phrased as a plural subject in Spanish but as "the CETES rate",
# singular, in natural English) — stored per language, not shared.
SERIES_DISPLAY_NAMES: dict[str, dict[str, tuple[str, bool]]] = {
    "fx_rate_fix": {"es": ("el tipo de cambio", False), "en": ("the exchange rate", False)},
    "international_reserves": {"es": ("las reservas internacionales", True), "en": ("international reserves", True)},
    "m1": {"es": ("M1", False), "en": ("M1", False)},
    "m2": {"es": ("M2", False), "en": ("M2", False)},
    "cetes_28d": {"es": ("los CETES a 28 días", True), "en": ("the 28-day CETES rate", False)},
    "target_rate": {"es": ("la tasa objetivo de Banxico", False), "en": ("Banxico's target rate", False)},
    "quarterly_gdp": {"es": ("el PIB trimestral", False), "en": ("quarterly GDP", False)},
    "unemployment_rate": {"es": ("la tasa de desocupación", False), "en": ("the unemployment rate", False)},
    "cpi": {"es": ("el INPC", False), "en": ("the CPI", False)},
}

PHRASES = {
    "es": {
        "no_level_data": "sin datos de nivel disponibles",
        "no_trend_data": "sin suficiente información de tendencia",
        "trend_consistent_up": "mostrando una tendencia consistente y estadísticamente significativa hacia mayor inestabilidad",
        "trend_consistent_down": "mostrando una tendencia consistente y estadísticamente significativa hacia mayor estabilidad",
        "trend_mixed": "mostrando una tendencia significativa solo en uno de los dos indicadores de estabilidad, sin un patrón consistente",
        "trend_none": "sin una tendencia estadísticamente significativa de estabilidad o fragilidad",
    },
    "en": {
        "no_level_data": "no level data available",
        "no_trend_data": "with insufficient trend data available",
        "trend_consistent_up": "showing a statistically significant, consistent trend toward greater instability",
        "trend_consistent_down": "showing a statistically significant, consistent trend toward greater stability",
        "trend_mixed": "showing a significant trend in only one of the two stability indicators, with no consistent pattern",
        "trend_none": "showing no statistically significant trend toward stability or fragility",
    },
}


def _ordinal_en(n: int) -> str:
    """21 -> '21st', 4 -> '4th', 97 -> '97th'. English percentile phrasing
    needs correct ordinal suffixes — 'the 21th percentile' is a visible
    error to a native reader, unlike Spanish which doesn't need this."""
    if 10 <= n % 100 <= 20:
        suffix = "th"
    else:
        suffix = {1: "st", 2: "nd", 3: "rd"}.get(n % 10, "th")
    return f"{n}{suffix}"


def _get_stat(results_df: pd.DataFrame, series_key: str, window_type: str, stat_name: str):
    match = results_df[
        (results_df["series_key"] == series_key)
        & (results_df["window_type"] == window_type)
        & (results_df["stat_name"] == stat_name)
    ]
    return match["value"].iloc[0] if not match.empty else None


def _get_significance(results_df: pd.DataFrame, series_key: str, window_type: str, stat_name: str) -> bool:
    match = results_df[
        (results_df["series_key"] == series_key)
        & (results_df["window_type"] == window_type)
        & (results_df["stat_name"] == stat_name)
    ]
    if match.empty or "flag_significant" not in match.columns:
        return False
    val = match["flag_significant"].iloc[0]
    return bool(val) if pd.notna(val) else False


def _level_phrase(percentile: float | None, lang: str) -> str:
    p = PHRASES[lang]
    if percentile is None:
        return p["no_level_data"]

    if lang == "en":
        ord_str = _ordinal_en(round(percentile))
        if percentile >= 67:
            return f"at a historically high level ({ord_str} percentile)"
        if percentile <= 33:
            return f"at a historically low level ({ord_str} percentile)"
        return f"at a typical level relative to its history ({ord_str} percentile)"

    # es
    if percentile >= 67:
        return f"en un nivel históricamente alto (percentil {percentile:.0f})"
    if percentile <= 33:
        return f"en un nivel históricamente bajo (percentil {percentile:.0f})"
    return f"en un nivel típico dentro de su historia (percentil {percentile:.0f})"


def _trend_phrase(ac1_tau, ac1_sig, var_tau, var_sig, lang: str) -> str:
    p = PHRASES[lang]
    if ac1_tau is None or var_tau is None:
        return p["no_trend_data"]

    ac1_rising = ac1_sig and ac1_tau > 0
    var_rising = var_sig and var_tau > 0
    ac1_falling = ac1_sig and ac1_tau < 0
    var_falling = var_sig and var_tau < 0

    if ac1_rising and var_rising:
        return p["trend_consistent_up"]
    if ac1_falling and var_falling:
        return p["trend_consistent_down"]
    if ac1_sig or var_sig:
        return p["trend_mixed"]
    return p["trend_none"]


def generate_series_narrative(
    results_df: pd.DataFrame,
    series_key: str,
    window_type: str = "rolling_10y",
    lang: str = "es",
) -> str:
    """Builds one plain-language sentence describing a single series,
    in the requested language (default Spanish, for backward
    compatibility with existing callers/tests)."""
    if lang not in SUPPORTED_LANGUAGES:
        raise ValueError(f"Unsupported language '{lang}'. Supported: {SUPPORTED_LANGUAGES}")

    display_name, is_plural = SERIES_DISPLAY_NAMES.get(series_key, {}).get(lang, (series_key, False))
    if lang == "es":
        verb = "están" if is_plural else "está"
    else:
        verb = "are" if is_plural else "is"

    percentile = _get_stat(results_df, series_key, window_type, "percentile_rank")
    ac1_tau = _get_stat(results_df, series_key, window_type, "ac1_trend_tau")
    ac1_sig = _get_significance(results_df, series_key, window_type, "ac1_trend_tau")
    var_tau = _get_stat(results_df, series_key, window_type, "variance_trend_tau")
    var_sig = _get_significance(results_df, series_key, window_type, "variance_trend_tau")

    level = _level_phrase(percentile, lang)
    trend = _trend_phrase(ac1_tau, ac1_sig, var_tau, var_sig, lang)

    sentence = f"{display_name} {verb} {level}, {trend}."
    return sentence[0].upper() + sentence[1:]


def generate_domain_narrative(
    results_df: pd.DataFrame,
    domain_key: str,
    window_type: str = "rolling_10y",
    lang: str = "es",
) -> str:
    domain_series = [k for k, v in DOMAIN_MAP.items() if v == domain_key]
    sentences = [
        generate_series_narrative(results_df, key, window_type, lang)
        for key in domain_series
        if key in SERIES_DISPLAY_NAMES
    ]
    return " ".join(sentences)


def generate_domain_narrative_bilingual(
    results_df: pd.DataFrame, domain_key: str, window_type: str = "rolling_10y"
) -> dict[str, str]:
    """Convenience function: returns {"es": ..., "en": ...} in one call,
    used by run_reporting.py to build the bilingual JSON output."""
    return {
        lang: generate_domain_narrative(results_df, domain_key, window_type, lang)
        for lang in SUPPORTED_LANGUAGES
    }


def generate_composite_technical_summary(domain_scores: list, composite_score: float) -> dict[str, str]:
    """
    Builds a technical, template-generated summary of the composite
    index: how many (and which) domains currently show a "monitor" or
    "fragile" status, out of the total evaluated. This is the composite
    index's equivalent of a per-series narrative — deterministic, built
    from the same domain_scores the JSON already contains, not a new
    calculation.
    """
    flagged = [d for d in domain_scores if d.label.status_id != "stable"]
    n_total = len(domain_scores)
    n_flagged = len(flagged)

    names_es = ", ".join(d.display_name["es"] for d in flagged)
    names_en = ", ".join(d.display_name["en"] for d in flagged)

    if n_flagged == 0:
        return {
            "es": f"El índice compuesto es {composite_score:.1f}, promedio no ponderado de {n_total} dominios. Ninguno de los {n_total} dominios evaluados muestra actualmente una señal de fragilidad a vigilar o fuerte.",
            "en": f"The composite index is {composite_score:.1f}, an unweighted average across {n_total} domains. None of the {n_total} evaluated domains currently show a monitor-level or strong fragility signal.",
        }

    verb_es = "muestra" if n_flagged == 1 else "muestran"
    dominio_es = "dominio" if n_flagged == 1 else "dominios"
    verb_en = "shows" if n_flagged == 1 else "show"
    domain_en = "domain" if n_flagged == 1 else "domains"

    return {
        "es": f"El índice compuesto es {composite_score:.1f}, promedio no ponderado de {n_total} dominios. {n_flagged} de {n_total} {dominio_es} {verb_es} una señal de fragilidad a vigilar o fuerte: {names_es}.",
        "en": f"The composite index is {composite_score:.1f}, an unweighted average across {n_total} domains. {n_flagged} of {n_total} {domain_en} {verb_en} a monitor-level or strong fragility signal: {names_en}.",
    }