"""
src/reporting/composite_index.py

Computes the domain-level fragility scorecard and the composite
fragility index from data/processed/analysis_results.csv.

Design principle (see planning discussion): the score measures RISING
FRAGILITY, not economic performance. It is built exclusively from
trend statistics (ac1_trend_tau, variance_trend_tau,
critical_slowing_down_flag) — never from level z-scores or percentiles.

The composite index is a simple, UNWEIGHTED average of the 5 eligible
domain sub-scores (fiscal_solvency is excluded — see domains.py).

Bilingual design (2026-09): status labels are stored per language, same
pattern as domains.py — see SERIES_METADATA.md, Decisions Log #15.
"""

from dataclasses import dataclass, field

import pandas as pd

from src.reporting.domains import (
    DOMAIN_MAP,
    DOMAIN_METADATA,
    get_composite_domains,
    get_display_name,
    SUPPORTED_LANGUAGES,
)

PRODUCTION_WINDOWS = {"full_history", "rolling_10y"}
TREND_STATS = {"ac1_trend_tau", "variance_trend_tau"}

# Score thresholds and their labels, per language. Order matters:
# first threshold that the score is <= wins.
SCORE_LABELS = [
    (33, {"es": "Sin cambios relevantes", "en": "No notable change"}),
    (66, {"es": "Tendencia a monitorear", "en": "Trend to monitor"}),
    (100, {"es": "Señal fuerte de fragilidad", "en": "Strong fragility signal"}),
]


@dataclass
class DomainScore:
    domain_key: str
    display_name: dict[str, str]
    score: float
    label: dict[str, str]
    n_signals_active: int
    n_signals_possible: int
    narrative: dict[str, str] = field(default_factory=dict)


@dataclass
class CompositeResult:
    composite_score: float
    composite_label: dict[str, str]
    domain_scores: list[DomainScore] = field(default_factory=list)


def label_for_score(score: float) -> dict[str, str]:
    """Returns the {lang: label} dict for a given score."""
    for threshold, label in SCORE_LABELS:
        if score <= threshold:
            return label
    return SCORE_LABELS[-1][1]


def _is_active_trend_signal(row: pd.Series) -> bool:
    return (
        row["stat_name"] in TREND_STATS
        and row["value"] > 0
        and bool(row.get("flag_significant", False))
    )


def _is_active_csd_flag(row: pd.Series) -> bool:
    return row["stat_name"] == "critical_slowing_down_flag" and row["value"] == 1.0


def compute_domain_fragility_score(results_df: pd.DataFrame, domain_key: str) -> DomainScore:
    domain_series = [k for k, v in DOMAIN_MAP.items() if v == domain_key]
    domain_info = DOMAIN_METADATA[domain_key]

    subset = results_df[
        results_df["series_key"].isin(domain_series)
        & results_df["window_type"].isin(PRODUCTION_WINDOWS)
    ]

    trend_rows = subset[subset["stat_name"].isin(TREND_STATS)]
    csd_rows = subset[subset["stat_name"] == "critical_slowing_down_flag"]

    n_possible = len(trend_rows) + len(csd_rows)
    if n_possible == 0:
        return DomainScore(
            domain_key=domain_key,
            display_name=domain_info.display_name,
            score=0.0,
            label=label_for_score(0.0),
            n_signals_active=0,
            n_signals_possible=0,
        )

    n_active_trend = trend_rows.apply(_is_active_trend_signal, axis=1).sum()
    n_active_csd = csd_rows.apply(_is_active_csd_flag, axis=1).sum()

    weighted_active = n_active_trend + (2 * n_active_csd)
    weighted_possible = len(trend_rows) + (2 * len(csd_rows))

    score = 100 * weighted_active / weighted_possible if weighted_possible else 0.0

    return DomainScore(
        domain_key=domain_key,
        display_name=domain_info.display_name,
        score=round(score, 1),
        label=label_for_score(score),
        n_signals_active=int(n_active_trend + n_active_csd),
        n_signals_possible=len(trend_rows) + len(csd_rows),
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