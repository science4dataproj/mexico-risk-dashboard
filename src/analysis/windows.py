"""
src/analysis/windows.py

Builds the three reference windows used to judge whether a given
observation is "normal" or anomalous:

  1. full_history  — the entire available series.
  2. rolling_10y    — trailing 10 years from the most recent observation.
                       Justification: ~10 years is the conventional rule
                       of thumb for spanning at least one full business
                       cycle (expansion + contraction), per NBER-style
                       cycle dating — avoids anchoring "normal" to only
                       one phase of the cycle. Documented explicitly so
                       this isn't an arbitrary constant.
  3. since_last_break — from the most recent sexenio boundary that
                       tested as a statistically significant structural
                       break (src/analysis/structural_breaks.py) to the
                       present. If no boundary tests significant for a
                       given series, falls back to full_history, with
                       that fallback explicitly flagged in the result
                       (never silently substituted).

See SERIES_METADATA.md, Decisions Log, for why these three (not just
one) are computed and shown side by side.
"""

from dataclasses import dataclass

import pandas as pd

from src.analysis.structural_breaks import most_recent_significant_break

ROLLING_WINDOW_YEARS = 10


@dataclass
class WindowResult:
    window_type: str       # "full_history" | "rolling_10y" | "since_last_break"
    label: str              # human-readable date range, e.g. "1991-11 to 2026-09"
    data: pd.Series         # the sliced series for this window
    start_date: pd.Timestamp
    end_date: pd.Timestamp
    used_fallback: bool = False  # True only for since_last_break when no break was found


def _label(start: pd.Timestamp, end: pd.Timestamp) -> str:
    return f"{start:%Y-%m} to {end:%Y-%m}"


def get_full_history_window(series: pd.Series) -> WindowResult:
    series = series.dropna().sort_index()
    start, end = series.index.min(), series.index.max()
    return WindowResult("full_history", _label(start, end), series, start, end)


def get_rolling_window(
    series: pd.Series, years: int = ROLLING_WINDOW_YEARS
) -> WindowResult:
    series = series.dropna().sort_index()
    end = series.index.max()
    start_cutoff = end - pd.DateOffset(years=years)
    windowed = series[series.index >= start_cutoff]
    start = windowed.index.min()
    return WindowResult(
        f"rolling_{years}y", _label(start, end), windowed, start, end
    )


def get_since_break_window(series: pd.Series, alpha: float = 0.05) -> WindowResult:
    series = series.dropna().sort_index()
    break_date = most_recent_significant_break(series, alpha=alpha)

    if break_date is None:
        # No significant break found — fall back to full history, but
        # say so explicitly rather than silently returning a window
        # that looks like a real "since break" result.
        full = get_full_history_window(series)
        return WindowResult(
            "since_last_break",
            full.label + " (fallback: no significant break found)",
            full.data,
            full.start_date,
            full.end_date,
            used_fallback=True,
        )

    windowed = series[series.index >= break_date]
    start, end = windowed.index.min(), series.index.max()
    return WindowResult(
        "since_last_break", _label(start, end), windowed, start, end
    )


def get_all_windows(series: pd.Series, alpha: float = 0.05) -> list[WindowResult]:
    """
    Convenience function: returns the reference windows used in the
    PRODUCTION pipeline.

    IMPORTANT: as of 2026-09-14, this returns only full_history and
    rolling_10y — NOT since_last_break. The since_last_break window
    (and the Chow-test-based structural break detection behind it) was
    retired from the production pipeline after discovering that the
    underlying Chow test is misspecified for these series: fitting a
    single straight line to 20-35 years of non-linear macro history,
    then testing a short recent segment against it, causes almost ANY
    recent cutoff date to appear "significant" — not just genuine
    regime changes. A placebo test (comparing the real boundary's
    F-statistic against F-statistics from arbitrary control dates)
    confirmed this: for several series, the actual sexenio boundary's
    F-statistic ranked in the bottom 10-20% of a sample of random
    dates, meaning it was LESS distinguishable than a typical
    arbitrary cutoff, not more. Full details, including the numbers
    from this diagnostic, are in SERIES_METADATA.md, Decisions Log #11.

    get_since_break_window() and the Chow test machinery in
    structural_breaks.py are kept in the codebase for reference and
    future research (see README, "Research directions"), but are no
    longer wired into the production analysis pipeline.
    """
    return [
        get_full_history_window(series),
        get_rolling_window(series),
    ]