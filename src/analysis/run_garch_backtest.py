"""
src/analysis/run_garch_backtest.py

Runs the GARCH conditional-volatility trend test on the SAME
pre-crisis windows used by backtest.py, to check whether GARCH detects
instability before known Mexican crises that the CSD backtest (see
Decisions Log) found no significant signal for — directly testing
whether the null result is about the underlying data/phenomenon, or
specific to CSD's particular test statistic.
"""

from src.analysis import _quiet_warnings  # noqa: F401
import pandas as pd
from src.analysis.backtest import KNOWN_CRISES
from src.analysis.early_warning import infer_rolling_window_periods
from src.analysis.garch_comparison import fit_garch_and_test_trend

BACKTEST_LOOKBACK_TARGET_POINTS = 24
MIN_PRE_CRISIS_POINTS = 12

panel = pd.read_csv("data/processed/panel_long.csv", parse_dates=["date"])

rows = []
for crisis_name, config in KNOWN_CRISES.items():
    for series_key in config["series"]:
        raw_series = (
            panel[panel.series_key == series_key]
            .dropna(subset=["value"]).sort_values("date").set_index("date")["value"]
        )
        pre_crisis = raw_series[raw_series.index < config["date"]].dropna()

        window = infer_rolling_window_periods(pre_crisis)
        if window is None:
            rows.append({"crisis_name": crisis_name, "series_key": series_key, "converged": False, "skip_reason": "annual/unrecognized frequency"})
            continue

        trimmed = pre_crisis.tail(window + BACKTEST_LOOKBACK_TARGET_POINTS)
        if len(trimmed) < window + MIN_PRE_CRISIS_POINTS:
            rows.append({"crisis_name": crisis_name, "series_key": series_key, "converged": False, "skip_reason": f"only {len(trimmed)} pre-crisis points"})
            continue

        result = fit_garch_and_test_trend(trimmed.to_numpy(), series_key)
        rows.append({
            "crisis_name": crisis_name, "series_key": series_key,
            "n_points": len(trimmed), "converged": result.converged,
            "skip_reason": result.skip_reason,
            "garch_tau": round(result.garch_tau, 3) if result.converged else None,
            "garch_p": round(result.garch_p_value, 4) if result.converged else None,
            "garch_significant_rising": (result.converged and result.garch_p_value < 0.05 and result.garch_tau > 0),
        })

from statsmodels.stats.multitest import multipletests

df = pd.DataFrame(rows)

valid = df["garch_p"].notna()
df["garch_p_adjusted"] = None
if valid.sum() > 0:
    _, p_adj, _, _ = multipletests(df.loc[valid, "garch_p"], alpha=0.05, method="fdr_bh")
    df.loc[valid, "garch_p_adjusted"] = p_adj
    df["garch_significant_rising"] = False
    df.loc[valid, "garch_significant_rising"] = (
        (df.loc[valid, "garch_p_adjusted"] < 0.05) & (df.loc[valid, "garch_tau"] > 0)
    )

print(df.to_string(index=False))
df.to_csv("data/processed/garch_backtest.csv", index=False)