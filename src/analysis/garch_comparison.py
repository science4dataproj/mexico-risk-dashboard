"""
src/analysis/garch_comparison.py

Compares this project's CSD (critical slowing down) fragility signal
against a GARCH(1,1) conditional-volatility trend test on the same
series — addressing the open limitation noted throughout this
project's methodology: rising variance is exactly what GARCH-family
models (Engle, 1982; Bollerslev, 1986) are built to capture, and this
comparison was never run until now.

Design: GARCH(1,1) is fit to the same Gaussian-detrended residuals
used elsewhere in this project (surrogates.py), for a fair starting
point between methods. The model's conditional volatility series is
tested for a rising trend via Kendall's tau. Significance is NOT taken
from Kendall's theoretical p-value (the conditional volatility series
is itself autocorrelated by construction of the GARCH recursion,
which would reproduce the same inflated-false-positive problem already
diagnosed and fixed elsewhere in this project — see
SERIES_METADATA.md). Instead, synthetic paths are simulated directly
from the FITTED (stationary, trend-free by construction) GARCH model
itself, and the real tau is compared against that null distribution —
the GARCH-native equivalent of the ARMA-surrogate method used for the
CSD signal, applying the same Phipson & Smyth (2010) empirical
p-value correction.
"""

from dataclasses import dataclass

import numpy as np
from arch import arch_model
from scipy import stats as scipy_stats

from src.analysis.surrogates import gaussian_detrend

N_SIMULATIONS = 2000
RANDOM_SEED = 42
SIM_BURN = 500


@dataclass
class GarchTrendResult:
    series_key: str
    converged: bool
    alpha: float = np.nan
    beta: float = np.nan
    persistence: float = np.nan  # alpha + beta; close to 1 = highly persistent volatility
    garch_tau: float = np.nan
    garch_p_value: float = np.nan
    n_simulations_used: int = 0
    skip_reason: str = ""

def fit_garch_and_test_trend(
    raw_values: np.ndarray,
    series_key: str,
    n_simulations: int = N_SIMULATIONS,
    seed: int = RANDOM_SEED,
) -> GarchTrendResult:
    """
    Fits GARCH(1,1) to the series' detrended residuals and tests
    whether the resulting conditional volatility shows a significant
    rising trend, using synthetic paths simulated from the fitted
    model itself as the null distribution (same logic as the
    ARMA-surrogate test in surrogates.py, applied with GARCH's own
    native simulator instead of borrowing ARMA's).

    mean="AR", lags=1 lets the mean equation absorb the series' known
    lag-1 autocorrelation (the same assumption surrogates.py already
    makes when fitting ARMA(1,1) to these residuals) — using
    mean="Zero" instead forced that unexplained structure into the
    variance equation, producing degenerate persistence estimates
    pinned at 1.0 (see SERIES_METADATA.md Decisions Log for the
    diagnosis).
    """
    residuals = gaussian_detrend(raw_values)

    std = np.std(residuals)
    if std == 0 or not np.isfinite(std):
        return GarchTrendResult(series_key, converged=False, skip_reason="zero or invalid variance after detrending")
    scaled = residuals * 100 / std

    am = arch_model(scaled, mean="AR", lags=1, vol="Garch", p=1, q=1, dist="normal", rescale=False)
    try:
        fitted = am.fit(disp="off", show_warning=False)
    except Exception as e:
        return GarchTrendResult(series_key, converged=False, skip_reason=f"GARCH fit failed: {e}")

    params = fitted.params
    alpha = params.get("alpha[1]", np.nan)
    beta = params.get("beta[1]", np.nan)

    # A corner solution (alpha pinned to its lower bound, ~0) means the
    # model found no ARCH effect beyond what the AR(1) mean already
    # explains — the variance recursion becomes purely deterministic,
    # so every simulated path converges to the same constant value and
    # a trend test against that "null" is undefined, not just hard to
    # compute. This is a legitimate finding, reported explicitly.
    if alpha < 1e-6:
        return GarchTrendResult(
            series_key, converged=False,
            alpha=alpha, beta=beta, persistence=alpha + beta,
            skip_reason="alpha pinned at 0 (corner solution): no ARCH effect detected beyond the AR(1) mean — variance is effectively constant, a rising-trend test is undefined",
        )
    # AR(1) in the mean equation leaves the first conditional-volatility
    # point undefined (no prior observation to condition on) — drop
    # NaNs before testing for a trend, rather than letting Kendall's
    # tau silently return NaN on the whole series.
    cond_vol = np.asarray(fitted.conditional_volatility)
    cond_vol = cond_vol[~np.isnan(cond_vol)]
    if len(cond_vol) < 12:
        return GarchTrendResult(series_key, converged=False, skip_reason=f"only {len(cond_vol)} valid conditional-volatility points after dropping NaNs")
    if np.std(cond_vol) == 0:
        return GarchTrendResult(series_key, converged=False, skip_reason="conditional volatility is constant — degenerate GARCH fit")

    real_tau, _ = scipy_stats.kendalltau(np.arange(len(cond_vol)), cond_vol)
    if np.isnan(real_tau):
        return GarchTrendResult(series_key, converged=False, skip_reason="Kendall's tau undefined on conditional volatility even after cleaning")

    rng = np.random.default_rng(seed)
    sim_taus = []
    sim_errors = []
    for _ in range(n_simulations):
        try:
            sim = am.simulate(params, nobs=len(scaled), burn=SIM_BURN)
        except Exception as e:
            sim_errors.append(str(e))
            continue
        sim_vol = np.asarray(sim["volatility"].to_numpy())
        sim_vol = sim_vol[~np.isnan(sim_vol)]
        if len(sim_vol) < 12 or np.std(sim_vol) == 0:
            continue
        tau, _ = scipy_stats.kendalltau(np.arange(len(sim_vol)), sim_vol)
        if not np.isnan(tau):
            sim_taus.append(tau)

    if not sim_taus:
        reason = f"GARCH simulation produced no usable paths. First error: {sim_errors[0] if sim_errors else 'unknown'}"
        return GarchTrendResult(series_key, converged=False, skip_reason=reason)

    b = sum(1 for t in sim_taus if t >= real_tau)
    m = len(sim_taus)
    p_value = (b + 1) / (m + 1)

    return GarchTrendResult(
        series_key=series_key, converged=True,
        alpha=alpha, beta=beta, persistence=alpha + beta,
        garch_tau=real_tau, garch_p_value=p_value, n_simulations_used=m,
    )