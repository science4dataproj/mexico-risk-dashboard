"""
src/analysis/_quiet_warnings.py

Suppresses ONLY the specific, already-diagnosed warnings encountered
during the AICc ARMA grid search and GARCH fitting — matched by exact
message text, not by broad category or module. This is deliberate:
silencing an entire library's warning category risks hiding a future,
genuinely new warning that might signal a real problem (the same
instinct that led to catching the M1 ARMA(4,5) edge case and the CPI
alpha=0 corner solution). Only the four messages below were actually
investigated and confirmed as expected background noise — see
SERIES_METADATA.md Decisions Log.

Import this module once, anywhere early in an entry-point script
(run_analysis.py, run_backtest.py, run_garch_comparison.py), for its
side effect only:

    from src.analysis import _quiet_warnings  # noqa: F401
"""

import warnings

_KNOWN_BENIGN_MESSAGES = [
    r"Non-stationary starting autoregressive parameters.*",
    r"Non-invertible starting MA parameters.*",
    r"y is poorly scaled.*",
    r"Parameters are not consistent with a stationary model.*",
]

for _pattern in _KNOWN_BENIGN_MESSAGES:
    warnings.filterwarnings("ignore", message=_pattern)