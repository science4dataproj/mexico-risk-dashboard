import pandas as pd
from src.analysis.backtest import (
    generate_control_dates, _trend_at_anchor, ALL_CRISIS_DATES,
)
from src.analysis.early_warning import infer_rolling_window_periods

panel = pd.read_csv('data/processed/panel_long.csv', parse_dates=['date'])

for series_key in ["fx_rate_fix", "m1"]:
    raw = (panel[panel.series_key == series_key]
           .dropna(subset=["value"]).sort_values("date")
           .set_index("date")["value"])
    window = infer_rolling_window_periods(raw)
    control_dates = generate_control_dates(raw, ALL_CRISIS_DATES, n_controls=500)
    results = [_trend_at_anchor(raw, d, window) for d in control_dates]
    results = [r for r in results if r is not None]
    ac1_taus = [r["ac1_tau"] for r in results]

    print(f"\n=== {series_key} (n={len(ac1_taus)} controles) ===")
    print(f"  Media: {pd.Series(ac1_taus).mean():.3f}")
    print(f"  % de controles con |tau| > 0.9: {(pd.Series(ac1_taus).abs() > 0.9).mean()*100:.1f}%")
    print(f"  % de controles con |tau| > 0.7: {(pd.Series(ac1_taus).abs() > 0.7).mean()*100:.1f}%")
    print(f"  Mínimo: {min(ac1_taus):.3f}  Máximo: {max(ac1_taus):.3f}")