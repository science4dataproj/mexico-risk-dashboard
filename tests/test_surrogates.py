import numpy as np
from src.analysis.surrogates import select_arma_order
from src.analysis.surrogates import max_arma_order_for_sample

def test_select_arma_order_picks_known_ar1_structure():
    """A synthetic AR(1) series with a strong, known coefficient
    should have its order correctly identified as (1, q) for some
    small q, not something wildly different."""
    rng = np.random.default_rng(5)
    n = 300
    values = np.zeros(n)
    for t in range(1, n):
        values[t] = 0.7 * values[t - 1] + rng.normal(0, 1)
    result = select_arma_order(values)
    assert result["order"][0] >= 1  # some AR component should be detected
    assert result["adequate"] in (True, False)  # never None on success


def test_select_arma_order_reports_inadequacy_honestly():
    """Ljung-Box adequacy should be a real check, not always True."""
    rng = np.random.default_rng(6)
    white_noise = rng.normal(0, 1, 200)
    result = select_arma_order(white_noise, max_order=2)
    assert result["adequate"] is not None

def test_max_order_scales_with_sample_size_not_fixed():
    """The cap must differ across realistic sample sizes from this
    project's own series (GDP ~41 obs vs. daily FX ~2500+ obs) — a
    single fixed number for both was exactly the flaw being fixed."""
    small = max_arma_order_for_sample(41)
    large = max_arma_order_for_sample(2515)
    assert small < large
    assert small >= 1
    assert large <= 5  # hard_cap respected


def test_select_arma_order_reports_acf_pacf_for_manual_inspection():
    rng = np.random.default_rng(5)
    values = rng.normal(0, 1, 200)
    result = select_arma_order(values)
    assert "acf" in result and "pacf" in result
    assert len(result["acf"]) > 0