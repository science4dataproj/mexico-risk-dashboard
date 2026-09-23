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
from src.analysis.surrogates import gaussian_detrend, select_arma_order


def fit_garch_and_test_trend(
    raw_values: np.ndarray,
    series_key: str,
    n_simulations: int = N_SIMULATIONS,
    seed: int = RANDOM_SEED,
) -> GarchTrendResult:
    """
    Two-step design, replacing the earlier mean="AR" approach: (1) fit
    the same AIC-selected ARMA(p,q) used for this project's CSD
    surrogates (select_arma_order) to remove the series' own
    short-term mean structure; (2) fit GARCH(1,1) with mean="Zero" on
    the ARMA residuals, now legitimately justified since the mean
    structure was already removed in step 1 — arch's built-in "AR"
    mean model cannot represent an MA component, so this avoids
    silently ignoring q > 0 for series where the selected order needs it.
    """
    residuals = gaussian_detrend(raw_values)

    arma_selection = select_arma_order(residuals)
    if arma_selection["fitted"] is None:
        return GarchTrendResult(series_key, converged=False, skip_reason="ARMA pre-whitening step failed to converge")

    arma_resid = np.asarray(arma_selection["fitted"].resid)
    arma_resid = arma_resid[~np.isnan(arma_resid)]

    std = np.std(arma_resid)
    if std == 0 or not np.isfinite(std):
        return GarchTrendResult(series_key, converged=False, skip_reason="zero or invalid variance after ARMA pre-whitening")
    scaled = arma_resid * 100 / std

    am = arch_model(scaled, mean="Zero", vol="Garch", p=1, q=1, dist="normal", rescale=False)
    try:
        fitted = am.fit(disp="off", show_warning=False)
    except Exception as e:
        return GarchTrendResult(series_key, converged=False, skip_reason=f"GARCH fit failed: {e}")

    params = fitted.params
    alpha = params.get("alpha[1]", np.nan)
    beta = params.get("beta[1]", np.nan)

    if alpha < 1e-6:
        return GarchTrendResult(
            series_key, converged=False, alpha=alpha, beta=beta, persistence=alpha + beta,
            skip_reason=f"alpha pinned at 0 (corner solution) — no ARCH effect beyond ARMA{arma_selection['order']} pre-whitening",
        )

    cond_vol = np.asarray(fitted.conditional_volatility)
    cond_vol = cond_vol[~np.isnan(cond_vol)]
    if len(cond_vol) < 12 or np.std(cond_vol) == 0:
        return GarchTrendResult(series_key, converged=False, skip_reason="insufficient or constant conditional volatility")

    real_tau, _ = scipy_stats.kendalltau(np.arange(len(cond_vol)), cond_vol)
    if np.isnan(real_tau):
        return GarchTrendResult(series_key, converged=False, skip_reason="Kendall's tau undefined on conditional volatility")

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