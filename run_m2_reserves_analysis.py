from src.analysis import _quiet_warnings  # noqa: F401
import pandas as pd

from src.transform.derived_series import compute_m2_reserves_ratio
from src.analysis.windows import get_all_windows
from src.analysis.early_warning import compute_early_warning_stats, infer_rolling_window_periods
from src.analysis.backtest import backtest_series, KNOWN_CRISES

panel = pd.read_csv("data/processed/panel_long.csv", parse_dates=["date"])
ratio = compute_m2_reserves_ratio(panel)

print(f"M2/reservas: {len(ratio)} puntos mensuales, de {ratio.index.min().date()} a {ratio.index.max().date()}\n")

print("=== Estado actual (full_history / rolling_10y) ===")
for window in get_all_windows(ratio):
    rolling_window = infer_rolling_window_periods(window.data)
    if rolling_window is None:
        print(f"{window.window_type}: sin ventana rodante determinable")
        continue
    stats_df = compute_early_warning_stats(window, "m2_reserves_ratio", rolling_window=rolling_window)
    print(f"\n--- {window.window_type} ---")
    print(stats_df[["stat_name", "value", "p_value"]].to_string(index=False))

print("\n=== Backtest contra crisis conocidas ===")
for crisis_name in KNOWN_CRISES:
    result = backtest_series(ratio, crisis_name, "m2_reserves_ratio")
    print(f"\n{crisis_name}:", result)