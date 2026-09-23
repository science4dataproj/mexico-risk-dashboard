"""
src/analysis/run_garch_comparison.py

Repeats the GARCH-vs-CSD comparison on the rolling_10y window instead
of full_history, to check whether the ~3-of-4 agreement found among
"clean" (non-degenerate) GARCH fits on full_history holds on a
shorter, more homogeneous window that isn't mixing multiple decades
of regime changes (fixed vs. floating exchange rate, 2008, COVID) into
a single fit — see SERIES_METADATA.md Decisions Log for the full_history
diagnosis this follows up on.
"""

from src.analysis import _quiet_warnings  # noqa: F401

import pandas as pd
from src.analysis.garch_comparison import fit_garch_and_test_trend

SERIES = ["fx_rate_fix", "cetes_28d", "target_rate", "international_reserves",
          "m1", "m2", "quarterly_gdp", "unemployment_rate", "cpi"]

panel = pd.read_csv("data/processed/panel_long.csv", parse_dates=["date"])
csd_results = pd.read_csv("data/processed/analysis_results.csv")

rows = []
for series_key in SERIES:
    series_df = (panel[panel.series_key == series_key]
                 .dropna(subset=["value"]).sort_values("date"))

    # Same rolling_10y definition already used elsewhere in this
    # project (windows.py / backtest.py): trailing 10 years from the
    # series' own most recent observation, not from "today" globally.
    cutoff = series_df["date"].max() - pd.DateOffset(years=10)
    windowed = series_df[series_df["date"] >= cutoff]
    raw = windowed["value"].to_numpy()

    result = fit_garch_and_test_trend(raw, series_key)

    csd_combined_row = csd_results[
        (csd_results.series_key == series_key)
        & (csd_results.stat_name == "critical_slowing_down_flag")
        & (csd_results.window_type == "rolling_10y")
    ]
    csd_combined_active = bool(csd_combined_row["value"].iloc[0]) if not csd_combined_row.empty else None

    csd_var_row = csd_results[
        (csd_results.series_key == series_key)
        & (csd_results.stat_name == "variance_trend_tau")
        & (csd_results.window_type == "rolling_10y")
    ]
    csd_variance_rising = bool(csd_var_row["flag_significant"].iloc[0]) if not csd_var_row.empty else None

    rows.append({
        "series": series_key, "n_points": len(raw), "converged": result.converged,
        "skip_reason": result.skip_reason,
        "persistence(a+b)": round(result.persistence, 3) if result.converged else None,
        "garch_tau": round(result.garch_tau, 3) if result.converged else None,
        "garch_p": round(result.garch_p_value, 4) if result.converged else None,
        "garch_significant_rising": (result.converged and result.garch_p_value < 0.05 and result.garch_tau > 0),
        "csd_variance_rising": csd_variance_rising,
        "csd_flag_combined": csd_combined_active,
    })

df = pd.DataFrame(rows)
print(df.to_string(index=False))
df.to_csv("data/processed/garch_comparison_rolling10y.csv", index=False)