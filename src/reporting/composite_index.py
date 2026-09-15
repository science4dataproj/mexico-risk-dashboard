"""
src/reporting/composite_index.py

Computes the domain-level fragility scorecard and the composite
fragility index from data/processed/analysis_results.csv.

Design principle (see planning discussion): the score measures RISING
FRAGILITY, not economic performance. It is built exclusively from
trend statistics (ac1_trend_tau, variance_trend_tau,
critical_slowing_down_flag) — never from level z-scores or percentiles.
This avoids having to decide, inside the composite number, whether a
high or low LEVEL is "good" or "bad" for a given indicator (ambiguous
and domain-specific) — that judgment stays in the narrative text, where
it can be explained with nuance, not silently baked into a single score.

The composite index is a simple, UNWEIGHTED average of the 5 eligible
domain sub-scores (fiscal_solvency is excluded — see domains.py). Equal
weighting is a deliberate, documented choice: no domain counts more
just because it happens to track more series.
"""

from dataclasses import dataclass, field

import pandas as pd

from src.reporting.domains import (
    DOMAIN_MAP,
    DOMAIN_METADATA,
    get_composite_domains,
)

# Trend statistics that count as "fragility signals" for the score.
# Only full_history and rolling_10y windows are used — since_last_break
# was retired from the production pipeline (see SERIES_METADATA.md,
# Decisions Log #11) and should never reach this module in practice,
# but we filter explicitly here too, defensively.
PRODUCTION_WINDOWS = {"full_history", "rolling_10y"}
TREND_STATS = {"ac1_trend_tau", "variance_trend_tau"}

SCORE_LABELS = [
    (33, "Sin cambios relevantes"),
    (66, "Tendencia a monitorear"),
    (100, "Señal fuerte de fragilidad"),
]


@dataclass
class DomainScore:
    domain_key: str
    display_name: str
    score: float
    label: str
    n_signals_active: int
    n_signals_possible: int
    narrative: str = ""


@dataclass
class CompositeResult:
    composite_score: float
    composite_label: str
    domain_scores: list[DomainScore] = field(default_factory=list)


def label_for_score(score: float) -> str:
    for threshold, label in SCORE_LABELS:
        if score <= threshold:
            return label
    return SCORE_LABELS[-1][1]  # fallback, should be unreachable given 0-100 range


def _is_active_trend_signal(row: pd.Series) -> bool:
    """A trend stat counts as an active fragility signal if it's
    positive (rising) AND statistically significant post-FDR-correction."""
    return (
        row["stat_name"] in TREND_STATS
        and row["value"] > 0
        and bool(row.get("flag_significant", False))
    )


def _is_active_csd_flag(row: pd.Series) -> bool:
    return row["stat_name"] == "critical_slowing_down_flag" and row["value"] == 1.0


def compute_domain_fragility_score(results_df: pd.DataFrame, domain_key: str) -> DomainScore:
    """
    Computes the fragility sub-score for one domain.

    Score = 100 * (weighted count of active signals) / (possible signals),
    where a critical_slowing_down_flag counts double (it's the combined,
    stronger signal — both AC1 and variance rising together), and each
    individual trend stat counts once.
    """
    domain_series = [k for k, v in DOMAIN_MAP.items() if v == domain_key]
    domain_info = DOMAIN_METADATA[domain_key]

    subset = results_df[
        results_df["series_key"].isin(domain_series)
        & results_df["window_type"].isin(PRODUCTION_WINDOWS)
    ]

    trend_rows = subset[subset["stat_name"].isin(TREND_STATS)]
    csd_rows = subset[subset["stat_name"] == "critical_slowing_down_flag"]

    n_possible = len(trend_rows) + len(csd_rows)  # each CSD row also "possible" to fire
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

    # CSD flags count double: they represent the stronger, combined signal.
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
    """
    Computes all domain sub-scores and the unweighted composite index
    across the 5 domains eligible for the composite
    (fiscal_solvency is excluded — see domains.py).
    """
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