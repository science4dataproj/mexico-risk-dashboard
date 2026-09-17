import numpy as np
import pandas as pd

from src.analysis.early_warning import (
    rolling_autocorr_lag1, rolling_variance, kendall_trend_test,
    infer_rolling_window_periods, MIN_TOTAL_OBS_FOR_EWS,
)

RANDOM_SEED = 42
N_ANCHOR_DATES = 150

panel = pd.read_csv('data/processed/panel_long.csv', parse_dates=['date'])

SERIES_TO_CHECK = [
    "fx_rate_fix", "cetes_28d", "target_rate", "international_reserves",
    "m1", "m2", "quarterly_gdp", "unemployment_rate", "cpi",
]

def audit_window_type(raw: pd.Series, window_type: str, rng):
    rolling_window = infer_rolling_window_periods(raw)
    if rolling_window is None:
        return None

    valid_dates = raw.dropna().index
    if len(valid_dates) < rolling_window + MIN_TOTAL_OBS_FOR_EWS:
        return None

    candidates = valid_dates[rolling_window + MIN_TOTAL_OBS_FOR_EWS:]
    n = min(N_ANCHOR_DATES, len(candidates))
    if n == 0:
        return None
    anchor_dates = rng.choice(candidates, size=n, replace=False)

    theoretical_p_values = []
    taus = []
    for anchor in anchor_dates:
        if window_type == "rolling_10y":
            start = pd.Timestamp(anchor) - pd.DateOffset(years=10)
            sliced = raw[(raw.index >= start) & (raw.index <= anchor)]
        else:  # full_history
            sliced = raw[raw.index <= anchor]

        ac1_series = rolling_autocorr_lag1(sliced, window=rolling_window).dropna()
        if len(ac1_series) < 12:
            continue
        result = kendall_trend_test(ac1_series)
        if not np.isnan(result["p_value"]):
            theoretical_p_values.append(result["p_value"])
            taus.append(result["tau"])

    if not theoretical_p_values:
        return None

    theoretical_p_values = np.array(theoretical_p_values)
    return {
        "n_replications": len(theoretical_p_values),
        "pct_p_below_0.05": (theoretical_p_values < 0.05).mean() * 100,
        "mean_tau": np.mean(taus),
    }


rng = np.random.default_rng(RANDOM_SEED)
print(f"{'Serie':25s} {'Ventana':15s} {'N réplicas':>10s} {'% p<0.05 (falso+ esperado)':>28s}")
for series_key in SERIES_TO_CHECK:
    raw = (panel[panel.series_key == series_key]
           .dropna(subset=["value"]).sort_values("date")
           .set_index("date")["value"])
    for window_type in ["full_history", "rolling_10y"]:
        result = audit_window_type(raw, window_type, rng)
        if result is None:
            print(f"{series_key:25s} {window_type:15s} {'—':>10s} {'insuficiente historia':>28s}")
        else:
            print(f"{series_key:25s} {window_type:15s} {result['n_replications']:>10d} {result['pct_p_below_0.05']:>27.1f}%")