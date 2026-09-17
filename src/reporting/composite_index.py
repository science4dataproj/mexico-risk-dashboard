"""
src/reporting/composite_index.py

Computes the domain-level fragility scorecard and the composite
fragility index from data/processed/analysis_results.csv.

Design principle: the score measures RISING FRAGILITY, not economic
performance. It is built exclusively from trend statistics
(ac1_trend_tau, variance_trend_tau, critical_slowing_down_flag) —
never from level z-scores or percentiles.

The composite index is a simple, UNWEIGHTED average of the 5 eligible
domain sub-scores (fiscal_solvency is excluded — see domains.py).

Bilingual design: status labels are stored per language. Each label
also carries a language-independent `status_id` ("stable" | "monitor"
| "fragile") so downstream consumers (the frontend, the stakeholder
narrative lookup) never need to string-match a translated label to
know which status band a score falls into.
"""

from dataclasses import dataclass, field

import pandas as pd

from src.reporting.domains import (
    DOMAIN_MAP,
    DOMAIN_METADATA,
    get_composite_domains,
)

PRODUCTION_WINDOWS = {"full_history", "rolling_10y"}
TREND_STATS = {"ac1_trend_tau", "variance_trend_tau"}

# (upper_threshold, status_id, {lang: label})
SCORE_LABELS = [
    (33, "stable", {"es": "Sin cambios relevantes", "en": "No notable change"}),
    (66, "monitor", {"es": "Tendencia a monitorear", "en": "Trend to monitor"}),
    (100, "fragile", {"es": "Señal fuerte de fragilidad", "en": "Strong fragility signal"}),
]


@dataclass
class ScoreLabel:
    status_id: str
    text: dict[str, str]


@dataclass
class DomainScore:
    domain_key: str
    display_name: dict[str, str]
    score: float
    label: ScoreLabel
    n_signals_active: int
    n_signals_possible: int


@dataclass
class CompositeResult:
    composite_score: float
    composite_label: ScoreLabel
    domain_scores: list[DomainScore] = field(default_factory=list)


def label_for_score(score: float) -> ScoreLabel:
    for threshold, status_id, text in SCORE_LABELS:
        if score <= threshold:
            return ScoreLabel(status_id=status_id, text=text)
    last = SCORE_LABELS[-1]
    return ScoreLabel(status_id=last[1], text=last[2])


def _is_active_trend_signal(row: pd.Series) -> bool:
    return (
        row["stat_name"] in TREND_STATS
        and row["value"] > 0
        and bool(row.get("flag_significant", False))
    )


def _is_active_csd_flag(row: pd.Series) -> bool:
    return row["stat_name"] == "critical_slowing_down_flag" and row["value"] == 1.0

def is_csd_active(results_df: pd.DataFrame, series_key: str, window_type: str) -> bool:
    """
    Single source of truth for 'is the combined CSD signal really
    active', decided ONLY from the post-FDR-correction significance of
    the two individual stats — never from critical_slowing_down_flag's
    own 'value' column, which is computed before correction exists and
    can disagree with the corrected result (found in production
    2026-09-16 for cetes_28d: value=1 pre-correction, but neither
    individual stat survived FDR — see SERIES_METADATA.md Decisions Log).
    """
    subset = results_df[
        (results_df["series_key"] == series_key)
        & (results_df["window_type"] == window_type)
        & (results_df["stat_name"].isin(["ac1_trend_tau", "variance_trend_tau"]))
    ]
    ac1_row = subset[subset["stat_name"] == "ac1_trend_tau"]
    var_row = subset[subset["stat_name"] == "variance_trend_tau"]
    if ac1_row.empty or var_row.empty:
        return False

    ac1_active = bool(ac1_row["flag_significant"].iloc[0]) and ac1_row["value"].iloc[0] > 0
    var_active = bool(var_row["flag_significant"].iloc[0]) and var_row["value"].iloc[0] > 0
    return ac1_active and var_active

def compute_domain_fragility_score(results_df: pd.DataFrame, domain_key: str) -> DomainScore:
    domain_series = [k for k, v in DOMAIN_MAP.items() if v == domain_key]
    domain_info = DOMAIN_METADATA[domain_key]

    subset = results_df[
        results_df["series_key"].isin(domain_series)
        & results_df["window_type"].isin(PRODUCTION_WINDOWS)
    ]

    trend_rows = subset[subset["stat_name"].isin(TREND_STATS)]

    # Enumerar combinaciones serie×ventana posibles para saber cuántas
    # banderas CSD son evaluables, sin depender de la columna 'value'
    # ya calculada de forma incorrecta en early_warning.py.
    series_window_pairs = subset[["series_key", "window_type"]].drop_duplicates()
    n_csd_possible = len(series_window_pairs)
    n_csd_active = sum(
        is_csd_active(results_df, row.series_key, row.window_type)
        for row in series_window_pairs.itertuples()
    )

    n_possible = len(trend_rows) + n_csd_possible
    if n_possible == 0:
        return DomainScore(
            domain_key=domain_key, display_name=domain_info.display_name,
            score=0.0, label=label_for_score(0.0),
            n_signals_active=0, n_signals_possible=0,
        )

    n_active_trend = trend_rows.apply(_is_active_trend_signal, axis=1).sum()

    weighted_active = n_active_trend + (2 * n_csd_active)
    weighted_possible = len(trend_rows) + (2 * n_csd_possible)

    score = 100 * weighted_active / weighted_possible if weighted_possible else 0.0

    return DomainScore(
        domain_key=domain_key, display_name=domain_info.display_name,
        score=round(score, 1), label=label_for_score(score),
        n_signals_active=int(n_active_trend + n_csd_active),
        n_signals_possible=len(trend_rows) + n_csd_possible,
    )


def compute_composite_index(results_df: pd.DataFrame) -> CompositeResult:
    eligible_domains = get_composite_domains()
    domain_scores = [
        compute_domain_fragility_score(results_df, domain_key)
        for domain_key in eligible_domains
    ]

    composite_score = round(sum(d.score for d in domain_scores) / len(domain_scores), 1)

    return CompositeResult(
        composite_score=composite_score,
        composite_label=label_for_score(composite_score),
        domain_scores=domain_scores,
    )