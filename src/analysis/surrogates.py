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


def generate_surrogates(
    residuals: np.ndarray,
    n_surrogates: int = DEFAULT_N_SURROGATES,
    order: tuple[int, int, int] = DEFAULT_ARMA_ORDER,
    seed: int = 42,
) -> list[np.ndarray] | None:
    """
    Fits ARMA to `residuals`, then generates `n_surrogates` synthetic
    series of the same length sharing the fitted short-term
    correlation structure but with no systematic trend by construction.
    Returns None if the ARMA fit fails to converge (documented, not
    silently misreported as a result).
    """
    n = len(residuals)
    try:
        fitted = fit_arma(residuals, order=order)
    except Exception:
        return None

    ar = np.r_[1, -fitted.arparams] if len(fitted.arparams) else np.r_[1]
    ma = np.r_[1, fitted.maparams] if len(fitted.maparams) else np.r_[1]
    sigma = np.sqrt(fitted.params[-1])

    process = ArmaProcess(ar, ma)
    rng = np.random.default_rng(seed)

    return [
        process.generate_sample(nsample=n, scale=sigma, distrvs=lambda size: rng.standard_normal(size))
        for _ in range(n_surrogates)
    ]


@dataclass
class SurrogateTrendTestResult:
    real_tau: float
    p_value: float
    n_surrogates_used: int


def surrogate_trend_test(
    raw_values: np.ndarray,
    window: int,
    stat_fn,
    n_surrogates: int = DEFAULT_N_SURROGATES,
    order: tuple[int, int, int] = DEFAULT_ARMA_ORDER,
    seed: int = 42,
) -> SurrogateTrendTestResult | None:
    """
    Full Dakos et al. (2012) pipeline for one series and one rolling
    statistic: detrend -> real trend -> fit ARMA on residuals ->
    generate surrogates -> same rolling stat + Kendall tau on each ->
    empirical p-value (Phipson & Smyth, 2010 correction) of the real
    tau against the surrogate (no-trend) distribution.
    """
    residuals = gaussian_detrend(raw_values)

    real_stat = stat_fn(residuals, window)
    real_stat = real_stat[~np.isnan(real_stat)]
    if len(real_stat) < 12:
        return None
    real_tau, _ = scipy_stats.kendalltau(np.arange(len(real_stat)), real_stat)

    surrogates = generate_surrogates(residuals, n_surrogates=n_surrogates, order=order, seed=seed)
    if surrogates is None:
        return None

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
    return SurrogateTrendTestResult(real_tau=real_tau, p_value=(b + 1) / (m + 1), n_surrogates_used=m)