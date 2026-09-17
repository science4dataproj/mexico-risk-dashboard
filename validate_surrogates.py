import pandas as pd
from src.analysis.surrogates import surrogate_trend_test, rolling_autocorr_lag1_array
from src.analysis.early_warning import infer_rolling_window_periods

panel = pd.read_csv('data/processed/panel_long.csv', parse_dates=['date'])

for series_key in ["fx_rate_fix", "m1"]:
    raw_full = (panel[panel.series_key == series_key]
                .dropna(subset=["value"]).sort_values("date"))
    raw_values = raw_full["value"].values
    raw_series_for_window = raw_full.set_index("date")["value"]  # infer_rolling_window_periods necesita el índice de fecha

    window = infer_rolling_window_periods(raw_series_for_window)
    print(f"\n{series_key}: ventana correcta = {window}")

    result = surrogate_trend_test(raw_values, window=window, stat_fn=rolling_autocorr_lag1_array, n_surrogates=200)
    if result is None:
        print(f"  No se pudo calcular (ver ajuste ARMA o datos insuficientes)")
    else:
        print(f"  tau={result.real_tau:.3f}  p={result.p_value:.4f}  (n_surrogates={result.n_surrogates_used})")