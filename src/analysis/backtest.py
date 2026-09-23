"""
src/analysis/backtest.py

Backtests the CSD (critical slowing down) early-warning signal against
known historical Mexican economic crises: does the rolling
autocorrelation/variance trend, computed using ONLY data available
before the crisis date, show a statistically significant rising trend
using the ARMA-surrogate method (Dakos et al., 2012)?

Design note — simplified from earlier versions: this used to require a
separate "Window B" (how many pre-crisis points feed Kendall's tau) and
a hand-built set of "control dates" sampled from real history. Both
were retired: the surrogate method's null distribution is generated
internally (synthetic series with no genuine trend, matching the real
series' short-term correlation), which is the properly-calibrated
replacement for both. See SERIES_METADATA.md, Decisions Log.
"""

import pandas as pd
import numpy as np
from src.analysis.early_warning import infer_rolling_window_periods
from src.analysis.surrogates import (
    surrogate_trend_test,
    rolling_autocorr_lag1_array,
    rolling_variance_array,
)

N_SURROGATES_BACKTEST = 200
MIN_PRE_CRISIS_POINTS = 12

ALL_NINE_SERIES = [
    "fx_rate_fix", "cetes_28d", "target_rate", "international_reserves",
    "m1", "m2", "quarterly_gdp", "unemployment_rate", "cpi",
]

KNOWN_CRISES = {
    "2008_financial_crisis": {"date": pd.Timestamp("2008-09-01"), "series": ALL_NINE_SERIES},
    "2014_oil_collapse": {"date": pd.Timestamp("2014-06-01"), "series": ALL_NINE_SERIES},
    "1994_tequila": {"date": pd.Timestamp("1994-12-01"), "series": ["fx_rate_fix", "quarterly_gdp", "cpi"]},
}


BACKTEST_LOOKBACK_TARGET_POINTS = 24  # cuántos puntos de la ESTADÍSTICA DERIVADA
                                        # (no de los datos crudos) queremos probar —
                                        # mismo objetivo que la "Ventana B" original

from statsmodels.stats.multitest import multipletests

def add_significance(results_df: pd.DataFrame, alpha: float = 0.05) -> pd.DataFrame:
    """Applies Benjamini-Hochberg FDR correction across the full batch
    of backtest p-values — same discipline used throughout production.
    See SERIES_METADATA.md Decisions Log for the earlier omission this fixes."""
    results_df = results_df.copy()
    results_df["ac1_p_adjusted"] = np.nan
    results_df["var_p_adjusted"] = np.nan

    valid = results_df["ac1_p"].notna() & results_df["var_p"].notna()
    if valid.sum() == 0:
        results_df["flag"] = False
        return results_df

    combined_p = pd.concat([results_df.loc[valid, "ac1_p"], results_df.loc[valid, "var_p"]], ignore_index=False)
    _, p_adj, _, _ = multipletests(combined_p, alpha=alpha, method="fdr_bh")

    n_valid = valid.sum()
    results_df.loc[valid, "ac1_p_adjusted"] = p_adj[:n_valid]
    results_df.loc[valid, "var_p_adjusted"] = p_adj[n_valid:]

    results_df["flag"] = False
    results_df.loc[valid, "flag"] = (
        (results_df.loc[valid, "ac1_p_adjusted"] < alpha)
        & (results_df.loc[valid, "var_p_adjusted"] < alpha)
        & (results_df.loc[valid, "ac1_tau"] > 0)
        & (results_df.loc[valid, "var_tau"] > 0)
    )
    return results_df

def backtest_series(raw_series: pd.Series, crisis_name: str, series_key: str) -> dict:
    crisis_date = KNOWN_CRISES[crisis_name]["date"]
    pre_crisis = raw_series[raw_series.index < crisis_date].dropna()

    # en backtest_series(), antes de llamar infer_rolling_window_periods():
    if len(pre_crisis) == 0:
        return {"crisis_name": crisis_name, "series_key": series_key, "skipped": True,
                "skip_reason": "no data available before this crisis date (series starts after it)"}

    window = infer_rolling_window_periods(pre_crisis)
    if window is None:
        return {"crisis_name": crisis_name, "series_key": series_key, "skipped": True,
                "skip_reason": "annual or unrecognized frequency"}

    # Recorta a una ventana RECIENTE antes de la crisis, no a toda la
    # historia disponible — un sistema de alerta temprana pregunta "¿algo
    # cambió recientemente?", no "¿hubo alguna vez una tendencia en
    # décadas de historia?". Ver SERIES_METADATA.md, Decisions Log, para
    # el error real que esto corrige (encontrado 2026-09-16).
    lookback_raw_points = window + BACKTEST_LOOKBACK_TARGET_POINTS
    trimmed = pre_crisis.tail(lookback_raw_points)

    if len(trimmed) < window + MIN_PRE_CRISIS_POINTS:
        return {"crisis_name": crisis_name, "series_key": series_key, "skipped": True,
                "skip_reason": f"only {len(trimmed)} points in the recent pre-crisis window, need at least {window + MIN_PRE_CRISIS_POINTS}"}

    ac1_result = surrogate_trend_test(trimmed.values, window, rolling_autocorr_lag1_array, n_surrogates=N_SURROGATES_BACKTEST)
    var_result = surrogate_trend_test(trimmed.values, window, rolling_variance_array, n_surrogates=N_SURROGATES_BACKTEST)

    if ac1_result is None or var_result is None:
        return {"crisis_name": crisis_name, "series_key": series_key, "skipped": True,
                "skip_reason": "surrogate test failed (ARMA fit or insufficient rolling-stat points)"}

    flag = (
        ac1_result.real_tau > 0 and var_result.real_tau > 0
        and ac1_result.p_value < 0.05 and var_result.p_value < 0.05
    )

    return {
        "crisis_name": crisis_name, "series_key": series_key, "skipped": False,
        "n_pre_crisis_points": len(trimmed),  # ahora refleja el recorte real, no toda la historia
        "ac1_tau": ac1_result.real_tau, "ac1_p": ac1_result.p_value,
        "var_tau": var_result.real_tau, "var_p": var_result.p_value,
        "flag": flag,
    }


from tqdm import tqdm


def run_backtest(panel_long: pd.DataFrame) -> pd.DataFrame:
    tasks = [
        (crisis_name, series_key)
        for crisis_name, config in KNOWN_CRISES.items()
        for series_key in config["series"]
    ]

    rows = []
    progress = tqdm(tasks, desc="Backtesting crisis", unit="serie-crisis", ncols=80)
    for crisis_name, series_key in progress:
        progress.set_postfix_str(f"{crisis_name[:20]} / {series_key}")

        raw = (
            panel_long[panel_long["series_key"] == series_key]
            .dropna(subset=["value"]).sort_values("date").set_index("date")["value"]
        )
        rows.append(backtest_series(raw, crisis_name, series_key))

    return add_significance(pd.DataFrame(rows))