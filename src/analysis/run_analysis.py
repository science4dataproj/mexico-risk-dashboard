"""
src/analysis/run_analysis.py

Runs the full analysis pipeline over every series in the unified panel:
  1. For each series, build the 3 reference windows.
  2. For each (series, window), compute Level 0/1 descriptive stats and
     the critical-slowing-down early-warning diagnostic.
  3. Combine everything into one tidy results table.
  4. Apply Benjamini-Hochberg correction ONCE, across the entire batch
     of p-values (never per series in isolation) — per project
     convention (SERIES_METADATA.md, Decisions Log).

Output: data/processed/analysis_results.csv
"""
from src.analysis import _quiet_warnings  # noqa: F401
from pathlib import Path

import pandas as pd
import numpy as np

from src.analysis.descriptive import compute_descriptive_stats, apply_multiple_testing_correction
from src.analysis.early_warning import (
    compute_early_warning_stats,
    infer_rolling_window_periods,
    MIN_TOTAL_OBS_FOR_EWS,
)
from src.analysis.windows import get_all_windows
from src.config import DATA_PROCESSED_DIR

PANEL_PATH = Path(DATA_PROCESSED_DIR) / "panel_long.csv"
RESULTS_PATH = Path(DATA_PROCESSED_DIR) / "analysis_results.csv"


def _skip_row(series_key: str, window_type: str, window_label: str, reason: str) -> dict:
    """
    Explicit placeholder row for a skipped early-warning analysis —
    never silently omit a series/window without saying why, consistent
    with how the rest of this project handles gaps and limitations.
    """
    return {
        "series_key": series_key,
        "window_type": window_type,
        "window_label": window_label,
        "stat_name": "early_warning_skipped",
        "value": np.nan,
        "ci_low": np.nan,
        "ci_high": np.nan,
        "p_value": np.nan,
        "skip_reason": reason,
    }


def load_panel() -> pd.DataFrame:
    if not PANEL_PATH.exists():
        raise FileNotFoundError(
            f"{PANEL_PATH} not found. Run `python -m src.transform.clean` first."
        )
    return pd.read_csv(PANEL_PATH, parse_dates=["date"])


from tqdm import tqdm


def run_analysis() -> pd.DataFrame:
    panel = load_panel()
    all_results = []

    # Construir la lista completa de combinaciones serie×ventana primero,
    # para que tqdm conozca el total desde el inicio y pueda mostrar
    # porcentaje y tiempo estimado, no solo un contador sin referencia.
    series_window_pairs = []
    for series_key, group in panel.groupby("series_key"):
        series = group.set_index("date")["value"].dropna().sort_values()
        if series.empty:
            continue
        for window in get_all_windows(series):
            series_window_pairs.append((series_key, window))

    progress = tqdm(
        series_window_pairs,
        desc="Analizando series",
        unit="serie-ventana",
        ncols=80,  # ancho fijo, evita que la barra se deforme en terminales angostas
    )

    for series_key, window in progress:
        progress.set_postfix_str(f"{series_key} ({window.window_type})")

        desc_df = compute_descriptive_stats(window, series_key)
        all_results.append(desc_df)

        rolling_window = infer_rolling_window_periods(window.data)
        if rolling_window is None:
            all_results.append(pd.DataFrame([_skip_row(
                series_key, window.window_type, window.label,
                "Series frequency is annual (or unrecognized) — insufficient "
                "resolution for rolling autocorrelation/variance trend analysis.",
            )]))
            continue

        if len(window.data) < rolling_window + MIN_TOTAL_OBS_FOR_EWS:
            all_results.append(pd.DataFrame([_skip_row(
                series_key, window.window_type, window.label,
                f"Only {len(window.data)} observations in this window; need at least "
                f"~{rolling_window + MIN_TOTAL_OBS_FOR_EWS} for a stable trend estimate.",
            )]))
            continue

        ews_df = compute_early_warning_stats(window, series_key, rolling_window=rolling_window)
        all_results.append(ews_df)

    combined = pd.concat(all_results, ignore_index=True)
    corrected = apply_multiple_testing_correction(combined)
    return corrected

def save_results(results: pd.DataFrame) -> Path:
    Path(DATA_PROCESSED_DIR).mkdir(parents=True, exist_ok=True)
    results.to_csv(RESULTS_PATH, index=False)
    return RESULTS_PATH


def run() -> Path:
    results = run_analysis()
    return save_results(results)


if __name__ == "__main__":
    path = run()
    print(f"Saved analysis results to {path}")

    # Quick console summary — not the final report, just a sanity check
    df = pd.read_csv(path)
    n_series = df["series_key"].nunique()
    n_flagged = df["flag_significant"].sum() if "flag_significant" in df.columns else 0
    n_skipped = (df["stat_name"] == "early_warning_skipped").sum()
    print(f"Series analyzed: {n_series}")
    print(f"Statistically significant flags (after FDR correction): {n_flagged}")
    print(f"Early-warning analyses skipped (insufficient resolution): {n_skipped}")