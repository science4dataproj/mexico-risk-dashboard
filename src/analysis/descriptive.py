"""
src/analysis/descriptive.py

Computes descriptive statistics (Level 0: location/spread/anomaly
detection; Level 1: distributional shape) for a single series over a
single reference window (see src/analysis/windows.py).

Design choices, documented here rather than left implicit:
  - "Latest value" is always the same observation across all three
    windows — only the historical baseline it's compared against
    changes (confirmed with the project owner before implementation).
  - Period-over-period change is evaluated as a z-score against the
    historical distribution of changes within the window, not as a
    raw percentage with a fabricated confidence interval — a single
    delta between two dates has no natural bootstrap distribution of
    its own, but the population of historical changes does.
  - Every stat with a meaningful null hypothesis carries a raw p-value.
    Multiple-testing correction (Benjamini-Hochberg) is applied
    separately, across a full batch of results, by
    apply_multiple_testing_correction() — never per-series in
    isolation, per SERIES_METADATA.md Decisions Log.
"""

from dataclasses import dataclass

import numpy as np
import pandas as pd
from scipy import stats as scipy_stats
from statsmodels.stats.multitest import multipletests

from src.analysis.windows import WindowResult

N_BOOTSTRAP = 2000
BOOTSTRAP_CI = 0.95
RANDOM_STATE = 42
ROLLING_VOL_PERIODS = 12  # for volatility_zscore; ~1 year for monthly data


def _bootstrap_ci(data: np.ndarray, statistic_fn, n_bootstrap: int = N_BOOTSTRAP) -> tuple[float, float]:
    """Percentile bootstrap CI for a given statistic function."""
    rng = np.random.default_rng(RANDOM_STATE)
    n = len(data)
    boot_stats = np.empty(n_bootstrap)
    for i in range(n_bootstrap):
        sample = rng.choice(data, size=n, replace=True)
        boot_stats[i] = statistic_fn(sample)
    alpha = 1 - BOOTSTRAP_CI
    lo, hi = np.percentile(boot_stats, [100 * alpha / 2, 100 * (1 - alpha / 2)])
    return lo, hi


def _row(stat_name: str, value: float, ci_low: float = np.nan, ci_high: float = np.nan, p_value: float = np.nan) -> dict:
    return {"stat_name": stat_name, "value": value, "ci_low": ci_low, "ci_high": ci_high, "p_value": p_value}


def compute_descriptive_stats(window: WindowResult, series_key: str) -> pd.DataFrame:
    """
    Computes all Level 0 + Level 1 statistics for one series over one
    window. Returns a tidy DataFrame: series_key, window_type,
    window_label, stat_name, value, ci_low, ci_high, p_value.
    """
    data = window.data.dropna()
    values = data.values
    latest_value = data.iloc[-1]
    rows = []

    # --- Location / spread ---
    rows.append(_row("mean", np.mean(values), *_bootstrap_ci(values, np.mean)))
    rows.append(_row("median", np.median(values), *_bootstrap_ci(values, np.median)))
    rows.append(_row("std", np.std(values, ddof=1)))
    rows.append(_row("min", np.min(values)))
    rows.append(_row("max", np.max(values)))
    rows.append(_row("latest_value", latest_value))

    # --- Anomaly detection on the level ---
    mean, std = np.mean(values), np.std(values, ddof=1)
    if std > 0:
        z_score = (latest_value - mean) / std
        z_ci = _bootstrap_ci(
            values, lambda s: (latest_value - np.mean(s)) / np.std(s, ddof=1) if np.std(s, ddof=1) > 0 else np.nan
        )
        z_pvalue = 2 * (1 - scipy_stats.norm.cdf(abs(z_score)))
        rows.append(_row("z_score", z_score, *z_ci, p_value=z_pvalue))

    percentile_rank = scipy_stats.percentileofscore(values, latest_value, kind="mean")
    pct_ci = _bootstrap_ci(values, lambda s: scipy_stats.percentileofscore(s, latest_value, kind="mean"))
    rows.append(_row("percentile_rank", percentile_rank, *pct_ci))

    # --- Anomaly detection on the rate of change ---
    changes = data.diff().dropna()
    if len(changes) >= 8:  # arbitrary but reasonable floor for a meaningful change distribution
        latest_change = changes.iloc[-1]
        change_mean, change_std = np.mean(changes.values), np.std(changes.values, ddof=1)
        if change_std > 0:
            change_z = (latest_change - change_mean) / change_std
            change_ci = _bootstrap_ci(
                changes.values,
                lambda s: (latest_change - np.mean(s)) / np.std(s, ddof=1) if np.std(s, ddof=1) > 0 else np.nan,
            )
            change_pvalue = 2 * (1 - scipy_stats.norm.cdf(abs(change_z)))
            rows.append(_row("change_zscore", change_z, *change_ci, p_value=change_pvalue))

    # --- Volatility clustering signal ---
    rolling_vol = data.rolling(window=ROLLING_VOL_PERIODS, min_periods=ROLLING_VOL_PERIODS // 2).std().dropna()
    if len(rolling_vol) >= 8:
        latest_vol = rolling_vol.iloc[-1]
        vol_mean, vol_std = np.mean(rolling_vol.values), np.std(rolling_vol.values, ddof=1)
        if vol_std > 0:
            vol_z = (latest_vol - vol_mean) / vol_std
            vol_ci = _bootstrap_ci(
                rolling_vol.values,
                lambda s: (latest_vol - np.mean(s)) / np.std(s, ddof=1) if np.std(s, ddof=1) > 0 else np.nan,
            )
            vol_pvalue = 2 * (1 - scipy_stats.norm.cdf(abs(vol_z)))
            rows.append(_row("volatility_zscore", vol_z, *vol_ci, p_value=vol_pvalue))

    # --- Distributional shape (Level 1) ---
    if len(values) >= 8:
        skewness = scipy_stats.skew(values, bias=False)
        skew_ci = _bootstrap_ci(values, lambda s: scipy_stats.skew(s, bias=False))
        rows.append(_row("skewness", skewness, *skew_ci))

        kurt = scipy_stats.kurtosis(values, fisher=True, bias=False)  # excess kurtosis; 0 = normal-like tails
        kurt_ci = _bootstrap_ci(values, lambda s: scipy_stats.kurtosis(s, fisher=True, bias=False))
        rows.append(_row("excess_kurtosis", kurt, *kurt_ci))

        jb_stat, jb_pvalue = scipy_stats.jarque_bera(values)
        # H0 for this row: the data is normally distributed. A significant
        # result here means "non-normal", NOT "anomalous value" — different
        # semantics from the z-score rows above. Documented in README/metadata.
        rows.append(_row("jarque_bera_normality", jb_stat, p_value=jb_pvalue))

    df = pd.DataFrame(rows)
    df.insert(0, "series_key", series_key)
    df.insert(1, "window_type", window.window_type)
    df.insert(2, "window_label", window.label)
    return df


def apply_multiple_testing_correction(results: pd.DataFrame, alpha: float = 0.05) -> pd.DataFrame:
    """
    Applies Benjamini-Hochberg FDR correction across ALL p-values in the
    batch at once (e.g. every series x window x stat combination run in
    one pass) — never per series in isolation, per project convention.
    Rows without a p_value (e.g. mean, median, min, max) are left
    untouched and excluded from the correction.
    """
    results = results.copy()

    # Defensive coercion: guarantees float64 dtype even if the input
    # DataFrame arrived with p_value as dtype "object" (e.g. from
    # concatenating rows that used Python None instead of np.nan for
    # missing numeric values elsewhere in the pipeline).
    results["p_value"] = pd.to_numeric(results["p_value"], errors="coerce")
    results["p_value_adjusted"] = pd.Series(np.nan, index=results.index, dtype="float64")
    results["flag_significant"] = False

    has_pvalue = results["p_value"].notna()
    if has_pvalue.sum() == 0:
        return results

    rejected, p_adjusted, _, _ = multipletests(
        results.loc[has_pvalue, "p_value"], alpha=alpha, method="fdr_bh"
    )
    results.loc[has_pvalue, "p_value_adjusted"] = p_adjusted
    results.loc[has_pvalue, "flag_significant"] = rejected
    return results