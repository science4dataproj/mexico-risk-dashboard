"""
src/analysis/run_backtest.py

Runnable entry point for the crisis backtest, following the same
`python3 -m src.analysis.run_X` pattern already used by run_analysis.py,
run_reporting.py, and run_garch_comparison.py — backtest.py itself was
never given one, an inconsistency found and fixed 2026-09-17.
"""
from src.analysis import _quiet_warnings  # noqa: F401

import pandas as pd
from src.analysis.backtest import run_backtest

if __name__ == "__main__":
    panel = pd.read_csv("data/processed/panel_long.csv", parse_dates=["date"])
    results = run_backtest(panel)
    results.to_csv("data/processed/backtest_results.csv", index=False)
    print()
    print(results[[
        "crisis_name", "series_key", "skipped", "n_pre_crisis_points",
        "ac1_tau", "ac1_p_adjusted", "var_tau", "var_p_adjusted", "flag",
    ]].to_string())