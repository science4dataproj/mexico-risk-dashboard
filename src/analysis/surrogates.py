"""
src/analysis/surrogates.py

Implements the ARMA-surrogate significance test for CSD (critical
slowing down) trend indicators, following the field's reference
methodology:

  Dakos, V., Carpenter, S. R., Brock, W. A., Ellison, A. M., Guttal, V.,
  Ives, A. R., Kéfi, S., Livina, V., Seekell, D. A., van Nes, E. H., &
  Scheffer, M. (2012). Methods for Detecting Early Warnings of Critical
  Transitions in Time Series Illustrated Using Simulated Ecological
  Data. PLOS ONE, 7(7), e41010.

Replaces the earlier ad hoc "real control dates" placebo approach
(see backtest.py's original design and early_warning.py's theoretical
Kendall p-value), both of which were found, empirically, to produce
wildly inflated false-positive rates (up to 98% in some series — see
SERIES_METADATA.md Decisions Log). Root cause of the earlier failures:
(1) rolling-window statistics are mechanically autocorrelated,
violating Kendall's independence assumption; (2) using OTHER REAL
DATES as a "null" reference isn't valid — real economic history has
its own genuine dynamics, it isn't noise.

The correct null hypothesis, per Dakos et al.: a synthetic ("surrogate")
series sharing the real series' short-term autocorrelation structure
(fitted via a low-order ARMA model on DETRENDED residuals) but with,
by construction, no systematic trend. Significance is the comparison
of the real trend statistic against the distribution of the same
statistic computed on many such surrogates.
"""

from dataclasses import dataclass

import numpy as np
import pandas as pd
from scipy import stats as scipy_stats
from scipy.ndimage import gaussian_filter1d
from statsmodels.tsa.arima.model import ARIMA
from statsmodels.tsa.arima_process import ArmaProcess

DEFAULT_ARMA_ORDER = (1, 0, 1)  # ARMA(1,1) — deliberately simple and
                                  # fixed, not AIC-selected, to keep
                                  # surrogate generation tractable and
                                  # its assumptions explicit/documented.
DEFAULT_N_SURROGATES = 1000
DEFAULT_DETREND_BANDWIDTH_FRACTION = 0.25


def gaussian_detrend(values: np.ndarray, bandwidth_fraction: float = DEFAULT_DETREND_BANDWIDTH_FRACTION) -> np.ndarray:
    """
    Removes a smooth, long-run trend via a Gaussian kernel smoother,
    returning residuals. Necessary because computing rolling
    autocorrelation/variance directly on a trending raw series
    conflates "this series has a smooth trend" with "this series is
    losing resilience" — not the same thing, and the first can
    mechanically inflate both AC1 and variance without any genuine
    CSD signal present.
    """
    n = len(values)
    sigma = max(2.0, n * bandwidth_fraction)
    trend = gaussian_filter1d(values, sigma=sigma, mode="nearest")
    return values - trend


def rolling_autocorr_lag1_array(values: np.ndarray, window: int) -> np.ndarray:
    """
    Vectorized lag-1 rolling autocorrelation, using pandas' compiled
    rolling-correlation implementation instead of a per-point Python
    loop — necessary because this function is called ~1000 times per
    (series, window, stat) combination when generating surrogates
    (see surrogate_trend_test), and the original loop-based version
    would make that computationally impractical for daily series with
    thousands of points.
    """
    s = pd.Series(values)
    lagged = s.shift(1)
    return s.rolling(window).corr(lagged).to_numpy()


def rolling_variance_array(values: np.ndarray, window: int) -> np.ndarray:
    """Vectorized rolling variance via pandas' compiled implementation."""
    return pd.Series(values).rolling(window).var(ddof=1).to_numpy()


def fit_arma(residuals: np.ndarray, order: tuple[int, int, int] = DEFAULT_ARMA_ORDER):
    """Fits a low-order ARMA model to detrended residuals."""
    return ARIMA(residuals, order=order, trend="n").fit()

from statsmodels.stats.diagnostic import acorr_ljungbox
from statsmodels.tsa.stattools import acf, pacf

#MAX_ARMA_ORDER = 2
LJUNG_BOX_LAGS = 10


def max_arma_order_for_sample(n_obs: int, min_obs_per_param: int = 15, hard_cap: int = 5) -> int:
    """
    Caps the ARMA order search according to how much data is
    available, instead of a single fixed number applied to every
    series regardless of sample size (the earlier MAX_ARMA_ORDER=2
    default was flagged as undefended and, worse, would have been
    inconsistently too permissive for some series and too restrictive
    for others — see SERIES_METADATA.md Decisions Log).

    `min_obs_per_param=15` is a conservative, widely used rule of
    thumb for time-series parameter estimation (enough observations
    per estimated parameter for reasonably stable maximum-likelihood
    fits) — not attributed to a single canonical source, stated here
    as a heuristic, not a theorem. `hard_cap=5` is a separate,
    practical ceiling for computational tractability across a 9-series
    pipeline, documented as such.

    Rejected alternative: Schwert's (1989) rule for maximum lag length
    (12*(T/100)^0.25) was considered and discarded — it was designed
    specifically for augmented Dickey-Fuller unit-root test lag
    selection, not general ARMA order selection, and applying it here
    would have suggested absurdly high orders for small samples (e.g.,
    order 9 for this project's 41-observation quarterly GDP series) —
    the same kind of cross-context tool misapplication already caught
    and corrected elsewhere in this project (the Chow-test and
    sandpile/SOC episodes).
    """
    return max(1, min(hard_cap, n_obs // min_obs_per_param))


def select_arma_order(residuals: np.ndarray, max_order: int | None = None) -> dict:
    """
    Selects ARMA(p, 0, q) order via AICc grid search (AIC corrected for
    small-sample bias — Hurvich & Tsai, 1989, Biometrika, 76(2),
    297-307), over (0..max_order) x (0..max_order), where max_order
    defaults to max_arma_order_for_sample() if not given explicitly.
    Also computes ACF/PACF on the input residuals as a diagnostic
    (matching standard Box-Jenkins practice), stored alongside the
    result for manual inspection — the AICc search is not treated as
    a substitute for eyeballing these, only as the mechanized part of
    the same workflow.

    Follows selection with a Ljung-Box test on the winning model's
    residuals: if significant autocorrelation remains even after the
    selected order, that's reported explicitly (`adequate=False`).
    """
    n = len(residuals)
    if max_order is None:
        max_order = max_arma_order_for_sample(n)

    acf_vals = acf(residuals, nlags=min(20, n // 2 - 1), fft=True)
    pacf_vals = pacf(residuals, nlags=min(20, n // 2 - 1))

    best_aicc = np.inf
    best_order = (1, 1)  # fallback if every candidate fails to fit — documented, not silent
    best_fitted = None

    for p in range(max_order + 1):
        for q in range(max_order + 1):
            if p == 0 and q == 0:
                continue
            k = p + q + 1  # +1 for the estimated variance
            if n - k - 1 <= 0:
                continue  # AICc is undefined when k is too large relative to n — skip, don't crash
            try:
                candidate = ARIMA(residuals, order=(p, 0, q), trend="n").fit()
            except Exception:
                continue
            aicc = candidate.aic + (2 * k * (k + 1)) / (n - k - 1)
            if aicc < best_aicc:
                best_aicc = aicc
                best_order = (p, q)
                best_fitted = candidate

    if best_fitted is None:
        return {
            "order": best_order, "aicc": np.nan, "max_order_used": max_order,
            "adequate": False, "ljung_box_p": np.nan, "fitted": None,
            "acf": acf_vals, "pacf": pacf_vals,
        }

    lb = acorr_ljungbox(best_fitted.resid, lags=[LJUNG_BOX_LAGS], return_df=True)
    lb_p = lb["lb_pvalue"].iloc[0]

    return {
        "order": best_order, "aicc": best_aicc, "max_order_used": max_order,
        "adequate": bool(lb_p >= 0.05), "ljung_box_p": lb_p,
        "fitted": best_fitted, "acf": acf_vals, "pacf": pacf_vals,
    }
def generate_surrogates(
    residuals: np.ndarray,
    n_surrogates: int = DEFAULT_N_SURROGATES,
    order: tuple[int, int, int] | None = None,
    seed: int = 42,
) -> tuple[list[np.ndarray], dict] | None:
    """
    Fits ARMA to `residuals` (order auto-selected via AIC + Ljung-Box
    if `order` is not given explicitly — see select_arma_order), then
    generates `n_surrogates` synthetic series sharing the fitted
    short-term correlation structure but with no systematic trend.
    Returns (surrogates, selection_info) so callers can report which
    order was used and whether the Ljung-Box check passed — or None if
    fitting failed to converge.
    """
    n = len(residuals)
    selection_info = {"order": order, "aic": np.nan, "adequate": None, "ljung_box_p": np.nan}

    if order is None:
        selection = select_arma_order(residuals)
        if selection["fitted"] is None:
            return None
        fitted = selection["fitted"]
        selection_info = {k: v for k, v in selection.items() if k != "fitted"}
    else:
        try:
            fitted = fit_arma(residuals, order=order)
        except Exception:
            return None
        selection_info["order"] = order

    p, _, q = selection_info["order"][0], 0, selection_info["order"][1]
    ar = np.r_[1, -fitted.arparams] if len(fitted.arparams) else np.r_[1]
    ma = np.r_[1, fitted.maparams] if len(fitted.maparams) else np.r_[1]
    sigma = np.sqrt(fitted.params[-1])

    process = ArmaProcess(ar, ma)
    rng = np.random.default_rng(seed)

    surrogates = [
        process.generate_sample(nsample=n, scale=sigma, distrvs=lambda size: rng.standard_normal(size))
        for _ in range(n_surrogates)
    ]
    return surrogates, selection_info

@dataclass
class SurrogateTrendTestResult:
    real_tau: float
    p_value: float
    n_surrogates_used: int

@dataclass
class SurrogateTrendTestResult:
    real_tau: float
    p_value: float
    n_surrogates_used: int
    arma_order: tuple[int, int] = None
    arma_adequate: bool = None  # False = Ljung-Box found residual autocorrelation even after selection


def surrogate_trend_test(
    raw_values: np.ndarray,
    window: int,
    stat_fn,
    n_surrogates: int = DEFAULT_N_SURROGATES,
    order: tuple[int, int, int] | None = None,
    seed: int = 42,
) -> SurrogateTrendTestResult | None:
    residuals = gaussian_detrend(raw_values)

    real_stat = stat_fn(residuals, window)
    real_stat = real_stat[~np.isnan(real_stat)]
    if len(real_stat) < 12:
        return None
    real_tau, _ = scipy_stats.kendalltau(np.arange(len(real_stat)), real_stat)

    result = generate_surrogates(residuals, n_surrogates=n_surrogates, order=order, seed=seed)
    if result is None:
        return None
    surrogates, selection_info = result

    surrogate_taus = []
    for surrogate in surrogates:
        s_stat = stat_fn(surrogate, window)
        s_stat = s_stat[~np.isnan(s_stat)]
        if len(s_stat) < 12:
            continue
        tau, _ = scipy_stats.kendalltau(np.arange(len(s_stat)), s_stat)
        if not np.isnan(tau):
            surrogate_taus.append(tau)

    if not surrogate_taus:
        return None

    b = sum(1 for t in surrogate_taus if t >= real_tau)
    m = len(surrogate_taus)
    return SurrogateTrendTestResult(
        real_tau=real_tau, p_value=(b + 1) / (m + 1), n_surrogates_used=m,
        arma_order=selection_info.get("order"), arma_adequate=selection_info.get("adequate"),
    )